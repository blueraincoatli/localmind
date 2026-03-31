"""
LocalMind 数据库操作模块
封装 SQLite 的常用操作
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from .config import config


@dataclass
class Record:
    """记忆记录"""
    id: str
    dimension_id: str
    content: str
    evidence: Optional[str] = None
    confidence: float = 0.5
    created_at: Optional[int] = None
    last_used_at: Optional[int] = None
    use_count: int = 0


@dataclass
class Dimension:
    """维度定义"""
    id: str
    domain: str
    domain_name: str
    name: str
    focus_prompt: str


class Database:
    """数据库操作类"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        self._conn: Optional[sqlite3.Connection] = None
    
    def connect(self):
        """连接数据库"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ========== 维度操作 ==========
    
    def get_all_dimensions(self) -> List[Dimension]:
        """获取所有维度"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dimensions ORDER BY domain, id")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            # 移除 created_at，因为它不在 Dimension dataclass 中
            d.pop("created_at", None)
            result.append(Dimension(**d))
        return result
    
    def get_dimension(self, dim_id: str) -> Optional[Dimension]:
        """获取单个维度"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dimensions WHERE id = ?", (dim_id,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            d.pop("created_at", None)
            return Dimension(**d)
        return None
    
    def get_dimensions_by_domain(self, domain: str) -> List[Dimension]:
        """获取指定域的所有维度"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dimensions WHERE domain = ?", (domain,))
        result = []
        for row in cursor.fetchall():
            d = dict(row)
            d.pop("created_at", None)
            result.append(Dimension(**d))
        return result
    
    # ========== 记录操作 ==========
    
    def add_record(
        self,
        record_id: str,
        dimension_id: str,
        content: str,
        evidence: Optional[str] = None,
        confidence: float = 0.5
    ) -> bool:
        """添加记忆记录"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO records (id, dimension_id, content, evidence, confidence)
                   VALUES (?, ?, ?, ?, ?)""",
                (record_id, dimension_id, content, evidence, confidence)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # 记录已存在，更新
            return self.update_record(record_id, content, evidence, confidence)
    
    def update_record(
        self,
        record_id: str,
        content: str,
        evidence: Optional[str] = None,
        confidence: float = 0.5
    ) -> bool:
        """更新记忆记录"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE records SET content = ?, evidence = ?, confidence = ?
               WHERE id = ?""",
            (content, evidence, confidence, record_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    
    def get_record(self, record_id: str) -> Optional[Record]:
        """获取记录"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        return Record(**dict(row)) if row else None
    
    def get_records_by_dimension(self, dimension_id: str) -> List[Record]:
        """获取指定维度的所有记录"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM records WHERE dimension_id = ? ORDER BY last_used_at DESC",
            (dimension_id,)
        )
        return [Record(**dict(row)) for row in cursor.fetchall()]
    
    def get_recent_records(self, limit: int = 10) -> List[Record]:
        """获取最近使用的记录"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM records ORDER BY last_used_at DESC LIMIT ?",
            (limit,)
        )
        return [Record(**dict(row)) for row in cursor.fetchall()]
    
    def increment_record_usage(self, record_id: str) -> None:
        """更新记录使用统计"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE records 
               SET use_count = use_count + 1, last_used_at = strftime('%s', 'now')
               WHERE id = ?""",
            (record_id,)
        )
        conn.commit()
    
    def get_top_dimensions(self, limit: int = 10) -> List[Tuple[str, int]]:
        """获取最热门的维度（按使用次数）"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT dimension_id, SUM(use_count) as total
               FROM records GROUP BY dimension_id
               ORDER BY total DESC LIMIT ?""",
            (limit,)
        )
        return [(row[0], row[1]) for row in cursor.fetchall()]
    
    # ========== 共现操作 ==========
    
    def update_cooccurrence(self, dimension_ids: List[str]) -> None:
        """更新维度共现关系"""
        conn = self.connect()
        cursor = conn.cursor()
        for i, dim_a in enumerate(dimension_ids):
            for dim_b in dimension_ids[i+1:]:
                # 保证顺序一致（字母序）
                if dim_a > dim_b:
                    dim_a, dim_b = dim_b, dim_a
                cursor.execute(
                    """INSERT INTO cooccurrence (dimension_a, dimension_b, count, last_seen)
                       VALUES (?, ?, 1, strftime('%s', 'now'))
                       ON CONFLICT(dimension_a, dimension_b) 
                       DO UPDATE SET count = count + 1, last_seen = strftime('%s', 'now')""",
                    (dim_a, dim_b)
                )
        conn.commit()
    
    def get_cooccurrence_dims(self, dimension_id: str, limit: int = 5) -> List[str]:
        """获取与指定维度共现的其他维度"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT 
                   CASE WHEN dimension_a = ? THEN dimension_b ELSE dimension_a END as related_dim,
                   count
               FROM cooccurrence
               WHERE dimension_a = ? OR dimension_b = ?
               ORDER BY count DESC LIMIT ?""",
            (dimension_id, dimension_id, dimension_id, limit)
        )
        return [row[0] for row in cursor.fetchall()]
    
    # ========== 历史记录 ==========
    
    def add_conversation_history(
        self,
        conversation_id: str,
        query: str,
        recalled_dimensions: List[str]
    ) -> None:
        """记录对话历史"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO conversation_history 
               (conversation_id, query_text, recalled_dimensions)
               VALUES (?, ?, ?)""",
            (conversation_id, query, json.dumps(recalled_dimensions))
        )
        conn.commit()
    
    def get_last_conversation_dims(self, conversation_id: str, limit: int = 5) -> List[str]:
        """获取上次对话使用的维度"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT recalled_dimensions FROM conversation_history
               WHERE conversation_id = ? 
               ORDER BY created_at DESC LIMIT 1""",
            (conversation_id,)
        )
        row = cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return []
    
    # ========== 统计 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        conn = self.connect()
        cursor = conn.cursor()
        
        stats = {}
        
        # 记录总数
        cursor.execute("SELECT COUNT(*) FROM records")
        stats["total_records"] = cursor.fetchone()[0]
        
        # 维度总数
        cursor.execute("SELECT COUNT(*) FROM dimensions")
        stats["total_dimensions"] = cursor.fetchone()[0]
        
        # 各域记录数
        cursor.execute(
            """SELECT domain, COUNT(*) FROM records 
               JOIN dimensions ON dimension_id = dimensions.id
               GROUP BY domain"""
        )
        stats["records_by_domain"] = dict(cursor.fetchall())
        
        # 热门维度
        cursor.execute(
            """SELECT dimension_id, SUM(use_count) as total
               FROM records GROUP BY dimension_id
               ORDER BY total DESC LIMIT 5"""
        )
        stats["top_dimensions"] = [
            {"dimension": row[0], "uses": row[1]} 
            for row in cursor.fetchall()
        ]
        
        return stats
