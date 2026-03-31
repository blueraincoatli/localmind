"""
语义召回模块
使用 ChromaDB 向量检索进行语义相似度召回
"""

import logging
from typing import List, Optional

from localmind.vector_store import VectorStore
from localmind.models import RecallResult

logger = logging.getLogger(__name__)


class SemanticRecall:
    """语义召回"""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or VectorStore()

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
                matches = []

            if matches:
                from localmind.models import MemoryRecord
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
            return []

        # 按维度聚合
        dim_records: dict = {}
        for m in matches:
            dim_id = m.get("dimension_id")
            if dim_id not in dim_map:
                continue
            if dim_id not in dim_records:
                dim_records[dim_id] = []
            from localmind.models import MemoryRecord
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
