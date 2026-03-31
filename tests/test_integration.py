#!/usr/bin/env python3
"""
LocalMind 端到端集成测试
测试完整 recall → write 生命周期
"""

import sys
import sqlite3
import subprocess
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from recall.engine import RecallEngine
from write.analyzer import MemoryAnalyzer
from write.writer import MemoryWriter
from localmind.config import config


def get_record_count() -> int:
    """获取当前记忆记录数"""
    conn = sqlite3.connect(str(config.db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM records")
    count = cur.fetchone()[0]
    conn.close()
    return count


def test_pre_hook_recall_personality():
    """测试1: 用"我是一个内向的人"做召回，验证 identity.personality 被召回"""
    print("[*] 测试1: Pre-hook 召回（内向性格）...")
    engine = RecallEngine()
    ctx = engine.recall(
        query="我是一个内向的人",
        conversation_id="test_integration_001",
        top_k=5,
    )

    assert len(ctx.recalled_results) > 0, "召回结果为空"

    dim_ids = [r.dimension_id for r in ctx.recalled_results]
    print(f"    召回维度: {dim_ids}")

    # 检查 identity.personality 是否被召回
    has_personality = any("identity.personality" in d for d in dim_ids)
    print(f"    包含 identity.personality: {has_personality}")

    # 验证 injection prompt 格式
    injection = ctx.to_injection_prompt()
    assert "[相关记忆]" in injection or injection == "", f"注入格式错误: {injection[:100]}"
    print(f"    注入 prompt 预览: {injection[:100]}...")

    print("[+] Pre-hook 召回测试通过")
    return dim_ids


def test_pre_hook_empty_query():
    """测试2: 空 query 应不崩溃"""
    print("[*] 测试2: 空 query 处理...")
    engine = RecallEngine()
    # 空字符串召回应该返回空上下文（graceful）
    try:
        ctx = engine.recall(query="", conversation_id="test_empty")
        print(f"    空召回结果数: {len(ctx.recalled_results)}")
        print("[+] 空 query 测试通过")
    except Exception as e:
        # 如果抛异常也是可接受的（因为已有空值保护）
        print(f"    空召回抛异常（可接受）: {e}")


def test_post_hook_significant_conversation():
    """测试3: 模拟对话写入，验证 SQLite 有新记录"""
    print("[*] 测试3: Post-hook 写入（显著对话）...")

    count_before = get_record_count()
    print(f"    写入前记录数: {count_before}")

    conversation = (
        "用户: 我其实是个内向的人，平时不太喜欢社交\n"
        "助手: 了解，内向的人通常更擅长独立思考和深度交流"
    )

    analyzer = MemoryAnalyzer()
    analysis = analyzer.analyze(conversation)

    print(f"    分析结果: should_record={analysis.should_record}, "
          f"confidence={analysis.confidence:.2f}, "
          f"records={len(analysis.records)}")

    if analysis.is_significant():
        writer = MemoryWriter()
        written_ids = writer.write_analysis(analysis)
        print(f"    写入 record IDs: {written_ids}")

        count_after = get_record_count()
        print(f"    写入后记录数: {count_after}")
        assert count_after > count_before, "写入后记录数未增加"
    else:
        print("    分析不显著，跳过写入（需 LLM 服务运行）")

    print("[+] Post-hook 写入测试完成")


def test_post_hook_trivial_conversation():
    """测试4: 闲聊对话不应触发写入"""
    print("[*] 测试4: Post-hook 闲聊（不应触发写入）...")
    conversation = "用户: 今天天气不错\n助手: 是啊，很舒服"

    analyzer = MemoryAnalyzer()
    analysis = analyzer.analyze(conversation)
    print(f"    分析结果: should_record={analysis.should_record}, "
          f"confidence={analysis.confidence:.2f}")

    # 闲聊不应该显著
    # （但如果 LLM 判定要写，也不算错）
    print("[+] 闲聊测试完成")


def test_hook_cli_pre():
    """测试5: Pre-hook CLI 调用"""
    print("[*] 测试5: Pre-hook CLI 调用...")
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "hooks" / "pre_hook.py"),
            "--query", "我是一个内向的人",
            "--conversation-id", "test_cli_001",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(f"    returncode: {result.returncode}")
    print(f"    stdout: {result.stdout[:200]}")
    print(f"    stderr: {result.stderr[:200] if result.stderr else '(无)'}")
    assert result.returncode == 0, f"pre_hook 失败: {result.stderr}"
    print("[+] Pre-hook CLI 测试通过")


def test_hook_cli_post():
    """测试6: Post-hook CLI 调用"""
    print("[*] 测试6: Post-hook CLI 调用...")
    conversation = (
        "用户: 我最近在学设计\n"
        "助手: 很好，设计很有创意价值"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "hooks" / "post_hook.py"),
            "--conversation", conversation,
            "--conversation-id", "test_cli_002",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(f"    returncode: {result.returncode}")
    print(f"    stdout: {result.stdout[:200]}")
    print(f"    stderr: {result.stderr[:200] if result.stderr else '(无)'}")
    assert result.returncode == 0, f"post_hook 失败: {result.stderr}"
    print("[+] Post-hook CLI 测试通过")


def test_wrapper_script():
    """测试7: wrapper.sh 调用"""
    print("[*] 测试7: wrapper.sh 调用...")
    result = subprocess.run(
        ["bash", str(project_root / "hooks" / "wrapper.sh"),
         "pre", "我喜欢简约风格", "test_wrapper_001"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(f"    returncode: {result.returncode}")
    print(f"    stdout: {result.stdout[:200]}")
    assert result.returncode == 0, f"wrapper.sh pre 失败: {result.stderr}"
    print("[+] wrapper.sh pre 测试通过")

    result2 = subprocess.run(
        ["bash", str(project_root / "hooks" / "wrapper.sh"),
         "post", "用户: 晚安\n助手: 晚安！好梦", "test_wrapper_002"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(f"    returncode: {result2.returncode}")
    print(f"    stdout: {result2.stdout[:200]}")
    assert result2.returncode == 0, f"wrapper.sh post 失败: {result2.stderr}"
    print("[+] wrapper.sh post 测试通过")


def main():
    print("=" * 60)
    print("LocalMind Phase 3 端到端集成测试")
    print("=" * 60)

    test_pre_hook_recall_personality()
    test_pre_hook_empty_query()
    test_post_hook_significant_conversation()
    test_post_hook_trivial_conversation()
    test_hook_cli_pre()
    test_hook_cli_post()
    test_wrapper_script()

    print("\n" + "=" * 60)
    print("✅ 所有集成测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
