#!/usr/bin/env python3
"""
LocalMind 数据库测试
"""

import sys
from pathlib import Path

# 添加项目根目录到 path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from localmind.config import config
from localmind.db import Database, Record, Dimension


def test_database_connection():
    """测试数据库连接"""
    print("[*] 测试数据库连接...")
    db = Database()
    conn = db.connect()
    assert conn is not None
    print("[+] 数据库连接成功")


def test_get_dimensions():
    """测试获取维度"""
    print("[*] 测试获取维度...")
    db = Database()
    dims = db.get_all_dimensions()
    print(f"    共有 {len(dims)} 个维度")
    assert len(dims) > 0, "应该至少有1个维度"
    
    # 按域分组显示
    from collections import defaultdict
    by_domain = defaultdict(list)
    for d in dims:
        by_domain[d.domain_name].append(d.name)
    
    for domain, dimensions in sorted(by_domain.items()):
        print(f"    {domain}: {len(dimensions)} 个")


def test_record_operations():
    """测试记录操作"""
    print("[*] 测试记录操作...")
    db = Database()
    
    test_id = "test_record_001"
    dim_id = "identity.name"
    
    # 清理旧数据（确保测试隔离）
    conn = db.connect()
    conn.execute("DELETE FROM records WHERE id = ?", (test_id,))
    conn.commit()
    
    # 添加测试记录
    success = db.add_record(
        record_id=test_id,
        dimension_id=dim_id,
        content="测试记忆内容",
        evidence="来自测试对话",
        confidence=0.9
    )
    assert success
    print("[+] 记录添加成功")
    
    # 读取记录
    record = db.get_record(test_id)
    assert record is not None
    assert record.content == "测试记忆内容"
    print("[+] 记录读取成功")
    
    # 更新使用次数
    db.increment_record_usage(test_id)
    record = db.get_record(test_id)
    assert record.use_count == 1
    print("[+] 使用计数更新成功")
    
    # 获取指定维度记录
    records = db.get_records_by_dimension(dim_id)
    assert len(records) > 0
    print(f"[+] 指定维度记录查询成功（{len(records)} 条）")


def test_cooccurrence():
    """测试共现关系"""
    print("[*] 测试共现关系...")
    db = Database()
    
    dims = ["identity.name", "psychology.thinking_mode", "career.profession"]
    db.update_cooccurrence(dims)
    print("[+] 共现关系更新成功")
    
    related = db.get_cooccurrence_dims("identity.name")
    print(f"    与 identity.name 共现的维度：{related}")


def test_history():
    """测试历史记录"""
    print("[*] 测试历史记录...")
    db = Database()
    
    conv_id = "test_conv_001"
    query = "测试对话"
    dims = ["identity.name", "psychology.thinking_mode"]
    
    db.add_conversation_history(conv_id, query, dims)
    print("[+] 历史记录添加成功")
    
    last_dims = db.get_last_conversation_dims(conv_id)
    assert last_dims == dims
    print("[+] 历史记录查询成功")


def test_stats():
    """测试统计功能"""
    print("[*] 测试统计功能...")
    db = Database()
    stats = db.get_stats()
    print(f"    总记录数：{stats['total_records']}")
    print(f"    总维度数：{stats['total_dimensions']}")
    print(f"    各域记录：{stats['records_by_domain']}")


def main():
    print("=" * 50)
    print("LocalMind 数据库测试")
    print("=" * 50)
    
    # 确保数据库已初始化
    if not config.db_path.exists():
        print("[-] 数据库未初始化，请先运行 scripts/init_db.py")
        sys.exit(1)
    
    test_database_connection()
    test_get_dimensions()
    test_record_operations()
    test_cooccurrence()
    test_history()
    test_stats()
    
    print("\n✅ 所有测试通过！")


if __name__ == "__main__":
    main()
