#!/usr/bin/env python3
"""
LocalMind Post-Hook
对话后触发：分析对话并写入记忆

OpenClaw 调用方式：
  post_hook.py <conversation_id> <query> <response>

输出：
  stdout: 状态 JSON（不影响 OpenClaw 主流程）
  stderr: 日志
"""

import sys
import json
import logging
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from localmind.config import config
from localmind.db import Database
from write import MemoryAnalyzer, MemoryWriter, MemoryUpdater
from recall import CooccurrenceRecall

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [post_hook] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main():
    try:
        # 解析参数
        if len(sys.argv) >= 4:
            conversation_id = sys.argv[1]
            query = sys.argv[2]
            response = sys.argv[3]
        else:
            conversation_id = "default"
            query = ""
            response = ""

        if not query and not response:
            logger.info("空对话，跳过写入")
            print(json.dumps({"status": "skipped", "reason": "empty"}))
            return

        conversation = f"用户: {query}\n助手: {response}"
        logger.info(f"写入分析开始: conv={conversation_id}, len={len(conversation)}")

        # 1. 分析对话
        analyzer = MemoryAnalyzer()
        analysis = analyzer.analyze(conversation)

        if not analyzer.is_significant(analysis):
            logger.info(f"分析不显著，跳过写入: confidence={analysis.confidence}")
            print(json.dumps({
                "status": "skipped",
                "reason": "not_significant",
                "confidence": analysis.confidence,
            }))
            return

        logger.info(f"分析结果: {len(analysis.records)} 条记录待写入")

        # 2. 写入记忆
        writer = MemoryWriter()
        written_ids = writer.write_analysis(analysis)
        logger.info(f"写入完成: {len(written_ids)} 条")

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
                query=query,
                recalled_dimensions=[r.dimension_id for r in analysis.records],
            )
        except Exception as e:
            logger.warning(f"对话历史记录失败: {e}")

        print(json.dumps({
            "status": "ok",
            "records_written": len(written_ids),
            "record_ids": written_ids,
        }))

    except Exception as e:
        logger.error(f"Post-hook 执行失败: {e}")
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(0)


if __name__ == "__main__":
    main()
