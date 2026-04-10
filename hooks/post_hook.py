#!/usr/bin/env python3
"""
LocalMind Post-Hook
对话后触发：分析对话并写入记忆

OpenClaw 调用方式（通过 openclaw.json 配置）：
{
  "hooks": {
    "post": {
      "enabled": true,
      "path": "/path/to/post_hook.py",
      "args": ["--conversation", "{conversation}", "--conversation-id", "{conversation_id}"]
    }
  }
}

直接调用方式：
  python3 post_hook.py --conversation "用户: 我想学设计\n助手: 好啊！" --conversation-id "conv_123"

输出：
  stdout: 状态摘要（不影响 OpenClaw 主流程）
  stderr: 日志
"""

import sys
import argparse
import logging
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from localmind.config import config
from localmind.db import Database
from write.analyzer import MemoryAnalyzer
from write.writer import MemoryWriter
from recall.cooccurrence import CooccurrenceRecall

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [post_hook] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="LocalMind Post-Hook - 写入对话记忆")
    parser.add_argument("--conversation", type=str, required=True,
                        help="完整对话文本（多轮，JSON字符串或纯文本）")
    parser.add_argument("--conversation-id", type=str, default="default",
                        help="对话 ID")
    args = parser.parse_args()

    conversation = args.conversation.strip()
    conversation_id = args.conversation_id

    if not conversation:
        logger.info("空对话，跳过写入")
        print("无需记录")
        return

    logger.info(f"写入分析开始: conv={conversation_id}, len={len(conversation)}")

    try:
        # 1. 分析对话
        analyzer = MemoryAnalyzer()
        analysis = analyzer.analyze(conversation)

        # 2. 写入记忆（结构化 + verbatim）
        writer = MemoryWriter()
        
        if analysis.is_significant():
            logger.info(f"分析结果: {len(analysis.records)} 条记录待写入")
            # Phase 6：同时写入结构化和 verbatim
            result = writer.write_analysis_with_verbatim(
                analysis=analysis,
                conversation=conversation,
                conversation_id=conversation_id
            )
            structured_count = len(result["structured_ids"])
            verbatim_count = len(result["verbatim_ids"])
            logger.info(f"写入完成: structured={structured_count}, verbatim={verbatim_count}")
            written_ids = result["structured_ids"]
        else:
            # 分析不显著，但仍存储 verbatim 作为 fallback
            logger.info(f"分析不显著，仅存储 verbatim: confidence={analysis.confidence}")
            verbatim_ids = writer.write_verbatim(conversation, conversation_id=conversation_id)
            written_ids = []
            logger.info(f"Verbatim 存储: {len(verbatim_ids)} 个片段")

        # 3. 更新共现关系
        if written_ids:
            try:
                dim_ids = list(set(r.dimension_id for r in analysis.records))
                cooc = CooccurrenceRecall()
                cooc.update_cooccurrence(dim_ids)
                logger.info(f"共现关系更新: {dim_ids}")
            except Exception as e:
                logger.warning(f"共现关系更新失败: {e}")

        # 4. 记录对话历史
        try:
            db = Database()
            db.add_conversation_history(
                conversation_id=conversation_id,
                query=conversation[:200],  # 截断存储
                recalled_dimensions=[r.dimension_id for r in analysis.records],
            )
        except Exception as e:
            logger.warning(f"对话历史记录失败: {e}")

        print(f"写入 {len(written_ids)} 条记忆")
        logger.info(f"Post-hook 完成: {len(written_ids)} 条记录写入")

    except Exception as e:
        logger.error(f"Post-hook 执行失败: {e}")
        print("写入失败")
        # graceful exit - 不影响主流程
        print("")


if __name__ == "__main__":
    main()
