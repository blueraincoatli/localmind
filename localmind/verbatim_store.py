"""
LocalMind Verbatim 原始对话存储模块 (Phase 6)
存储原始对话片段，作为结构化记忆的 fallback

设计理念：
- 热数据：结构化记忆（精准、小体积）
- 冷数据：Verbatim 原始对话（完整、大体积）
- 召回时优先结构化，无结果时 fallback 到 verbatim
"""

import re
import uuid
import logging
import sqlite3
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

from .config import config
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class VerbatimSnippet:
    """原始对话片段"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""  # 原始对话内容
    source: str = ""   # 来源（如 conversation_id）
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 元数据
    speaker: Optional[str] = None  # 说话人（用户/助手）
    turn_index: int = 0  # 对话轮次
    
    # 快速索引（无需 LLM）
    keywords: List[str] = field(default_factory=list)  # 提取的关键词
    domain_hints: List[str] = field(default_factory=list)  # 可能的域提示
    
    @property
    def is_user_speech(self) -> bool:
        """是否用户发言"""
        return self.speaker == "user" if self.speaker else False
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "timestamp": int(self.timestamp.timestamp()),
            "speaker": self.speaker,
            "turn_index": self.turn_index,
            "keywords": self.keywords,
            "domain_hints": self.domain_hints,
        }


class VerbatimStore:
    """
    原始对话存储管理器
    
    使用独立的 ChromaDB collection 存储原始对话
    支持：
    1. 对话分割和索引
    2. 关键词提取（规则-based，无 LLM）
    3. 语义搜索 fallback
    """
    
    COLLECTION_NAME = "localmind_verbatim"
    SQLITE_TABLE = "verbatim_snippets"
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or VectorStore()
        self._collection = None
        self._sqlite_ready = False
    
    def _get_collection(self):
        """获取 verbatim collection"""
        if self._collection is None:
            client = self.vector_store._get_client()
            self._collection = client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "LocalMind 原始对话 verbatim 存储"}
            )
        return self._collection
    
    # ========== 核心存储操作 ==========
    
    def store_snippet(self, snippet: VerbatimSnippet) -> str:
        """
        存储原始对话片段
        
        Args:
            snippet: VerbatimSnippet 实例
            
        Returns:
            embedding_id
        """
        try:
            collection = self._get_collection()
            
            # 生成向量（复用 VectorStore 的 embedding 逻辑）
            embedding = self.vector_store._generate_embedding(snippet.content)
            
            # 构建元数据
            metadata = {
                "snippet_id": snippet.id,
                "source": snippet.source,
                "speaker": snippet.speaker or "",
                "turn_index": snippet.turn_index,
                "keywords": ",".join(snippet.keywords[:10]),  # 限制长度
                "domain_hints": ",".join(snippet.domain_hints[:5]),
                "timestamp": int(snippet.timestamp.timestamp()),
            }
            
            embedding_id = str(uuid.uuid4())
            
            collection.add(
                ids=[embedding_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[snippet.content]
            )
            logger.debug(f"[VerbatimStore] 存储片段(向量): {snippet.id[:8]}... "
                        f"keywords={snippet.keywords[:3]}")
            return embedding_id
        except Exception as e:
            logger.warning(f"[VerbatimStore] 向量存储不可用，回退到 SQLite: {e}")
            return self._store_snippet_sqlite(snippet)
    
    def store_conversation(self, conversation: str, source: str = "",
                          conversation_id: Optional[str] = None) -> List[str]:
        """
        存储完整对话，自动分割成片段
        
        Args:
            conversation: 对话文本（多轮）
            source: 来源标识
            conversation_id: 可选的对话 ID
            
        Returns:
            存储的 embedding_id 列表
        """
        # 分割对话
        snippets = self._split_conversation(conversation, source or conversation_id)
        
        # 批量存储
        embedding_ids = []
        for snippet in snippets:
            try:
                eid = self.store_snippet(snippet)
                embedding_ids.append(eid)
            except Exception as e:
                logger.warning(f"[VerbatimStore] 存储片段失败: {e}")
        
        logger.info(f"[VerbatimStore] 存储对话: {len(embedding_ids)} 个片段 "
                   f"source={source}")
        return embedding_ids
    
    # ========== 搜索操作 ==========
    
    def search(self, query: str, n_results: int = 5,
               speaker_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        语义搜索原始对话
        
        Args:
            query: 查询文本
            n_results: 返回结果数
            speaker_filter: 可选，过滤说话人 ("user"/"assistant")
            
        Returns:
            匹配的 verbatim 片段列表
        """
        try:
            collection = self._get_collection()
            
            # 生成查询向量
            query_embedding = self.vector_store._generate_embedding(query)
            
            # 构建过滤条件
            where = None
            if speaker_filter:
                where = {"speaker": speaker_filter}
            
            # 执行查询
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["metadatas", "documents", "distances"]
            )
            
            # 格式化结果
            matches = []
            if results["ids"] and len(results["ids"]) > 0:
                for i, embedding_id in enumerate(results["ids"][0]):
                    meta = results["metadatas"][0][i]
                    matches.append({
                        "embedding_id": embedding_id,
                        "snippet_id": meta.get("snippet_id"),
                        "content": results["documents"][0][i],
                        "source": meta.get("source"),
                        "speaker": meta.get("speaker"),
                        "keywords": meta.get("keywords", "").split(",") if meta.get("keywords") else [],
                        "distance": results["distances"][0][i],
                        "similarity": 1 - results["distances"][0][i],
                    })
            
            return matches
        except Exception as e:
            logger.warning(f"[VerbatimStore] 向量搜索不可用，回退到 SQLite: {e}")
            return self._search_sqlite(query, n_results=n_results, speaker_filter=speaker_filter)
    
    def search_by_keywords(self, keywords: List[str], 
                          n_results: int = 5) -> List[Dict[str, Any]]:
        """
        关键词搜索（无需向量，纯 metadata 过滤）
        
        用于零 LLM 模式下的快速召回
        """
        try:
            collection = self._get_collection()
            
            # 获取所有文档（在 small scale 下可行）
            all_docs = collection.get(include=["metadatas", "documents"])
            
            matches = []
            if all_docs["ids"]:
                for i, doc_id in enumerate(all_docs["ids"]):
                    meta = all_docs["metadatas"][i]
                    doc_keywords = meta.get("keywords", "").split(",")
                    
                    # 计算关键词匹配度
                    match_count = sum(1 for kw in keywords if kw.lower() in doc_keywords)
                    if match_count > 0:
                        matches.append({
                            "embedding_id": doc_id,
                            "snippet_id": meta.get("snippet_id"),
                            "content": all_docs["documents"][i],
                            "source": meta.get("source"),
                            "match_score": match_count / len(keywords),
                            "keywords": doc_keywords,
                        })
            
            # 按匹配度排序
            matches.sort(key=lambda x: x["match_score"], reverse=True)
            return matches[:n_results]
        except Exception:
            return self._search_sqlite_by_keywords(keywords, n_results=n_results)
    
    # ========== 对话分割和预处理 ==========
    
    def _split_conversation(self, conversation: str, 
                           source: str) -> List[VerbatimSnippet]:
        """
        分割对话为片段
        
        支持格式：
        1. 用户: xxx\n助手: yyy
        2. User: xxx\nAssistant: yyy
        3. 纯文本（按句子分割）
        """
        snippets = []
        
        # 尝试识别 "用户/助手" 或 "User/Assistant" 格式
        # 改进正则：更宽松地匹配冒号和空格
        pattern = r'(?:用户|User)\s*[:：\s]\s*(.*?)(?=(?:助手|Assistant)\s*[:：\s]|$)'
        user_matches = re.findall(pattern, conversation, re.DOTALL | re.IGNORECASE)
        
        turn_idx = 0
        
        # 处理用户发言
        for content in user_matches:
            content = content.strip()
            if len(content) > 5:  # 过滤太短的片段（降低阈值）
                snippet = VerbatimSnippet(
                    content=content,
                    source=source,
                    speaker="user",
                    turn_index=turn_idx,
                )
                # 提取关键词和域提示
                snippet.keywords = self._extract_keywords(content)
                snippet.domain_hints = self._infer_domains(content)
                snippets.append(snippet)
                turn_idx += 1
        
        # 如果没有识别到格式，尝试按行分割
        if not snippets:
            lines = conversation.strip().split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                # 过滤掉空行、助手回复、过短行
                if (line and 
                    len(line) > 10 and 
                    not line.lower().startswith(('助手', 'assistant'))):
                    # 去除 "用户:" 前缀
                    if line.lower().startswith(('用户', 'user')):
                        line = re.sub(r'^(?:用户|User)\s*[:：\s]', '', line, flags=re.IGNORECASE).strip()
                    
                    snippet = VerbatimSnippet(
                        content=line,
                        source=source,
                        speaker="user",
                        turn_index=i,
                    )
                    snippet.keywords = self._extract_keywords(line)
                    snippet.domain_hints = self._infer_domains(line)
                    snippets.append(snippet)
        
        # 如果还是没有，按句子分割
        if not snippets:
            sentences = re.split(r'[。！？\.\!\?\n]', conversation)
            for i, sent in enumerate(sentences):
                sent = sent.strip()
                if len(sent) > 15:  # 至少 15 字符
                    snippet = VerbatimSnippet(
                        content=sent,
                        source=source,
                        speaker="user",
                        turn_index=i,
                    )
                    snippet.keywords = self._extract_keywords(sent)
                    snippet.domain_hints = self._infer_domains(sent)
                    snippets.append(snippet)
        
        return snippets
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词（规则-based，无 LLM）
        
        策略：
        1. 提取引号内的内容
        2. 提取特定词性（简单启发式）
        3. 去除停用词
        """
        keywords = []
        
        # 1. 提取引号内容（通常是重要信息）
        quoted = re.findall(r'["""]([^"""]+)["""]', text)
        keywords.extend(quoted)
        
        # 2. 提取特定模式
        # 数字 + 单位
        numbers = re.findall(r'\d+\s*(?:年|月|日|岁|人|个|次)', text)
        keywords.extend(numbers)
        
        # 3. 提取 2-4 字的名词性短语（简单启发式）
        # 这里使用简单的长度和字符筛选
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
        
        # 停用词过滤
        stopwords = {"这个", "那个", "然后", "就是", "什么", "怎么", "觉得", "认为"}
        words = [w for w in words if w not in stopwords and len(w) >= 2]
        
        keywords.extend(words[:5])  # 限制数量
        
        return list(set(keywords))  # 去重
    
    def _infer_domains(self, text: str) -> List[str]:
        """
        推断可能的域（规则-based）
        
        返回可能的域列表，用于快速过滤
        """
        domains = []
        text_lower = text.lower()
        
        # 身份相关
        if any(kw in text for kw in ["我叫", "我是", "职业", "工作", "年龄", "性别"]):
            domains.append("identity")
        
        # 心理相关
        if any(kw in text for kw in ["性格", "情绪", "喜欢", "讨厌", "觉得", "感受"]):
            domains.append("psychology")
        
        # 职业相关
        if any(kw in text for kw in ["工作", "公司", "项目", "技能", "开发", "设计"]):
            domains.append("career")
        
        # 目标相关
        if any(kw in text for kw in ["目标", "计划", "想", "要", "学习", "提升"]):
            domains.append("goals")
        
        # 关系相关
        if any(kw in text for kw in ["朋友", "家人", "同事", "父母", "孩子"]):
            domains.append("relations")
        
        return domains
    
    # ========== 统计和管理 ==========
    
    def count(self) -> int:
        """统计 verbatim 片段数量"""
        try:
            collection = self._get_collection()
            return collection.count()
        except Exception:
            return self._count_sqlite()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_snippets": self.count(),
        }
        
        try:
            collection = self._get_collection()
            all_data = collection.get(include=["metadatas"])
            
            if all_data["metadatas"]:
                speakers = {}
                for meta in all_data["metadatas"]:
                    speaker = meta.get("speaker", "unknown")
                    speakers[speaker] = speakers.get(speaker, 0) + 1
                stats["by_speaker"] = speakers
                
        except Exception as e:
            logger.warning(f"[VerbatimStore] 向量统计失败，回退到 SQLite: {e}")
            stats.update(self._get_sqlite_stats())
        
        return stats
    
    def delete_by_source(self, source: str) -> int:
        """按来源删除 verbatim 片段"""
        try:
            collection = self._get_collection()
            # 查询要删除的 IDs
            results = collection.get(where={"source": source})
            if results["ids"]:
                collection.delete(ids=results["ids"])
                return len(results["ids"])
            return 0
        except Exception as e:
            logger.warning(f"[VerbatimStore] 向量删除失败，回退到 SQLite: {e}")
            return self._delete_sqlite_by_source(source)

    def _sqlite_connection(self) -> sqlite3.Connection:
        self._ensure_sqlite_table()
        conn = sqlite3.connect(str(config.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_sqlite_table(self) -> None:
        if self._sqlite_ready:
            return
        conn = sqlite3.connect(str(config.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.SQLITE_TABLE} (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    speaker TEXT,
                    turn_index INTEGER DEFAULT 0,
                    keywords TEXT,
                    domain_hints TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
                """
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.SQLITE_TABLE}_source ON {self.SQLITE_TABLE}(source)"
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.SQLITE_TABLE}_speaker ON {self.SQLITE_TABLE}(speaker)"
            )
            conn.commit()
            self._sqlite_ready = True
        finally:
            conn.close()

    def _store_snippet_sqlite(self, snippet: VerbatimSnippet) -> str:
        conn = self._sqlite_connection()
        try:
            cursor = conn.cursor()
            snippet_id = f"sqlite-{snippet.id}"
            cursor.execute(
                f"""
                INSERT OR REPLACE INTO {self.SQLITE_TABLE}
                (id, source, content, speaker, turn_index, keywords, domain_hints, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snippet_id,
                    snippet.source,
                    snippet.content,
                    snippet.speaker or "",
                    snippet.turn_index,
                    json.dumps(snippet.keywords, ensure_ascii=False),
                    json.dumps(snippet.domain_hints, ensure_ascii=False),
                    int(snippet.timestamp.timestamp()),
                ),
            )
            conn.commit()
            logger.debug(f"[VerbatimStore] 存储片段(SQLite): {snippet.id[:8]}...")
            return snippet_id
        finally:
            conn.close()

    def _search_sqlite(
        self,
        query: str,
        n_results: int = 5,
        speaker_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conn = self._sqlite_connection()
        try:
            cursor = conn.cursor()
            if speaker_filter:
                cursor.execute(
                    f"SELECT * FROM {self.SQLITE_TABLE} WHERE speaker = ? ORDER BY created_at DESC",
                    (speaker_filter,),
                )
            else:
                cursor.execute(f"SELECT * FROM {self.SQLITE_TABLE} ORDER BY created_at DESC")
            rows = cursor.fetchall()
        finally:
            conn.close()

        matches = []
        for row in rows:
            keywords = json.loads(row["keywords"] or "[]")
            similarity = self._lexical_similarity(query, row["content"], keywords)
            if similarity <= 0:
                continue
            matches.append({
                "embedding_id": row["id"],
                "snippet_id": row["id"],
                "content": row["content"],
                "source": row["source"],
                "speaker": row["speaker"],
                "keywords": keywords,
                "distance": 1 - similarity,
                "similarity": similarity,
            })

        matches.sort(key=lambda item: item["similarity"], reverse=True)
        return matches[:n_results]

    def _search_sqlite_by_keywords(self, keywords: List[str], n_results: int = 5) -> List[Dict[str, Any]]:
        conn = self._sqlite_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.SQLITE_TABLE} ORDER BY created_at DESC")
            rows = cursor.fetchall()
        finally:
            conn.close()

        matches = []
        normalized = [kw.strip().lower() for kw in keywords if kw.strip()]
        for row in rows:
            doc_keywords = json.loads(row["keywords"] or "[]")
            lowered_keywords = [kw.lower() for kw in doc_keywords]
            match_count = sum(1 for kw in normalized if kw in lowered_keywords)
            if match_count <= 0:
                continue
            matches.append({
                "embedding_id": row["id"],
                "snippet_id": row["id"],
                "content": row["content"],
                "source": row["source"],
                "match_score": match_count / max(len(normalized), 1),
                "keywords": doc_keywords,
            })

        matches.sort(key=lambda item: item["match_score"], reverse=True)
        return matches[:n_results]

    def _count_sqlite(self) -> int:
        try:
            conn = self._sqlite_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {self.SQLITE_TABLE}")
                return int(cursor.fetchone()[0])
            finally:
                conn.close()
        except Exception:
            return 0

    def _get_sqlite_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {"storage": "sqlite_fallback"}
        conn = self._sqlite_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT speaker, COUNT(*) FROM {self.SQLITE_TABLE} GROUP BY speaker")
            stats["by_speaker"] = {
                (row[0] or "unknown"): row[1]
                for row in cursor.fetchall()
            }
            return stats
        finally:
            conn.close()

    def _delete_sqlite_by_source(self, source: str) -> int:
        conn = self._sqlite_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.SQLITE_TABLE} WHERE source = ?", (source,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            conn.close()

    def _lexical_similarity(self, query: str, content: str, keywords: Optional[List[str]] = None) -> float:
        query_text = query.strip().lower()
        content_text = content.strip().lower()
        if not query_text or not content_text:
            return 0.0

        query_tokens = self._tokenize(query_text)
        content_tokens = self._tokenize(content_text)
        if keywords:
            content_tokens |= {kw.lower() for kw in keywords if kw}
        if not query_tokens or not content_tokens:
            return 0.0

        overlap = len(query_tokens & content_tokens)
        token_score = overlap / max(len(query_tokens), 1)
        substring_bonus = 0.0
        for token in sorted(query_tokens, key=len, reverse=True):
            if len(token) >= 2 and token in content_text:
                substring_bonus = max(substring_bonus, min(len(token) / 6.0, 0.35))
        return min(token_score * 0.75 + substring_bonus, 1.0)

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


# 全局 VerbatimStore 实例
verbatim_store = VerbatimStore()


def store_conversation(conversation: str, source: str = "") -> List[str]:
    """快捷函数：存储对话"""
    return verbatim_store.store_conversation(conversation, source)


def search_verbatim(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """快捷函数：搜索 verbatim"""
    return verbatim_store.search(query, n_results)
