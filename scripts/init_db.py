#!/usr/bin/env python3
"""
LocalMind 数据库初始化脚本
初始化 SQLite schema 并加载 8 大域维度定义
"""

import sqlite3
import os
import yaml
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "personal.db"
DIMENSIONS_DIR = PROJECT_ROOT / "dimensions"


def ensure_dir(path: Path) -> None:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)


def init_schema(conn: sqlite3.Connection) -> None:
    """初始化数据库 schema"""
    cursor = conn.cursor()
    
    # 维度定义表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dimensions (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            domain_name TEXT NOT NULL,
            name TEXT NOT NULL,
            focus_prompt TEXT NOT NULL,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
    """)
    
    # 记忆记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            dimension_id TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence TEXT,
            confidence REAL DEFAULT 0.5,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            last_used_at INTEGER DEFAULT (strftime('%s', 'now')),
            use_count INTEGER DEFAULT 0,
            FOREIGN KEY (dimension_id) REFERENCES dimensions(id)
        )
    """)
    
    # 向量映射表（ChromaDB metadata 同步用）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS record_vectors (
            record_id TEXT PRIMARY KEY,
            dimension_id TEXT NOT NULL,
            content_text TEXT NOT NULL,
            embedding_id TEXT NOT NULL,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
    """)
    
    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_dimension ON records(dimension_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_last_used ON records(last_used_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_use_count ON records(use_count)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dimensions_domain ON dimensions(domain)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_record_vectors_dimension ON record_vectors(dimension_id)")
    
    # 共现关系表（记录哪些维度经常一起出现）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cooccurrence (
            dimension_a TEXT NOT NULL,
            dimension_b TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            last_seen INTEGER DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (dimension_a, dimension_b)
        )
    """)
    
    # 对话历史表（记录每次对话和调用的维度）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            query_text TEXT,
            recalled_dimensions TEXT,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
    """)
    
    conn.commit()
    print("[+] 数据库 schema 初始化完成")


def load_dimensions(conn: sqlite3.Connection) -> int:
    """加载所有维度定义 YAML 文件"""
    cursor = conn.cursor()
    count = 0
    
    for yaml_file in sorted(DIMENSIONS_DIR.glob("*.yaml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        domain = data["domain"]
        domain_name = data["domain_name"]
        
        for dim in data["dimensions"]:
            dim_id = dim["id"]
            cursor.execute(
                """INSERT OR REPLACE INTO dimensions 
                   (id, domain, domain_name, name, focus_prompt) 
                   VALUES (?, ?, ?, ?, ?)""",
                (dim_id, domain, domain_name, dim["name"], dim["focus_prompt"])
            )
            count += 1
    
    conn.commit()
    print(f"[+] 加载了 {count} 个维度定义")
    return count


def print_stats(conn: sqlite3.Connection) -> None:
    """打印数据库统计信息"""
    cursor = conn.cursor()
    
    # 维度统计
    cursor.execute("SELECT domain, domain_name, COUNT(*) FROM dimensions GROUP BY domain")
    print("\n📊 维度统计：")
    print(f"{'域':<15} {'维度数':<8}")
    print("-" * 25)
    for row in cursor.fetchall():
        print(f"{row[1]:<15} {row[2]:<8}")
    
    # 总记录数
    cursor.execute("SELECT COUNT(*) FROM records")
    total_records = cursor.fetchone()[0]
    print(f"\n📊 当前记忆记录数：{total_records}")


def main():
    print("=" * 50)
    print("LocalMind 数据库初始化")
    print("=" * 50)
    
    # 确保数据目录存在
    ensure_dir(DB_PATH.parent)
    
    # 连接数据库
    conn = sqlite3.connect(str(DB_PATH))
    print(f"[+] 数据库路径：{DB_PATH}")
    
    # 初始化 schema
    init_schema(conn)
    
    # 加载维度
    count = load_dimensions(conn)
    
    # 打印统计
    print_stats(conn)
    
    conn.close()
    print("\n✅ 初始化完成！")


if __name__ == "__main__":
    main()
