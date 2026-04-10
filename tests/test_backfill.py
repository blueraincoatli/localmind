#!/usr/bin/env python3
"""
LocalMind 历史回填脚本测试
"""

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backfill_memories import (
    load_conversations_from_path,
    render_messages,
)


def test_render_messages():
    print("[*] 测试消息渲染...")
    text = render_messages(
        [
            {"role": "user", "content": "我叫 Alice"},
            {"role": "assistant", "content": "你好 Alice"},
            {"role": "user", "content": "我喜欢设计"},
        ]
    )
    assert "用户: 我叫 Alice" in text
    assert "助手: 你好 Alice" in text
    print("[+] 消息渲染测试通过")


def test_load_json_conversations():
    print("[*] 测试 JSON 对话加载...")
    tmpdir = PROJECT_ROOT / "temp_test_backfill"
    tmpdir.mkdir(exist_ok=True)
    try:
        path = tmpdir / "history.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "conversation_id": "conv_001",
                        "messages": [
                            {"role": "user", "content": "我是一名设计师"},
                            {"role": "assistant", "content": "了解"},
                        ],
                    },
                    {
                        "conversation": "用户: 我喜欢极简风格\n助手: 收到",
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        items = load_conversations_from_path(path)
        assert len(items) == 2
        assert items[0].conversation_id == "conv_001"
        assert "用户: 我是一名设计师" in items[0].conversation
        assert items[1].conversation_id == "history-2"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("[+] JSON 对话加载测试通过")


def test_load_plain_text_conversation():
    print("[*] 测试纯文本对话加载...")
    tmpdir = PROJECT_ROOT / "temp_test_backfill"
    tmpdir.mkdir(exist_ok=True)
    try:
        path = tmpdir / "chat.txt"
        path.write_text("用户: 我最近在学 Python", encoding="utf-8")

        items = load_conversations_from_path(path)
        assert len(items) == 1
        assert items[0].conversation_id == "chat"
        assert items[0].conversation == "用户: 我最近在学 Python"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("[+] 纯文本对话加载测试通过")


def main():
    print("=" * 60)
    print("LocalMind 历史回填脚本测试")
    print("=" * 60)
    test_render_messages()
    test_load_json_conversations()
    test_load_plain_text_conversation()
    print("\n[OK] 所有回填脚本测试通过")


if __name__ == "__main__":
    main()
