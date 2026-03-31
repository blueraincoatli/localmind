"""
热度召回模块
基于 use_count 统计进行热门维度召回
"""

import logging
from typing import List, Optional, Dict

from localmind.db import Database
from localmind.models import RecallResult, MemoryRecord

logger = logging.getLogger(__name__)


class PopularityRecall:
    """热度召回 - 按 use_count 排序"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def recall(
        self,
        dimensions: List,
        top_k: int = 10,
    ) -> List[RecallResult]:
        """
        基于热度（use_count）召回热门维度的记忆

        Args:
            dimensions: 所有可用维度列表
            top_k: 返回数量

        Returns:
            RecallResult 列表
        """
        dim_map = {dim.id: dim for dim in dimensions}

        try:
            top_dims = self.db.get_top_dimensions(limit=top_k)
        except Exception as e:
            logger.warning(f"[PopularityRecall] 获取热门维度失败: {e}")
            return []

        results = []
        for dim_id, total_uses in top_dims:
            if dim_id not in dim_map:
                continue
            dim = dim_map[dim_id]

            try:
                records = self.db.get_records_by_dimension(dim_id)
            except Exception as e:
                logger.warning(f"[PopularityRecall] 获取记录失败 dim={dim_id}: {e}")
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
                # 热度得分归一化 (0-1, 假设 max 100)
                pop_score = min(total_uses / 100.0, 1.0)
                results.append(
                    RecallResult(
                        dimension_id=dim_id,
                        dimension_name=dim.name,
                        domain=dim.domain,
                        records=memory_records,
                        score=pop_score,
                        reasons=[f"热度召回: 该维度共被使用 {total_uses} 次"],
                    )
                )

        return results

    def get_top_dimension_ids(self, limit: int = 10) -> List[str]:
        """获取热门维度 ID 列表"""
        try:
            return [dim_id for dim_id, _ in self.db.get_top_dimensions(limit=limit)]
        except Exception as e:
            logger.warning(f"[PopularityRecall] 获取热门维度失败: {e}")
            return []
