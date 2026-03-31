#!/usr/bin/env python3
"""
LocalMind Hook 测试
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import hooks.pre_hook
import hooks.post_hook
import hooks.config


def test_pre_hook_signature():
    print("[*] 测试 pre_hook 签名...")
    assert hasattr(hooks.pre_hook, 'main')
    print("[+] pre_hook.main 存在")


def test_post_hook_signature():
    print("[*] 测试 post_hook 签名...")
    assert hasattr(hooks.post_hook, 'main')
    print("[+] post_hook.main 存在")


def test_pre_hook_help():
    print("[*] 测试 pre_hook 帮助信息...")
    import subprocess
    result = subprocess.run(
        ["python3", "-c", "import hooks.pre_hook; help(hooks.pre_hook.main)"],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0
    print("[+] pre_hook 帮助信息正常")


def test_post_hook_help():
    print("[*] 测试 post_hook 帮助信息...")
    import subprocess
    result = subprocess.run(
        ["python3", "-c", "import hooks.post_hook; help(hooks.post_hook.main)"],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0
    print("[+] post_hook 帮助信息正常")


def main():
    print("=" * 50)
    print("LocalMind Hook 测试")
    print("=" * 50)
    
    test_pre_hook_signature()
    test_post_hook_signature()
    test_pre_hook_help()
    test_post_hook_help()
    
    print("\n✅ Hook 模块测试完成！")


if __name__ == "__main__":
    main()
