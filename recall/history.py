"""
历史召回模块
基于上次对话使用的维度进行召回
"""

import logging
from typing import List, Optional

from localmind.db import Database
from localmind.models import RecallResult, MemoryRecord

logger = logging.getLogger(__name__)


class HistoryRecall:
    """历史召回 - 查找上次对话使用的维度"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def recall(
        self,
        conversation_id: str,
        dimensions: List,
        top_k: int = 5,
    ) -> List[RecallResult]:
        """
        基于对话历史召回相关维度的记忆

        Args:
            conversation_id: 当前对话 ID
            dimensions: 所有可用维度列表
            top_k: 返回数量

        Returns:
            RecallResult 列表
        """
        dim_map = {dim.id: dim for dim in dimensions}

        try:
            last_dims = self.db.get_last_conversation_dims(conversation_id, limit=top_k)
        except Exception as e:
            logger.warning(f"[HistoryRecall] 获取历史维度失败: {e}")
            last_dims = []

        if not last_dims:
            return []

        results = []
        for dim_id in last_dims:
            if dim_id not in dim_map:
                continue
            dim = dim_map[dim_id]

            try:
                records = self.db.get_records_by_dimension(dim_id)
            except Exception as e:
                logger.warning(f"[HistoryRecall] 获取维度记录失败 dim={dim_id}: {e}")
                continue

            memory_records = [
                MemoryRecord(
                    id=r.id,
                    dimension_id=r.dimension_id,
                    content=r.content,
                    evidence=r.evidence,
                    confidence=r.confidence,
                    use_count=r.use_count,
                )
                for r in records
            ]

            if memory_records:
                avg_confidence = sum(r.confidence for r in memory_records) / len(memory_records)
                results.append(
                    RecallResult(
                        dimension_id=dim_id,
                        dimension_name=dim.name,
                        domain=dim.domain,
                        records=memory_records,
                        score=avg_confidence,
                        reasons=[f"历史召回: 上次对话使用了该维度"],
                    )
                )

        return results

    def get_recent_dimensions(
        self,
        conversation_id: str,
        limit: int = 5,
    ) -> List[str]:
        """获取上次对话的维度 ID 列表"""
        try:
            return self.db.get_last_conversation_dims(conversation_id, limit=limit)
        except Exception as e:
            logger.warning(f"[HistoryRecall] 获取历史维度失败: {e}")
            return []
