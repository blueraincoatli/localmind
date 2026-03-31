#!/usr/bin/env python3
"""
LocalMind 召回引擎测试
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from recall.engine import RecallEngine
from recall.semantic import SemanticRecall
from recall.history import HistoryRecall
from recall.popularity import PopularityRecall
from recall.cooccurrence import CooccurrenceRecall
from recall.gaps import GapsRecall


def test_imports():
    print("[*] 测试模块导入...")
    assert RecallEngine is not None
    assert SemanticRecall is not None
    assert HistoryRecall is not None
    assert PopularityRecall is not None
    assert CooccurrenceRecall is not None
    assert GapsRecall is not None
    print("[+] 所有召回模块导入成功")


def test_recall_engine_init():
    print("[*] 测试召回引擎初始化...")
    engine = RecallEngine()
    assert engine is not None
    assert engine.config is not None
    print("[+] 召回引擎初始化成功")


def test_recall_single_query():
    print("[*] 测试单次召回...")
    engine = RecallEngine()
    results = engine.recall("我想学习设计", conversation_id="test_001")
    assert isinstance(results, list)
    print(f"    召回结果数：{len(results)}")
    for r in results[:3]:
        print(f"    - {r.dimension_name}: score={r.score:.3f}")
    print("[+] 召回引擎单次测试通过")


def test_recall_multiple_queries():
    print("[*] 测试多次不同query...")
    queries = [
        "我最近在找工作",
        "我喜欢简约的设计风格",
        "今天晚上睡不着觉",
        "下周要交一个项目",
    ]
    for q in queries:
        engine = RecallEngine()
        results = engine.recall(q, conversation_id="test_002")
        print(f"  query: {q[:15]}... -> {len(results)} 个维度")


def main():
    print("=" * 50)
    print("LocalMind 召回引擎测试")
    print("=" * 50)
    
    test_imports()
    test_recall_engine_init()
    test_recall_single_query()
    test_recall_multiple_queries()
    
    print("\n✅ 召回引擎测试完成！")


if __name__ == "__main__":
    main()
