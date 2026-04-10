#!/usr/bin/env python3
"""
LocalMind 分层唤醒功能测试 (Phase 4)
"""

import sys
import sqlite3
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from localmind.config import config
from localmind.db import Database
from localmind.layers import LayerManager, wake_up, LayerContext, WakeContext
from recall.engine import RecallEngine


def test_layer_context():
    """测试 LayerContext 基础功能"""
    print("[*] 测试 LayerContext...")
    
    ctx = LayerContext(layer_name="L0", content="用户名: Alice\n性格: 内向")
    assert ctx.layer_name == "L0"
    assert ctx.token_estimate > 0
    print(f"    Token 估算: {ctx.token_estimate}")
    print("[+] LayerContext 测试通过")


def test_wake_context():
    """测试 WakeContext 组合功能"""
    print("[*] 测试 WakeContext...")
    
    wake = WakeContext()
    wake.l0 = LayerContext("L0", "用户: Alice")
    wake.l1 = LayerContext("L1", "喜好: 设计、编程")
    
    prompt = wake.to_prompt()
    assert "身份认知" in prompt or "Alice" in prompt
    assert wake.total_tokens > 0
    assert wake.is_ready
    
    print(f"    总 tokens: {wake.total_tokens}")
    print(f"    Prompt 预览: {prompt[:100]}...")
    print("[+] WakeContext 测试通过")


def test_layer_manager_init():
    """测试 LayerManager 初始化"""
    print("[*] 测试 LayerManager 初始化...")
    
    db = Database()
    manager = LayerManager(db)
    
    assert manager.db is not None
    assert manager.L0_MAX_TOKENS == 50
    assert manager.L1_MAX_TOKENS == 120
    print("[+] LayerManager 初始化测试通过")


def test_layer_manager_wake_up():
    """测试分层唤醒功能"""
    print("[*] 测试分层唤醒...")
    
    engine = RecallEngine()
    
    # 测试空唤醒（无数据）
    wake_ctx = engine.wake_up("测试查询")
    
    # 即使没有数据，也应该返回 WakeContext
    assert isinstance(wake_ctx, WakeContext)
    print(f"    L0: {wake_ctx.l0.token_estimate if wake_ctx.l0 else 0} tokens")
    print(f"    L1: {wake_ctx.l1.token_estimate if wake_ctx.l1 else 0} tokens")
    print(f"    L2: {wake_ctx.l2.token_estimate if wake_ctx.l2 else 0} tokens")
    print("[+] 分层唤醒测试通过")


def test_layer_manager_stats():
    """测试分层统计"""
    print("[*] 测试分层统计...")
    
    manager = LayerManager()
    stats = manager.get_stats()
    
    assert "l0_max_tokens" in stats
    assert "l1_max_tokens" in stats
    assert "l2_max_tokens" in stats
    print(f"    统计: {stats}")
    print("[+] 分层统计测试通过")


def test_recall_engine_wake_up():
    """测试 RecallEngine 的分层唤醒集成"""
    print("[*] 测试 RecallEngine 分层唤醒...")
    
    engine = RecallEngine()
    
    # 测试 wake_up 方法
    wake_ctx = engine.wake_up("我想学设计")
    assert isinstance(wake_ctx, WakeContext)
    
    # 测试 recall_with_wake 方法
    wake_ctx, full_ctx = engine.recall_with_wake("我想学设计", "test_conv_001")
    assert isinstance(wake_ctx, WakeContext)
    assert full_ctx is not None
    
    print(f"    唤醒 tokens: {wake_ctx.total_tokens}")
    print(f"    完整召回维度: {len(full_ctx.recalled_results)}")
    print("[+] RecallEngine 分层唤醒测试通过")


def test_layered_prompt_building():
    """测试分层 prompt 构建"""
    print("[*] 测试分层 prompt 构建...")
    
    engine = RecallEngine()
    wake_ctx = engine.wake_up("测试")
    
    # 测试 build_layered_prompt
    prompt = engine.build_layered_prompt(wake_ctx, None)
    
    # 应该至少包含核心记忆部分（即使没有内容）
    print(f"    Prompt 长度: {len(prompt)}")
    print("[+] 分层 prompt 构建测试通过")


def test_global_wake_up():
    """测试全局 wake_up 快捷函数"""
    print("[*] 测试全局 wake_up 函数...")
    
    ctx = wake_up("测试查询")
    assert isinstance(ctx, WakeContext)
    print("[+] 全局 wake_up 函数测试通过")


def main():
    print("=" * 60)
    print("LocalMind Phase 4 分层唤醒功能测试")
    print("=" * 60)
    
    test_layer_context()
    test_wake_context()
    test_layer_manager_init()
    test_layer_manager_wake_up()
    test_layer_manager_stats()
    test_recall_engine_wake_up()
    test_layered_prompt_building()
    test_global_wake_up()
    
    print("\n" + "=" * 60)
    print("所有分层唤醒测试通过！")
    print("=" * 60)
    print("\n提示：要测试完整功能，请先运行:")
    print("  python scripts/init_db.py  # 确保数据库已初始化")
    print("  python scripts/setup_ollama.py  # 确保 Ollama 运行")


if __name__ == "__main__":
    main()
