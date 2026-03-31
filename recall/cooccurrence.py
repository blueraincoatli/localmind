"""
共现召回模块
基于维度共现关系进行召回
"""

import logging
from typing import List, Optional, Dict

from localmind.db import Database
from localmind.models import RecallResult, MemoryRecord

logger = logging.getLogger(__name__)


class CooccurrenceRecall:
    """共现召回 - 哪些维度经常一起出现"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def recall(
        self,
        current_dim_ids: List[str],
        dimensions: List,
        top_k: int = 5,
    ) -> List[RecallResult]:
        """
        基于共现关系召回相关维度的记忆

        Args:
            current_dim_ids: 当前已确定的维度 ID 列表
            dimensions: 所有可用维度列表
            top_k: 每个维度返回的共现维度数量

        Returns:
            RecallResult 列表
        """
        dim_map = {dim.id: dim for dim in dimensions}

        all_related: Dict[str, float] = {}  # dim_id -> total_cooc_weight

        for dim_id in current_dim_ids:
            try:
                related = self.db.get_cooccurrence_dims(dim_id, limit=top_k)
            except Exception as e:
                logger.warning(f"[CooccurrenceRecall] 获取共现维度失败 dim={dim_id}: {e}")
                continue

            for related_dim in related:
                all_related[related_dim] = all_related.get(related_dim, 0) + 1

        if not all_related:
            return []

        results = []
        for dim_id, cooc_weight in sorted(all_related.items(), key=lambda x: -x[1]):
            if dim_id in current_dim_ids or dim_id not in dim_map:
                continue
            dim = dim_map[dim_id]

            try:
                records = self.db.get_records_by_dimension(dim_id)
            except Exception as e:
                logger.warning(f"[CooccurrenceRecall] 获取记录失败 dim={dim_id}: {e}")
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
                # 归一化共现得分
                max_weight = max(all_related.values())
                cooc_score = cooc_weight / max_weight if max_weight > 0 else 0
                results.append(
                    RecallResult(
                        dimension_id=dim_id,
                        dimension_name=dim.name,
                        domain=dim.domain,
                        records=memory_records,
                        score=cooc_score,
                        reasons=[f"共现召回: 与当前维度共现强度 {cooc_weight}"],
                    )
                )

        return results

    def update_cooccurrence(self, dimension_ids: List[str]) -> None:
        """更新维度共现关系"""
        try:
            self.db.update_cooccurrence(dimension_ids)
        except Exception as e:
            logger.warning(f"[CooccurrenceRecall] 更新共现关系失败: {e}")
