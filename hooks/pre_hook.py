#!/usr/bin/env python3
"""
LocalMind Pre-Hook (Phase 4)
对话前触发：分层唤醒 + 深度召回

OpenClaw 调用方式（通过 openclaw.json 配置）：
{
  "hooks": {
    "pre": {
      "enabled": true,
      "path": "/path/to/pre_hook.py",
      "args": ["--query", "{query}", "--conversation-id", "{conversation_id}"]
    }
  }
}

直接调用方式：
  python3 pre_hook.py --query "我想学设计" --conversation-id "conv_123"
  python3 pre_hook.py --query "我想学设计" --quick  # 仅分层唤醒，不深度召回

输出：
  stdout: 注入上下文的 prompt 字符串（空则无输出）
  stderr: 日志（不影响主流程）
"""

import sys
import argparse
import logging
from pathlib import Path

# 确保 localmind 在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from localmind.config import config
from recall.engine import RecallEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [pre_hook] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="LocalMind Pre-Hook - 分层唤醒 + 深度召回")
    parser.add_argument("--query", type=str, required=True, help="当前对话查询")
    parser.add_argument("--conversation-id", type=str, default="default", help="对话 ID")
    parser.add_argument("--quick", action="store_true", help="仅使用分层唤醒（更快）")
    args = parser.parse_args()

    query = args.query.strip()
    conversation_id = args.conversation_id

    if not query:
        logger.info("空 query，跳过召回")
        return

    logger.info(f"召回开始: conversation_id={conversation_id}, query={query[:50]}...")

    try:
        engine = RecallEngine()
        
        if args.quick:
            # 快速模式：仅分层唤醒（~200 tokens，<100ms）
            wake_ctx = engine.wake_up(query, conversation_id)
            injection = wake_ctx.to_prompt(include_l2=config.l2_enable)
            logger.info(f"快速唤醒: {wake_ctx.total_tokens} tokens")
        else:
            # 完整模式：分层唤醒 + 深度召回
            wake_ctx, full_ctx = engine.recall_with_wake(
                query=query,
                conversation_id=conversation_id,
                top_k=config.recall_top_k,
            )
            injection = engine.build_layered_prompt(wake_ctx, full_ctx)
            logger.info(
                f"分层+深度召回: wake={wake_ctx.total_tokens}t, "
                f"deep={len(full_ctx.recalled_results)}dims"
            )

        if injection and injection.strip():
            print(injection)
            logger.info(f"召回成功，注入 {len(injection)} 字符")
        else:
            logger.info("无相关记忆")
            print("")

    except Exception as e:
        logger.error(f"Pre-hook 执行失败: {e}")
        # 不输出到 stdout，避免污染注入上下文
        print("")


if __name__ == "__main__":
    main()
