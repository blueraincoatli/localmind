"""
召回排序模块
使用 HeyCube 公式进行综合评分排序

公式：score(d) = α·rel_llm + β·hist + γ·pop + δ·cooc - λ·fatigue - μ·over_coverage
"""

import logging
import time
from typing import List, Dict, Optional
from collections import defaultdict

from localmind.config import config
from localmind.db import Database
from localmind.models import RecallResult

logger = logging.getLogger(__name__)


class RecallRanker:
    """召回排序器 - HeyCube 加权公式"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.alpha = config.recall_alpha    # rel_llm
        self.beta = config.recall_beta     # hist
        self.gamma = config.recall_gamma   # pop
        self.delta = config.recall_delta   # cooc
        self.lambda_ = config.recall_lambda  # fatigue
        self.mu = config.recall_mu         # over_coverage

    def rank(
        self,
        results: List[RecallResult],
        conversation_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RecallResult]:
        """
        对召回结果进行综合排序

        Args:
            results: 各类召回结果合并列表
            conversation_id: 对话 ID（用于计算疲劳度）
            top_k: 返回最终 top_k

        Returns:
            排序后的 RecallResult 列表
        """
        if not results:
            return []

        # 聚合同一维度的多路召回结果
        dim_results: Dict[str, RecallResult] = {}
        for r in results:
            if r.dimension_id in dim_results:
                # 合并记录
                existing = dim_results[r.dimension_id]
                existing.records.extend(r.records)
                existing.score = max(existing.score, r.score)
                existing.reasons.extend(r.reasons)
            else:
                dim_results[r.dimension_id] = r

        # 计算各维度得分
        scored = []
        for dim_id, result in dim_results.items():
            score_breakdown = self._compute_score(
                result,
                conversation_id=conversation_id,
            )
            result.score = score_breakdown["total"]
            result.reasons.extend(score_breakdown["reasons"])
            scored.append(result)

        # 按得分降序排列
        scored.sort(key=lambda x: x.score, reverse=True)

        return scored[:top_k]

    def _compute_score(
        self,
        result: RecallResult,
        conversation_id: Optional[str] = None,
    ) -> Dict:
        """计算单个维度的综合得分"""
        reasons = []

        # rel_llm: 使用语义相似度作为 LLM 相关性
        rel_llm = result.score  # 已有 score 代表语义相关性
        reasons.append(f"rel_llm={rel_llm:.3f}*α={self.alpha:.2f}")

        # hist: 历史使用权重（查 use_count）
        hist = self._get_history_score(result.dimension_id)
        reasons.append(f"hist={hist:.3f}*β={self.beta:.2f}")

        # pop: 热度得分
        pop = self._get_popularity_score(result.dimension_id)
        reasons.append(f"pop={pop:.3f}*γ={self.gamma:.2f}")

        # cooc: 共现得分
        cooc = self._get_cooccurrence_score(result.dimension_id, result.domain)
        reasons.append(f"cooc={cooc:.3f}*δ={self.delta:.2f}")

        # fatigue: 疲劳度惩罚（近期频繁使用的降权）
        fatigue = self._get_fatigue_score(result.dimension_id, conversation_id)
        reasons.append(f"fatigue={fatigue:.3f}*λ={self.lambda_:.2f}")

        # over_coverage: 过度覆盖惩罚（同一域已有太多记忆的降权）
        over_coverage = self._get_over_coverage_score(result.dimension_id, result.domain)
        reasons.append(f"over_coverage={over_coverage:.3f}*μ={self.mu:.2f}")

        total = (
            self.alpha * rel_llm
            + self.beta * hist
            + self.gamma * pop
            + self.delta * cooc
            - self.lambda_ * fatigue
            - self.mu * over_coverage
        )

        return {
            "total": max(0.0, total),
            "reasons": reasons,
        }

    def _get_history_score(self, dimension_id: str) -> float:
        """历史访问得分（0-1）"""
        try:
            records = self.db.get_records_by_dimension(dimension_id)
            if not records:
                return 0.0
            total_uses = sum(r.use_count for r in records)
            return min(total_uses / 50.0, 1.0)  # 归一化
        except Exception as e:
            logger.warning(f"[RecallRanker] 历史得分计算失败 dim={dimension_id}: {e}")
            return 0.0

    def _get_popularity_score(self, dimension_id: str) -> float:
        """热度得分"""
        try:
            top_dims = self.db.get_top_dimensions(limit=20)
            dim_scores = {dim_id: score for dim_id, score in top_dims}
            total = sum(score for _, score in top_dims) or 1
            score = dim_scores.get(dimension_id, 0)
            return min(score / total, 1.0) if total > 0 else 0.0
        except Exception as e:
            logger.warning(f"[RecallRanker] 热度得分计算失败 dim={dimension_id}: {e}")
            return 0.0

    def _get_cooccurrence_score(self, dimension_id: str, domain: str) -> float:
        """共现得分"""
        try:
            related = self.db.get_cooccurrence_dims(dimension_id, limit=5)
            return min(len(related) / 5.0, 1.0)
        except Exception as e:
            logger.warning(f"[RecallRanker] 共现得分计算失败 dim={dimension_id}: {e}")
            return 0.0

    def _get_fatigue_score(
        self,
        dimension_id: str,
        conversation_id: Optional[str] = None,
    ) -> float:
        """疲劳度惩罚（0-1，越高惩罚越大）"""
        if not conversation_id:
            return 0.0
        try:
            last_dims = self.db.get_last_conversation_dims(conversation_id, limit=3)
            if dimension_id in last_dims:
                idx = last_dims.index(dimension_id)
                return 1.0 - (0.3 * idx)  # 最近使用的惩罚更大
            return 0.0
        except Exception:
            return 0.0

    def _get_over_coverage_score(self, dimension_id: str, domain: str) -> float:
        """过度覆盖惩罚（0-1）"""
        try:
            records = self.db.get_records_by_dimension(dimension_id)
            # 超过 5 条记录开始惩罚
            if len(records) <= 5:
                return 0.0
            return min((len(records) - 5) / 10.0, 1.0)
        except Exception:
            return 0.0
