#!/usr/bin/env python3
"""
LocalMind Pre-Hook
对话前触发：召回相关记忆，生成注入上下文

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
    parser = argparse.ArgumentParser(description="LocalMind Pre-Hook - 召回相关记忆")
    parser.add_argument("--query", type=str, required=True, help="当前对话查询")
    parser.add_argument("--conversation-id", type=str, default="default", help="对话 ID")
    args = parser.parse_args()

    query = args.query.strip()
    conversation_id = args.conversation_id

    if not query:
        logger.info("空 query，跳过召回")
        return

    logger.info(f"召回开始: conversation_id={conversation_id}, query={query[:50]}...")

    try:
        # 执行召回
        engine = RecallEngine()
        ctx = engine.recall(
            query=query,
            conversation_id=conversation_id,
            top_k=config.recall_top_k,
        )

        # 构建注入 prompt
        injection = ctx.to_injection_prompt()

        if injection and injection.strip() not in ("", "[相关记忆]", "[相关记忆]\n", "[相关记忆]\n\n"):
            print(injection)
            logger.info(f"召回成功: {len(ctx.recalled_results)} 维度")
        else:
            logger.info("无相关记忆")
            # 输出空，不注入无用内容
            print("")

    except Exception as e:
        logger.error(f"Pre-hook 执行失败: {e}")
        # 不输出到 stdout，避免污染注入上下文
        print("")


if __name__ == "__main__":
    main()
