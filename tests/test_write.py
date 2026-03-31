#!/usr/bin/env python3
"""
LocalMind 写入引擎测试
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from write.analyzer import MemoryAnalyzer
from write.writer import MemoryWriter
from write.updater import MemoryUpdater


def test_imports():
    print("[*] 测试模块导入...")
    assert MemoryAnalyzer is not None
    assert MemoryWriter is not None
    assert MemoryUpdater is not None
    print("[+] 所有写入模块导入成功")


def test_analyzer_init():
    print("[*] 测试分析器初始化...")
    analyzer = MemoryAnalyzer()
    assert analyzer is not None
    print("[+] 记忆分析器初始化成功")


def test_analyzer_conversation():
    print("[*] 测试对话分析...")
    analyzer = MemoryAnalyzer()
    
    # 测试1：应该触发记录的对话
    conversation1 = "我其实是个内向的人，平时不太喜欢社交，喜欢一个人待着看书"
    result1 = analyzer.analyze(conversation1, conversation_id="test_conv_001")
    print(f"    对话1分析结果：should_record={result1.should_record}")
    if result1.records:
        for r in result1.records:
            print(f"    - {r.dimension_id}: {r.content[:30]}...")
    
    # 测试2：普通闲聊
    conversation2 = "今天天气不错啊"
    result2 = analyzer.analyze(conversation2, conversation_id="test_conv_002")
    print(f"    对话2分析结果：should_record={result2.should_record}")


def test_writer():
    print("[*] 测试写入器...")
    writer = MemoryWriter()
    assert writer is not None
    print("[+] 记忆写入器初始化成功")


def test_updater():
    print("[*] 测试更新器...")
    updater = MemoryUpdater()
    assert updater is not None
    print("[+] 记忆更新器初始化成功")


def main():
    print("=" * 50)
    print("LocalMind 写入引擎测试")
    print("=" * 50)
    
    test_imports()
    test_analyzer_init()
    test_analyzer_conversation()
    test_writer()
    test_updater()
    
    print("\n✅ 写入引擎测试完成！")


if __name__ == "__main__":
    main()
