"""
召回引擎核心模块
整合 5 路召回 + 排序，输出 RecallResult 列表
支持分层冷启动 (Phase 4)
"""

import logging
from typing import List, Optional

from localmind.config import config
from localmind.db import Database
from localmind.vector_store import VectorStore
from localmind.models import RecallResult, ConversationContext
from localmind.layers import LayerManager, WakeContext

from .semantic import SemanticRecall
from .history import HistoryRecall
from .popularity import PopularityRecall
from .cooccurrence import CooccurrenceRecall
from .gaps import GapDetector
from .ranker import RecallRanker

logger = logging.getLogger(__name__)


class RecallEngine:
    """
    召回引擎 - 整合 5 路召回 + 排序 + 分层冷启动

    召回流程：
    1. 分层唤醒 (LayerManager) - L0/L1/L2 冷启动
    2. 语义召回 (SemanticRecall) - 基于向量检索
    3. 历史召回 (HistoryRecall) - 上次对话维度
    4. 热度召回 (PopularityRecall) - 热门维度
    5. 共现召回 (CooccurrenceRecall) - 经常一起出现的维度
    6. 空白检测 (GapDetector) - 尚未填充的重要维度
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

        # 分层管理器 (Phase 4)
        self.layer_manager = LayerManager(self.db)

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

    def wake_up(self, query: Optional[str] = None, 
                conversation_id: Optional[str] = None) -> WakeContext:
        """
        分层冷启动唤醒 - Phase 4 核心功能
        
        返回 L0 + L1 + (可选 L2) 的轻量级上下文
        用于快速冷启动，token 控制在 ~200 (L0+L1) 或 ~700 (含 L2)
        
        Args:
            query: 当前查询，用于加载相关的 L2
            conversation_id: 对话 ID
            
        Returns:
            WakeContext 分层上下文
        """
        if not config.enable_layered_wake:
            logger.debug("[RecallEngine] 分层唤醒已禁用")
            return WakeContext()
        
        try:
            wake_ctx = self.layer_manager.wake_up(query, conversation_id)
            logger.info(
                f"[RecallEngine] Wake up: L0={wake_ctx.l0.token_estimate if wake_ctx.l0 else 0}t, "
                f"L1={wake_ctx.l1.token_estimate if wake_ctx.l1 else 0}t, "
                f"L2={wake_ctx.l2.token_estimate if wake_ctx.l2 else 0}t"
            )
            return wake_ctx
        except Exception as e:
            logger.warning(f"[RecallEngine] 分层唤醒失败: {e}")
            return WakeContext()
    
    def recall_with_wake(self, query: str, 
                         conversation_id: Optional[str] = None,
                         top_k: int = 5) -> tuple[WakeContext, ConversationContext]:
        """
        分层唤醒 + 深度召回 组合
        
        返回: (wake_context, full_context)
        - wake_context: 用于快速响应（L0+L1+L2）
        - full_context: 用于完整召回（L3 深度搜索）
        
        使用示例:
            wake_ctx, full_ctx = engine.recall_with_wake("我想学设计")
            quick_prompt = wake_ctx.to_prompt()  # ~200 tokens 快速响应
            full_prompt = full_ctx.to_injection_prompt()  # 完整上下文
        """
        # 1. 分层唤醒（快速）
        wake_ctx = self.wake_up(query, conversation_id)
        
        # 2. 完整召回（深度）
        full_ctx = self.recall(query, conversation_id, top_k)
        
        return wake_ctx, full_ctx

    def build_injection_prompt(self, ctx: ConversationContext) -> str:
        """
        根据召回结果构建注入上下文的 prompt

        Args:
            ctx: 召回上下文

        Returns:
            可直接注入的 prompt 字符串
        """
        return ctx.to_injection_prompt()
    
    def build_layered_prompt(self, wake_ctx: WakeContext, 
                            full_ctx: Optional[ConversationContext] = None) -> str:
        """
        构建分层注入 prompt（Phase 4）
        
        格式:
        [相关记忆 - 核心]
        L0: 身份认知
        L1: 关键记忆
        
        [相关记忆 - 当前]
        L2: 上下文相关（可选）
        
        [相关记忆 - 深度]
        L3: 完整召回结果
        """
        parts = []
        
        # L0 + L1（始终包含）
        core = wake_ctx.to_prompt(include_l2=False)
        if core:
            parts.append("[相关记忆 - 核心]\n" + core)
        
        # L2（可选）
        if config.l2_enable and wake_ctx.l2 and wake_ctx.l2.content:
            parts.append(f"[相关记忆 - 当前]\n{wake_ctx.l2.content}")
        
        # L3（完整召回）
        if full_ctx and full_ctx.recalled_results:
            deep = full_ctx.to_injection_prompt()
            if deep:
                parts.append("[相关记忆 - 深度]\n" + deep)
        
        return "\n\n".join(parts)
