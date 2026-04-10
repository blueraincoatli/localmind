#!/usr/bin/env python3
"""
LocalMind 降级召回与维度归一化测试
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from recall.semantic import SemanticRecall
from write.analyzer import MemoryAnalyzer


def test_dimension_normalization():
    print("[*] 测试维度归一化...")
    analyzer = MemoryAnalyzer.__new__(MemoryAnalyzer)
    analyzer._dimension_ids = {
        "identity.name",
        "identity.basic_info",
        "identity.personality",
        "career.profession",
        "career.skills",
        "aesthetics.design_style",
        "goals.short_term",
    }

    assert analyzer._normalize_dimension_id("personal_info.identity", "Alice 是设计师") == "identity.basic_info"
    assert analyzer._normalize_dimension_id("personality.traits", "我是内向的人") == "identity.personality"
    assert analyzer._normalize_dimension_id("activity.learning", "我在学习 Python") == "goals.short_term"
    print("[+] 维度归一化测试通过")


def test_lexical_similarity():
    print("[*] 测试词面相似度...")
    semantic = SemanticRecall.__new__(SemanticRecall)

    high = semantic._lexical_similarity("用户喜欢什么风格", "用户喜欢简约风格的设计")
    low = semantic._lexical_similarity("用户喜欢什么风格", "今天晚上吃了米饭")

    assert high > low
    assert high > 0
    print(f"    high={high:.3f}, low={low:.3f}")
    print("[+] 词面相似度测试通过")


def main():
    print("=" * 60)
    print("LocalMind 降级能力测试")
    print("=" * 60)
    test_dimension_normalization()
    test_lexical_similarity()
    print("\n[OK] 所有降级能力测试通过")


if __name__ == "__main__":
    main()
