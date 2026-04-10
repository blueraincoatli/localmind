"""
记忆写入模块 (Phase 6)
三重写入：SQLite + ChromaDB + Verbatim（原始对话）
"""

import logging
from typing import List, Optional

from localmind.config import config
from localmind.db import Database
from localmind.vector_store import VectorStore
from localmind.verbatim_store import VerbatimStore
from localmind.models import MemoryRecord, WriteAnalysis

logger = logging.getLogger(__name__)


class MemoryWriter:
    """
    记忆写入器 - 三重写入 SQLite + ChromaDB + Verbatim
    
    Phase 6 更新：
    - 支持 verbatim 原始对话存储
    - 可配置 enable_verbatim_storage
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        vector_store: Optional[VectorStore] = None,
        verbatim_store: Optional[VerbatimStore] = None,
    ):
        self.db = db or Database()
        self.vector_store = vector_store or VectorStore()
        self.verbatim_store = verbatim_store or VerbatimStore()
        self.enable_verbatim = getattr(config, 'enable_verbatim_storage', True)

    def write(self, record: MemoryRecord) -> bool:
        """
        写入单条记忆（双重写入）

        Args:
            record: MemoryRecord 实例

        Returns:
            是否成功
        """
        success_sql = False
        success_vec = False

        # 1. 写入 SQLite
        try:
            success_sql = self.db.add_record(
                record_id=record.id,
                dimension_id=record.dimension_id,
                content=record.content,
                evidence=record.evidence,
                confidence=record.confidence,
            )
        except Exception as e:
            logger.error(f"[MemoryWriter] SQLite 写入失败: {e}")

        # 2. 写入 ChromaDB
        try:
            self.vector_store.add_memory(
                dimension_id=record.dimension_id,
                content=record.content,
                record_id=record.id,
                metadata={
                    "confidence": record.confidence,
                    "evidence": record.evidence or "",
                },
            )
            success_vec = True
        except Exception as e:
            logger.error(f"[MemoryWriter] ChromaDB 写入失败: {e}")

        if not success_sql and not success_vec:
            logger.warning(f"[MemoryWriter] 记忆写入失败（双重失败）: dim={record.dimension_id}")
            return False

        logger.info(f"[MemoryWriter] 写入成功: {record.id} dim={record.dimension_id}")
        return True

    def write_analysis(self, analysis: WriteAnalysis) -> List[str]:
        """
        批量写入 WriteAnalysis 中的所有记录

        Args:
            analysis: WriteAnalysis 结果

        Returns:
            成功写入的 record_id 列表
        """
        if not analysis.should_record or not analysis.records:
            logger.debug("[MemoryWriter] 无需写入")
            return []

        written_ids = []
        for record in analysis.records:
            if self.write(record):
                written_ids.append(record.id)

        return written_ids

    def write_batch(self, records: List[MemoryRecord]) -> List[str]:
        """
        批量写入多条记忆

        Args:
            records: MemoryRecord 列表

        Returns:
            成功写入的 record_id 列表
        """
        written_ids = []
        for record in records:
            if self.write(record):
                written_ids.append(record.id)
        return written_ids
    
    def write_verbatim(self, conversation: str, source: str = "",
                       conversation_id: Optional[str] = None) -> List[str]:
        """
        写入原始对话（verbatim）
        
        Phase 6：存储原始对话片段，作为结构化记忆的 fallback
        
        Args:
            conversation: 对话文本
            source: 来源标识
            conversation_id: 对话 ID
            
        Returns:
            存储的 embedding_id 列表
        """
        if not self.enable_verbatim:
            logger.debug("[MemoryWriter] Verbatim 存储已禁用")
            return []
        
        try:
            embedding_ids = self.verbatim_store.store_conversation(
                conversation=conversation,
                source=source or conversation_id or "unknown"
            )
            logger.info(f"[MemoryWriter] Verbatim 存储: {len(embedding_ids)} 个片段 "
                       f"source={source}")
            return embedding_ids
        except Exception as e:
            logger.error(f"[MemoryWriter] Verbatim 存储失败: {e}")
            return []
    
    def write_analysis_with_verbatim(self, analysis: WriteAnalysis,
                                     conversation: str,
                                     conversation_id: Optional[str] = None) -> dict:
        """
        同时写入结构化记忆和 verbatim 原始对话
        
        Args:
            analysis: LLM 分析结果
            conversation: 原始对话文本
            conversation_id: 对话 ID
            
        Returns:
            写入结果统计
        """
        result = {
            "structured_ids": [],
            "verbatim_ids": [],
            "success": False
        }
        
        # 1. 写入结构化记忆
        if analysis.is_significant():
            result["structured_ids"] = self.write_analysis(analysis)
        
        # 2. 写入 verbatim
        result["verbatim_ids"] = self.write_verbatim(
            conversation=conversation,
            conversation_id=conversation_id
        )
        
        result["success"] = len(result["structured_ids"]) > 0 or len(result["verbatim_ids"]) > 0
        
        logger.info(
            f"[MemoryWriter] 混合写入: "
            f"structured={len(result['structured_ids'])}, "
            f"verbatim={len(result['verbatim_ids'])}"
        )
        
        return result
