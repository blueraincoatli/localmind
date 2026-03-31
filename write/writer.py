"""
记忆写入模块
双重写入：SQLite（db.py）+ ChromaDB（vector_store.py）
"""

import logging
from typing import List, Optional

from localmind.config import config
from localmind.db import Database
from localmind.vector_store import VectorStore
from localmind.models import MemoryRecord, WriteAnalysis

logger = logging.getLogger(__name__)


class MemoryWriter:
    """
    记忆写入器 - 双重写入 SQLite + ChromaDB
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.db = db or Database()
        self.vector_store = vector_store or VectorStore()

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
