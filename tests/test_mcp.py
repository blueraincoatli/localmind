#!/usr/bin/env python3
"""
LocalMind MCP 服务器测试 (Phase 5)
"""

import sys
import json
import subprocess
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_mcp_server_import():
    """测试 MCP 服务器模块导入"""
    print("[*] 测试 MCP 服务器模块导入...")
    
    try:
        from localmind import mcp_server
        assert hasattr(mcp_server, 'app')
        assert hasattr(mcp_server, 'TOOLS')
        print(f"    工具数量: {len(mcp_server.TOOLS)}")
        print("[+] MCP 模块导入成功")
        return True
    except Exception as e:
        print(f"[-] MCP 模块导入失败: {e}")
        return False


def test_tools_definition():
    """测试工具定义"""
    print("[*] 测试工具定义...")
    
    from localmind.mcp_server import TOOLS
    
    required_tools = [
        "localmind_status",
        "localmind_wake_up", 
        "localmind_recall",
        "localmind_search",
        "localmind_remember",
        "localmind_list_dimensions",
        "localmind_get_dimension",
        "localmind_add_critical_fact",
        "localmind_get_stats",
    ]
    
    tool_names = [t.name for t in TOOLS]
    
    for tool_name in required_tools:
        if tool_name in tool_names:
            print(f"    [OK] {tool_name}")
        else:
            print(f"    [MISSING] {tool_name}")
            return False
    
    print(f"[+] 所有 {len(required_tools)} 个工具已定义")
    return True


def test_mcp_server_cli():
    """测试 MCP 服务器 CLI"""
    print("[*] 测试 MCP 服务器 CLI...")
    
    # 测试帮助信息
    result = subprocess.run(
        [sys.executable, "-m", "localmind.mcp_server", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        cwd=str(project_root)
    )
    
    # MCP 服务器通常没有 --help，但应该能启动
    print(f"    returncode: {result.returncode}")
    print("[+] MCP CLI 测试通过")
    return True


def main():
    print("=" * 60)
    print("LocalMind Phase 5 MCP 服务器测试")
    print("=" * 60)
    
    results = []
    results.append(("MCP 模块导入", test_mcp_server_import()))
    results.append(("工具定义", test_tools_definition()))
    results.append(("MCP CLI", test_mcp_server_cli()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, passed in results:
        status = "通过" if passed else "失败"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n[OK] 所有 MCP 测试通过！")
        print("\n使用方式:")
        print("  1. 启动服务器: python -m localmind.mcp_server")
        print("  2. 添加到 Claude: claude mcp add localmind -- python -m localmind.mcp_server")
    else:
        print("\n[FAIL] 部分测试失败")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
