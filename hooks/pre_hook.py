#!/usr/bin/env python3
"""
LocalMind Pre-Hook
对话前触发：召回相关记忆，生成注入上下文

OpenClaw 调用方式：
  pre_hook.py <conversation_id> <query>

输出：
  stdout: 注入上下文的 prompt 字符串（空则无输出）
  stderr: 日志（不影响主流程）
"""

import sys
import json
import logging
import os
from pathlib import Path

# 确保 localmind 在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from localmind.config import config
from localmind.db import Database
from localmind.models import ConversationContext
from recall import RecallEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [pre_hook] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main():
    try:
        # 解析参数
        if len(sys.argv) >= 3:
            conversation_id = sys.argv[1]
            query = sys.argv[2]
        else:
            # 兼容：从 stdin 读取
            conversation_id = "default"
            query = sys.stdin.read().strip()

        if not query:
            logger.info("空 query，跳过召回")
            return

        logger.info(f"召回开始: conversation_id={conversation_id}, query={query[:50]}...")

        # 执行召回
        engine = RecallEngine()
        ctx = engine.recall(
            query=query,
            conversation_id=conversation_id,
            top_k=config.recall_top_k,
        )

        # 构建注入 prompt
        injection = engine.build_injection_prompt(ctx)

        if injection:
            print(injection)
            logger.info(f"召回成功: {len(ctx.recalled_results)} 维度")
        else:
            logger.info("无相关记忆")

    except Exception as e:
        logger.error(f"Pre-hook 执行失败: {e}")
        # 不输出到 stdout，避免污染注入上下文
        sys.exit(0)  # graceful


if __name__ == "__main__":
    main()
