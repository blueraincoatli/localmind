"""
语义召回模块 (Phase 6)
使用 ChromaDB 向量检索进行语义相似度召回
支持 Verbatim fallback（原始对话召回）
"""

import logging
import re
from typing import List, Optional

from localmind.config import config
from localmind.db import Database
from localmind.vector_store import VectorStore
from localmind.verbatim_store import VerbatimStore
from localmind.models import RecallResult, MemoryRecord

logger = logging.getLogger(__name__)


class SemanticRecall:
    """
    语义召回
    
    Phase 6 更新：支持 Verbatim fallback
    - 优先召回结构化记忆
    - 结构化无结果时 fallback 到 verbatim 原始对话
    """

    def __init__(self, vector_store: Optional[VectorStore] = None,
                 verbatim_store: Optional[VerbatimStore] = None):
        self.db = Database()
        self.vector_store = vector_store or VectorStore()
        self.verbatim_store = verbatim_store or VerbatimStore()
        self.enable_verbatim_fallback = getattr(config, 'enable_verbatim_storage', True)

    def recall(
        self,
        query: str,
        dimensions: List,
        top_k: int = 5,
    ) -> List[RecallResult]:
        """
        执行语义召回

        Args:
            query: 当前对话查询
            dimensions: 所有可用维度列表
            top_k: 每维度返回数量

        Returns:
            RecallResult 列表
        """
        results = []

        for dim in dimensions:
            try:
                matches = self.vector_store.search(
                    query=query,
                    dimension_filter=dim.id,
                    n_results=top_k,
                )
            except Exception as e:
                logger.warning(f"[SemanticRecall] 向量搜索失败 dim={dim.id}: {e}")
                matches = self._lexical_matches(query, dimension_filter=dim.id, n_results=top_k)

            if matches:
                records = []
                for m in matches:
                    records.append(
                        MemoryRecord(
                            id=m.get("record_id", ""),
                            dimension_id=m.get("dimension_id", dim.id),
                            content=m.get("content", ""),
                            confidence=m.get("similarity", 0.5),
                        )
                    )

                top_similarity = matches[0].get("similarity", 0.0)
                results.append(
                    RecallResult(
                        dimension_id=dim.id,
                        dimension_name=dim.name,
                        domain=dim.domain,
                        records=records,
                        score=top_similarity,
                        reasons=[f"语义相似度: {top_similarity:.3f}"],
                    )
                )

        return results

    def recall_global(
        self,
        query: str,
        dimensions: List,
        top_k: int = 10,
    ) -> List[RecallResult]:
        """
        全局语义召回，不限制维度

        Args:
            query: 当前对话查询
            dimensions: 所有可用维度列表
            top_k: 全局返回数量

        Returns:
            RecallResult 列表
        """
        dim_map = {dim.id: dim for dim in dimensions}

        try:
            matches = self.vector_store.search(
                query=query,
                n_results=top_k,
            )
        except Exception as e:
            logger.warning(f"[SemanticRecall] 全局向量搜索失败: {e}")
            matches = self._lexical_matches(query, n_results=top_k)

        # 按维度聚合
        dim_records: dict = {}
        for m in matches:
            dim_id = m.get("dimension_id")
            if dim_id not in dim_map:
                continue
            if dim_id not in dim_records:
                dim_records[dim_id] = []
            dim_records[dim_id].append(
                MemoryRecord(
                    id=m.get("record_id", ""),
                    dimension_id=dim_id,
                    content=m.get("content", ""),
                    confidence=m.get("similarity", 0.5),
                )
            )

        results = []
        for dim_id, records in dim_records.items():
            dim = dim_map[dim_id]
            avg_score = sum(r.confidence for r in records) / len(records)
            results.append(
                RecallResult(
                    dimension_id=dim_id,
                    dimension_name=dim.name,
                    domain=dim.domain,
                    records=records,
                    score=avg_score,
                    reasons=[f"全局语义匹配, avg_sim={avg_score:.3f}"],
                )
            )

        return results
    
    def recall_with_verbatim_fallback(
        self,
        query: str,
        dimensions: List,
        top_k: int = 5,
        fallback_threshold: float = 0.3,
    ) -> List[RecallResult]:
        """
        语义召回 + Verbatim fallback
        
        Phase 6：
        1. 先尝试召回结构化记忆
        2. 如果结果不足或分数过低，fallback 到 verbatim 原始对话
        
        Args:
            query: 查询文本
            dimensions: 维度列表
            top_k: 返回结果数
            fallback_threshold: 触发 fallback 的分数阈值
            
        Returns:
            RecallResult 列表（可能包含 verbatim 结果）
        """
        # 1. 先召回结构化记忆
        structured_results = self.recall_global(query, dimensions, top_k=top_k)
        
        # 2. 检查结果质量
        need_fallback = False
        if not structured_results:
            need_fallback = True
            logger.debug("[SemanticRecall] 结构化召回无结果，触发 verbatim fallback")
        elif structured_results[0].score < fallback_threshold:
            need_fallback = True
            logger.debug(f"[SemanticRecall] 结构化召回分数过低 ({structured_results[0].score:.3f})，"
                        f"触发 verbatim fallback")
        
        # 3. 如需要，召回 verbatim
        if need_fallback and self.enable_verbatim_fallback:
            verbatim_results = self._recall_verbatim(query, top_k=3)
            if verbatim_results:
                # 合并结果（verbatim 作为补充）
                structured_results.extend(verbatim_results)
                # 重新排序
                structured_results.sort(key=lambda x: x.score, reverse=True)
        
        return structured_results[:top_k]
    
    def _recall_verbatim(self, query: str, top_k: int = 3) -> List[RecallResult]:
        """
        召回 verbatim 原始对话
        
        将 verbatim 片段包装为 RecallResult 格式
        """
        try:
            matches = self.verbatim_store.search(query, n_results=top_k)
            
            if not matches:
                return []
            
            results = []
            for match in matches:
                # 将 verbatim 包装为 RecallResult
                # 使用特殊维度 ID 标识 verbatim
                record = MemoryRecord(
                    id=match.get("snippet_id", ""),
                    dimension_id="verbatim.raw",
                    content=match.get("content", ""),
                    confidence=match.get("similarity", 0.5),
                    evidence=f"source: {match.get('source', 'unknown')}"
                )
                
                results.append(
                    RecallResult(
                        dimension_id="verbatim.raw",
                        dimension_name="原始对话",
                        domain="verbatim",
                        records=[record],
                        score=match.get("similarity", 0.0),
                        reasons=[f"verbatim_fallback: {match.get('keywords', [])[:3]}"],
                    )
                )
            
            logger.debug(f"[SemanticRecall] Verbatim 召回: {len(results)} 条")
            return results
            
        except Exception as e:
            logger.warning(f"[SemanticRecall] Verbatim 召回失败: {e}")
            return []

    def _lexical_matches(
        self,
        query: str,
        dimension_filter: Optional[str] = None,
        n_results: int = 5,
    ) -> List[dict]:
        """当 embedding 服务不可用时，退化为基于 SQLite 的词面匹配。"""
        try:
            if dimension_filter:
                records = self.db.get_records_by_dimension(dimension_filter)
            else:
                records = self.db.get_all_records()
        except Exception as e:
            logger.warning(f"[SemanticRecall] 词面回退失败: {e}")
            return []

        scored = []
        for record in records:
            score = self._lexical_similarity(query, record.content)
            if score <= 0:
                continue
            scored.append({
                "record_id": record.id,
                "dimension_id": record.dimension_id,
                "content": record.content,
                "similarity": score,
            })

        scored.sort(key=lambda item: item["similarity"], reverse=True)
        return scored[:n_results]

    def _lexical_similarity(self, query: str, content: str) -> float:
        """轻量词面相似度，兼容中英文。"""
        query_text = query.strip().lower()
        content_text = content.strip().lower()
        if not query_text or not content_text:
            return 0.0

        query_tokens = self._tokenize(query_text)
        content_tokens = self._tokenize(content_text)
        if not query_tokens or not content_tokens:
            return 0.0

        overlap = len(query_tokens & content_tokens)
        token_score = overlap / max(len(query_tokens), 1)

        substring_bonus = 0.0
        for token in sorted(query_tokens, key=len, reverse=True):
            if len(token) >= 2 and token in content_text:
                substring_bonus = max(substring_bonus, min(len(token) / 6.0, 0.35))

        char_overlap = len(set(query_text) & set(content_text)) / max(len(set(query_text)), 1)
        return min(token_score * 0.7 + char_overlap * 0.2 + substring_bonus, 1.0)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        latin_tokens = set(re.findall(r"[a-z0-9_]+", text))
        cjk_tokens: set[str] = set()
        for chunk in re.findall(r"[\u4e00-\u9fff]+", text):
            if len(chunk) == 1:
                cjk_tokens.add(chunk)
                continue
            cjk_tokens.add(chunk)
            for idx in range(len(chunk) - 1):
                cjk_tokens.add(chunk[idx:idx + 2])
        return latin_tokens | cjk_tokens
