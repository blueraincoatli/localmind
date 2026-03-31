"""
召回引擎核心模块
整合 5 路召回 + 排序，输出 RecallResult 列表
"""

import logging
from typing import List, Optional

from localmind.config import config
from localmind.db import Database
from localmind.vector_store import VectorStore
from localmind.models import RecallResult, ConversationContext

from .semantic import SemanticRecall
from .history import HistoryRecall
from .popularity import PopularityRecall
from .cooccurrence import CooccurrenceRecall
from .gaps import GapDetector
from .ranker import RecallRanker

logger = logging.getLogger(__name__)


class RecallEngine:
    """
    召回引擎 - 整合 5 路召回 + 排序

    召回流程：
    1. 语义召回 (SemanticRecall) - 基于向量检索
    2. 历史召回 (HistoryRecall) - 上次对话维度
    3. 热度召回 (PopularityRecall) - 热门维度
    4. 共现召回 (CooccurrenceRecall) - 经常一起出现的维度
    5. 空白检测 (GapDetector) - 尚未填充的重要维度
    → 加权排序 (RecallRanker)
    → Top-K 输出
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.db = db or Database()
        self.vector_store = vector_store or VectorStore()

        self.semantic = SemanticRecall(self.vector_store)
        self.history = HistoryRecall(self.db)
        self.popularity = PopularityRecall(self.db)
        self.cooccurrence = CooccurrenceRecall(self.db)
        self.gaps = GapDetector(self.db)
        self.ranker = RecallRanker(self.db)

        self._dimensions = None

    @property
    def dimensions(self) -> List:
        """获取所有维度（懒加载）"""
        if self._dimensions is None:
            self._dimensions = self.db.get_all_dimensions()
        return self._dimensions

    def recall(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        top_k: int = 5,
        include_gaps: bool = True,
    ) -> ConversationContext:
        """
        执行完整召回流程

        Args:
            query: 当前对话查询
            conversation_id: 对话 ID
            top_k: 返回维度数量
            include_gaps: 是否包含空白检测

        Returns:
            ConversationContext（含召回结果）
        """
        ctx = ConversationContext(
            conversation_id=conversation_id or "default",
            query=query,
        )

        all_results: List[RecallResult] = []

        # 1. 语义召回
        try:
            semantic_results = self.semantic.recall_global(
                query=query,
                dimensions=self.dimensions,
                top_k=10,
            )
            all_results.extend(semantic_results)
            logger.debug(f"[RecallEngine] 语义召回: {len(semantic_results)} 维度")
        except Exception as e:
            logger.warning(f"[RecallEngine] 语义召回失败: {e}")

        # 2. 历史召回
        current_dim_ids = [r.dimension_id for r in all_results]
        if conversation_id:
            try:
                history_results = self.history.recall(
                    conversation_id=conversation_id,
                    dimensions=self.dimensions,
                    top_k=5,
                )
                all_results.extend(history_results)
                logger.debug(f"[RecallEngine] 历史召回: {len(history_results)} 维度")
            except Exception as e:
                logger.warning(f"[RecallEngine] 历史召回失败: {e}")

        # 更新当前维度集合（包含历史召回的维度）
        current_dim_ids = [r.dimension_id for r in all_results]

        # 3. 热度召回
        try:
            pop_results = self.popularity.recall(
                dimensions=self.dimensions,
                top_k=10,
            )
            all_results.extend(pop_results)
            logger.debug(f"[RecallEngine] 热度召回: {len(pop_results)} 维度")
        except Exception as e:
            logger.warning(f"[RecallEngine] 热度召回失败: {e}")

        # 4. 共现召回（基于当前已有关键维度）
        if current_dim_ids:
            try:
                cooc_results = self.cooccurrence.recall(
                    current_dim_ids=current_dim_ids,
                    dimensions=self.dimensions,
                    top_k=5,
                )
                all_results.extend(cooc_results)
                logger.debug(f"[RecallEngine] 共现召回: {len(cooc_results)} 维度")
            except Exception as e:
                logger.warning(f"[RecallEngine] 共现召回失败: {e}")

        # 5. 空白检测
        if include_gaps:
            try:
                gap_results = self.gaps.detect(
                    dimensions=self.dimensions,
                    current_dim_ids=current_dim_ids,
                    top_k=3,
                )
                all_results.extend(gap_results)
                logger.debug(f"[RecallEngine] 空白检测: {len(gap_results)} 维度")
            except Exception as e:
                logger.warning(f"[RecallEngine] 空白检测失败: {e}")

        # 排序
        try:
            ranked = self.ranker.rank(
                results=all_results,
                conversation_id=conversation_id,
                top_k=top_k,
            )
            ctx.recalled_results = ranked
            logger.debug(f"[RecallEngine] 最终排序: {len(ranked)} 维度")
        except Exception as e:
            logger.warning(f"[RecallEngine] 排序失败: {e}")
            ctx.recalled_results = all_results[:top_k]

        return ctx

    def build_injection_prompt(self, ctx: ConversationContext) -> str:
        """
        根据召回结果构建注入上下文的 prompt

        Args:
            ctx: 召回上下文

        Returns:
            可直接注入的 prompt 字符串
        """
        return ctx.to_injection_prompt()
