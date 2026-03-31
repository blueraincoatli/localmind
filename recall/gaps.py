"""
空白检测模块
检测哪些重要维度还没有填充记忆
"""

import logging
from typing import List, Optional, Set, Dict

from localmind.db import Database
from localmind.models import RecallResult, MemoryRecord

logger = logging.getLogger(__name__)


class GapDetector:
    """空白检测 - 找出尚未填充的维度"""

    # 高优先级域（这些域的空白需要优先关注）
    HIGH_PRIORITY_DOMAINS = {
        "identity",
        "psychology",
        "career",
    }

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def detect(
        self,
        dimensions: List,
        current_dim_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[RecallResult]:
        """
        检测空白维度

        Args:
            dimensions: 所有可用维度列表
            current_dim_ids: 当前已召回的维度 ID（这些不算空白）
            top_k: 返回数量

        Returns:
            RecallResult 列表（空白维度）
        """
        current_set = set(current_dim_ids or [])

        # 找出缺失的维度
        missing_dims = [d for d in dimensions if d.id not in current_set]

        # 优先返回高优先级域的缺失维度
        prioritized = sorted(
            missing_dims,
            key=lambda d: (
                d.domain not in self.HIGH_PRIORITY_DOMAINS,
                d.id,
            )
        )

        results = []
        for dim in prioritized[:top_k]:
            # 空白维度没有记录，分数为 0
            results.append(
                RecallResult(
                    dimension_id=dim.id,
                    dimension_name=dim.name,
                    domain=dim.domain,
                    records=[],
                    score=0.0,
                    reasons=[f"空白检测: 该维度还没有记忆记录"],
                )
            )

        return results

    def get_gap_report(self, dimensions: List) -> Dict[str, int]:
        """
        获取各域填充率报告

        Returns:
            {domain: filled_count} dict
        """
        report: Dict[str, Dict[str, int]] = {}  # domain -> {total, filled}

        for dim in dimensions:
            if dim.domain not in report:
                report[dim.domain] = {"total": 0, "filled": 0}
            report[dim.domain]["total"] += 1

            try:
                records = self.db.get_records_by_dimension(dim.id)
                if records:
                    report[dim.domain]["filled"] += 1
            except Exception as e:
                logger.warning(f"[GapDetector] 检查维度失败 dim={dim.id}: {e}")

        return {
            domain: info["filled"]
            for domain, info in report.items()
        }

    def get_critical_gaps(self, dimensions: List, min_gap_ratio: float = 0.5) -> List[str]:
        """
        获取严重空白维度（某域超过 min_gap_ratio 比例未填充）

        Args:
            dimensions: 所有维度
            min_gap_ratio: 空白比例阈值

        Returns:
            严重空白维度 ID 列表
        """
        report = self.get_gap_report(dimensions)

        critical = []
        for dim in dimensions:
            filled = report.get(dim.domain, 0)
            # 估算该域总数
            domain_dims = [d for d in dimensions if d.domain == dim.domain]
            total = len(domain_dims)
            if total > 0 and (total - filled) / total >= min_gap_ratio:
                critical.append(dim.id)

        return critical
