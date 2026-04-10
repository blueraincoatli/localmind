#!/usr/bin/env python3
"""
LocalMind Verbatim 原始对话存储测试 (Phase 6)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from localmind.verbatim_store import (
    VerbatimStore, VerbatimSnippet, 
    store_conversation, search_verbatim
)


class BrokenVectorStore:
    """模拟 embedding / Chroma 不可用。"""

    def _get_client(self):
        raise RuntimeError("chroma unavailable")

    def _generate_embedding(self, text: str):
        raise RuntimeError("embedding unavailable")


def test_verbatim_snippet():
    """测试 VerbatimSnippet 数据类"""
    print("[*] 测试 VerbatimSnippet...")
    
    snippet = VerbatimSnippet(
        content="我是一个内向的人，喜欢设计",
        source="test_conv_001",
        speaker="user",
        turn_index=0,
        keywords=["内向", "设计"],
        domain_hints=["identity", "psychology"]
    )
    
    assert snippet.is_user_speech
    assert len(snippet.keywords) == 2
    print(f"    片段: {snippet.content[:30]}...")
    print(f"    关键词: {snippet.keywords}")
    print("[+] VerbatimSnippet 测试通过")


def test_keyword_extraction():
    """测试关键词提取"""
    print("[*] 测试关键词提取...")
    
    store = VerbatimStore()
    
    text = "我今年28岁，是一名设计师，喜欢简约风格"
    keywords = store._extract_keywords(text)
    
    print(f"    文本: {text}")
    print(f"    提取关键词: {keywords}")
    
    # 应该提取到年龄和职业相关信息
    assert len(keywords) > 0
    print("[+] 关键词提取测试通过")


def test_domain_inference():
    """测试域推断"""
    print("[*] 测试域推断...")
    
    store = VerbatimStore()
    
    test_cases = [
        ("我叫Alice，是一名设计师", ["identity", "career"]),
        ("我觉得压力很大", ["psychology"]),
        ("我想学习编程", ["goals"]),
        ("我的朋友很少", ["relations"]),
    ]
    
    for text, expected in test_cases:
        domains = store._infer_domains(text)
        print(f"    '{text[:20]}...' -> {domains}")
        # 至少匹配一个预期域
        assert any(d in domains for d in expected) or not expected
    
    print("[+] 域推断测试通过")


def test_conversation_splitting():
    """测试对话分割"""
    print("[*] 测试对话分割...")
    
    store = VerbatimStore()
    
    conversation = """
用户: 我是一个内向的人
助手: 了解，内向的人通常更擅长深度思考
用户: 是的，我喜欢独处
助手: 独处是很好的充电方式
"""
    
    snippets = store._split_conversation(conversation, "test_001")
    
    print(f"    分割出 {len(snippets)} 个片段")
    for i, s in enumerate(snippets[:3]):
        print(f"    {i+1}. [{s.speaker}] {s.content[:40]}...")
    
    assert len(snippets) > 0
    print("[+] 对话分割测试通过")


def test_verbatim_store_init():
    """测试 VerbatimStore 初始化"""
    print("[*] 测试 VerbatimStore 初始化...")
    
    store = VerbatimStore()
    assert store.COLLECTION_NAME == "localmind_verbatim"
    print("[+] VerbatimStore 初始化测试通过")


def test_store_and_search():
    """测试存储和搜索"""
    print("[*] 测试 verbatim 存储和搜索...")
    
    store = VerbatimStore()
    
    # 存储对话
    conversation = "用户: 我是一个内向的设计师，喜欢简约风格"
    ids = store.store_conversation(conversation, "test_search")
    
    print(f"    存储了 {len(ids)} 个片段")
    
    # 搜索
    if ids:
        results = store.search("性格内向", n_results=3)
        print(f"    搜索返回 {len(results)} 条结果")
        for r in results[:2]:
            print(f"    - {r['content'][:50]}... (相似度: {r['similarity']:.3f})")
    
    print("[+] 存储和搜索测试通过")


def test_global_functions():
    """测试全局快捷函数"""
    print("[*] 测试全局快捷函数...")
    
    # store_conversation
    ids = store_conversation("用户: 我喜欢编程和阅读", "test_global")
    print(f"    store_conversation: {len(ids)} 个片段")
    
    # search_verbatim (可能因 Ollama 不可用而失败)
    try:
        results = search_verbatim("兴趣爱好", n_results=3)
        print(f"    search_verbatim: {len(results)} 条结果")
    except Exception as e:
        print(f"    search_verbatim: 跳过 (Ollama 不可用: {type(e).__name__})")
    
    print("[+] 全局快捷函数测试通过")


def test_sqlite_fallback_store_and_search():
    """测试 SQLite fallback 存储和搜索"""
    print("[*] 测试 SQLite fallback verbatim...")

    store = VerbatimStore(vector_store=BrokenVectorStore())
    deleted = store.delete_by_source("test_sqlite_fallback")
    assert deleted >= 0

    ids = store.store_conversation(
        "用户: 我喜欢简约风格，也在学习 Python",
        "test_sqlite_fallback",
    )
    print(f"    fallback 存储: {len(ids)} 个片段")
    assert len(ids) > 0
    assert all(str(i).startswith("sqlite-") for i in ids)

    results = store.search("简约风格", n_results=3)
    print(f"    fallback 搜索: {len(results)} 条结果")
    assert len(results) > 0
    assert "简约风格" in results[0]["content"]
    print("[+] SQLite fallback 测试通过")


def main():
    print("=" * 60)
    print("LocalMind Phase 6 Verbatim 功能测试")
    print("=" * 60)
    
    try:
        test_verbatim_snippet()
        test_keyword_extraction()
        test_domain_inference()
        test_conversation_splitting()
        test_verbatim_store_init()
        test_store_and_search()
        test_global_functions()
        test_sqlite_fallback_store_and_search()
        
        print("\n" + "=" * 60)
        print("所有 Verbatim 测试通过！")
        print("=" * 60)
        print("\nPhase 6 功能:")
        print("  - 原始对话存储 (verbatim)")
        print("  - 关键词提取 (无 LLM)")
        print("  - 域推断 (规则-based)")
        print("  - 语义搜索 fallback")
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
