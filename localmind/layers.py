"""
LocalMind 分层记忆管理模块
实现 MemPalace 式的冷启动分层机制

分层结构：
- L0 (Identity):    ~50 tokens,  始终加载，关键身份信息
- L1 (Critical):    ~120 tokens, 始终加载，高频记忆摘要
- L2 (Contextual):  ~500 tokens, 按需加载，当前主题相关
- L3 (Deep Search): 无上限，     按需查询，完整向量召回
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

from .config import config
from .db import Database
from .models import MemoryRecord

logger = logging.getLogger(__name__)


@dataclass
class LayerContext:
    """单层上下文"""
    layer_name: str  # "L0", "L1", "L2", "L3"
    content: str
    token_estimate: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.token_estimate == 0:
            self.token_estimate = self._estimate_tokens(self.content)
    
    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估计 token 数（英文 ~4 chars/token，中文 ~1.5 chars/token）"""
        if not text:
            return 0
        # 简单启发式：混合文本平均 ~2.5 chars/token
        return len(text) // 2


@dataclass
class WakeContext:
    """唤醒上下文（L0 + L1 + 可选 L2）"""
    l0: Optional[LayerContext] = None
    l1: Optional[LayerContext] = None
    l2: Optional[LayerContext] = None
    
    def to_prompt(self, include_l2: bool = True) -> str:
        """生成注入 prompt"""
        parts = []
        
        if self.l0 and self.l0.content:
            parts.append(f"[身份认知]\n{self.l0.content}")
        
        if self.l1 and self.l1.content:
            parts.append(f"[关键记忆]\n{self.l1.content}")
        
        if include_l2 and self.l2 and self.l2.content:
            parts.append(f"[当前上下文]\n{self.l2.content}")
        
        return "\n\n".join(parts) if parts else ""
    
    @property
    def total_tokens(self) -> int:
        """估算总 token 数"""
        total = 0
        if self.l0:
            total += self.l0.token_estimate
        if self.l1:
            total += self.l1.token_estimate
        if self.l2:
            total += self.l2.token_estimate
        return total
    
    @property
    def is_ready(self) -> bool:
        """是否有足够的唤醒上下文"""
        return (self.l0 is not None or self.l1 is not None)


class LayerManager:
    """
    分层记忆管理器
    
    负责：
    1. 管理 L0/L1/L2 三层记忆的加载和更新
    2. 生成冷启动上下文（wake_up）
    3. 维护关键事实（critical facts）
    """
    
    # 分层配置
    L0_MAX_TOKENS = 50
    L1_MAX_TOKENS = 120
    L2_MAX_TOKENS = 500
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self._l0_cache: Optional[str] = None
        self._l1_cache: Optional[str] = None
        self._cache_timestamp: Optional[datetime] = None
    
    def wake_up(self, query: Optional[str] = None, 
                conversation_id: Optional[str] = None) -> WakeContext:
        """
        唤醒记忆，返回 L0 + L1 + (可选 L2)
        
        Args:
            query: 当前查询，用于加载相关的 L2
            conversation_id: 对话 ID，用于加载历史上下文
        
        Returns:
            WakeContext 包含各层内容
        """
        ctx = WakeContext()
        
        # L0: 身份认知（始终加载）
        try:
            ctx.l0 = self._load_l0_identity()
            logger.debug(f"[LayerManager] L0 loaded: {ctx.l0.token_estimate} tokens")
        except Exception as e:
            logger.warning(f"[LayerManager] L0 加载失败: {e}")
        
        # L1: 关键记忆（始终加载）
        try:
            ctx.l1 = self._load_l1_critical()
            logger.debug(f"[LayerManager] L1 loaded: {ctx.l1.token_estimate} tokens")
        except Exception as e:
            logger.warning(f"[LayerManager] L1 加载失败: {e}")
        
        # L2: 上下文记忆（按需加载）
        if query:
            try:
                ctx.l2 = self._load_l2_contextual(query, conversation_id)
                logger.debug(f"[LayerManager] L2 loaded: {ctx.l2.token_estimate if ctx.l2 else 0} tokens")
            except Exception as e:
                logger.warning(f"[LayerManager] L2 加载失败: {e}")
        
        logger.info(f"[LayerManager] Wake up complete: {ctx.total_tokens} tokens")
        return ctx
    
    def _load_l0_identity(self) -> LayerContext:
        """加载 L0: 身份认知层"""
        # 从 critical_facts 表获取 identity 类型的事实
        facts = self._get_critical_facts("identity", limit=5)
        
        if not facts:
            # 回退：从 records 表获取 identity 域的记录
            facts = self._get_domain_records("identity", limit=3)
        
        content = self._format_facts(facts, max_tokens=self.L0_MAX_TOKENS)
        
        return LayerContext(
            layer_name="L0",
            content=content,
            metadata={"source": "identity_facts", "count": len(facts)}
        )
    
    def _load_l1_critical(self) -> LayerContext:
        """加载 L1: 关键记忆层"""
        # 获取高频使用的关键事实
        facts = self._get_critical_facts("critical", limit=10)
        
        if not facts:
            # 回退：获取最热门的记录（非 identity 域）
            facts = self._get_popular_records(limit=5)
        
        content = self._format_facts(facts, max_tokens=self.L1_MAX_TOKENS)
        
        return LayerContext(
            layer_name="L1",
            content=content,
            metadata={"source": "critical_facts", "count": len(facts)}
        )
    
    def _load_l2_contextual(self, query: str, 
                           conversation_id: Optional[str] = None) -> Optional[LayerContext]:
        """加载 L2: 上下文记忆层（基于查询相关）"""
        from .vector_store import VectorStore
        
        try:
            vs = VectorStore()
            # 语义搜索最相关的记忆
            matches = vs.search(query, n_results=10)
            
            if not matches:
                return None
            
            # 格式化为文本，控制 token 数
            parts = []
            current_tokens = 0
            
            for match in matches:
                content = match.get("content", "")
                estimated = len(content) // 2
                
                if current_tokens + estimated > self.L2_MAX_TOKENS:
                    break
                
                parts.append(f"- {content}")
                current_tokens += estimated
            
            return LayerContext(
                layer_name="L2",
                content="\n".join(parts),
                metadata={"query": query, "matches": len(matches)}
            )
            
        except Exception as e:
            logger.warning(f"[LayerManager] L2 向量搜索失败: {e}")
            return None
    
    def _get_critical_facts(self, fact_type: str, limit: int = 10) -> List[Dict]:
        """从 critical_facts 表获取关键事实"""
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT content, priority FROM critical_facts 
                   WHERE fact_type = ? 
                   ORDER BY priority DESC, updated_at DESC 
                   LIMIT ?""",
                (fact_type, limit)
            )
            return [{"content": row[0], "priority": row[1]} for row in cursor.fetchall()]
        except Exception as e:
            logger.debug(f"[LayerManager] critical_facts 表不存在或查询失败: {e}")
            return []
    
    def _get_domain_records(self, domain: str, limit: int = 5) -> List[Dict]:
        """获取指定域的记录"""
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT r.content, r.confidence 
                   FROM records r
                   JOIN dimensions d ON r.dimension_id = d.id
                   WHERE d.domain = ?
                   ORDER BY r.use_count DESC, r.last_used_at DESC
                   LIMIT ?""",
                (domain, limit)
            )
            return [{"content": row[0], "priority": int(row[1] * 10)} for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"[LayerManager] 获取 {domain} 域记录失败: {e}")
            return []
    
    def _get_popular_records(self, limit: int = 5) -> List[Dict]:
        """获取热门记录"""
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT content, use_count FROM records 
                   ORDER BY use_count DESC, last_used_at DESC
                   LIMIT ?""",
                (limit,)
            )
            return [{"content": row[0], "priority": row[1]} for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"[LayerManager] 获取热门记录失败: {e}")
            return []
    
    def _format_facts(self, facts: List[Dict], max_tokens: int) -> str:
        """格式化事实列表，控制 token 数"""
        if not facts:
            return ""
        
        parts = []
        current_tokens = 0
        
        for fact in facts:
            content = fact.get("content", "").strip()
            if not content:
                continue
            
            # 简单 token 估算
            estimated = len(content) // 2 + 1  # +1 for bullet
            
            if current_tokens + estimated > max_tokens:
                # 尝试截断最后一条
                remaining = (max_tokens - current_tokens) * 2
                if remaining > 20:  # 至少保留 20 chars
                    truncated = content[:remaining-3] + "..."
                    parts.append(f"- {truncated}")
                break
            
            parts.append(f"- {content}")
            current_tokens += estimated
        
        return "\n".join(parts)
    
    # ========== 关键事实管理 ==========
    
    def add_critical_fact(self, fact_type: str, content: str, 
                         priority: int = 0) -> bool:
        """
        添加关键事实到 L0/L1 层
        
        Args:
            fact_type: "identity" 或 "critical"
            content: 事实内容
            priority: 优先级（越高越重要）
        
        Returns:
            是否成功
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # 确保表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS critical_facts (
                    id TEXT PRIMARY KEY,
                    fact_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            import uuid
            fact_id = str(uuid.uuid4())
            
            cursor.execute(
                """INSERT INTO critical_facts (id, fact_type, content, priority)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                   content = excluded.content,
                   priority = excluded.priority,
                   updated_at = strftime('%s', 'now')""",
                (fact_id, fact_type, content, priority)
            )
            conn.commit()
            
            # 清除缓存
            self._invalidate_cache()
            
            logger.info(f"[LayerManager] 添加关键事实: type={fact_type}, priority={priority}")
            return True
            
        except Exception as e:
            logger.error(f"[LayerManager] 添加关键事实失败: {e}")
            return False
    
    def update_from_records(self, record: MemoryRecord) -> bool:
        """
        根据新记录自动更新关键事实
        
        规则：
        - identity.* 域的高置信度记录 → L0
        - 高使用次数的记录 → L1
        """
        try:
            # Identity 域自动进入 L0
            if record.dimension_id.startswith("identity.") and record.confidence > 0.7:
                return self.add_critical_fact(
                    "identity", 
                    record.content, 
                    priority=int(record.confidence * 10)
                )
            
            # 高频使用记录进入 L1
            if record.use_count >= 3:
                return self.add_critical_fact(
                    "critical",
                    record.content,
                    priority=record.use_count
                )
            
            return False
            
        except Exception as e:
            logger.warning(f"[LayerManager] 从记录更新关键事实失败: {e}")
            return False
    
    def _invalidate_cache(self):
        """清除缓存"""
        self._l0_cache = None
        self._l1_cache = None
        self._cache_timestamp = None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取分层统计"""
        stats = {
            "l0_max_tokens": self.L0_MAX_TOKENS,
            "l1_max_tokens": self.L1_MAX_TOKENS,
            "l2_max_tokens": self.L2_MAX_TOKENS,
        }
        
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # 关键事实统计
            try:
                cursor.execute(
                    "SELECT fact_type, COUNT(*) FROM critical_facts GROUP BY fact_type"
                )
                stats["critical_facts"] = dict(cursor.fetchall())
            except:
                stats["critical_facts"] = {"identity": 0, "critical": 0}
            
            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM records")
            stats["total_records"] = cursor.fetchone()[0]
            
        except Exception as e:
            logger.warning(f"[LayerManager] 获取统计失败: {e}")
        
        return stats


# 全局 LayerManager 实例
layer_manager = LayerManager()


def wake_up(query: Optional[str] = None, 
            conversation_id: Optional[str] = None) -> WakeContext:
    """
    快速唤醒函数
    
    使用示例：
        ctx = wake_up("我想学设计")
        prompt = ctx.to_prompt()
        # prompt 包含 L0 + L1 + L2，约 170-500 tokens
    """
    return layer_manager.wake_up(query, conversation_id)
