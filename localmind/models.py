"""
LocalMind 数据模型定义
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import hashlib


@dataclass
class MemoryRecord:
    """记忆记录（内存中的数据结构）"""
    dimension_id: str
    content: str
    evidence: Optional[str] = None
    confidence: float = 0.5
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: datetime = field(default_factory=datetime.now)
    use_count: int = 0
    
    @property
    def record_id(self) -> str:
        """兼容性别名"""
        return self.id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dimension_id": self.dimension_id,
            "content": self.content,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "created_at": int(self.created_at.timestamp()),
            "last_used_at": int(self.last_used_at.timestamp()),
            "use_count": self.use_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        return cls(
            id=data["id"],
            dimension_id=data["dimension_id"],
            content=data["content"],
            evidence=data.get("evidence"),
            confidence=data.get("confidence", 0.5),
            created_at=datetime.fromtimestamp(data["created_at"]),
            last_used_at=datetime.fromtimestamp(data["last_used_at"]),
            use_count=data.get("use_count", 0)
        )


@dataclass
class RecallResult:
    """召回结果"""
    dimension_id: str
    dimension_name: str
    domain: str
    records: List[MemoryRecord]
    score: float
    reasons: List[str] = field(default_factory=list)
    
    @property
    def top_record(self) -> Optional[MemoryRecord]:
        return self.records[0] if self.records else None
    
    def to_focus_prompt(self) -> str:
        """生成本维度的 focus prompt"""
        if not self.records:
            return f"[{self.dimension_name}] 无相关记忆"
        
        parts = [f"[{self.dimension_name}]"]
        for record in self.records[:3]:  # 最多3条
            parts.append(f"- {record.content}")
        return "\n".join(parts)


@dataclass 
class ConversationContext:
    """对话上下文"""
    conversation_id: str
    query: str
    recalled_results: List[RecallResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_injection_prompt(self) -> str:
        """生成注入上下文的 prompt"""
        if not self.recalled_results:
            return ""
        
        sections = ["[相关记忆]", ""]
        for result in self.recalled_results:
            sections.append(result.to_focus_prompt())
            sections.append("")
        
        return "\n".join(sections)


@dataclass
class WriteAnalysis:
    """写入分析结果"""
    should_record: bool
    records: List[MemoryRecord]
    reasoning: str = ""
    confidence: float = 0.5
    
    def is_significant(self) -> bool:
        """判断是否值得记录"""
        return self.should_record and len(self.records) > 0 and self.confidence > 0.4
