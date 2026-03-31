"""
记忆更新模块
判断已有记忆是 keep / update / conflict
"""

import json
import logging
from typing import List, Optional

from localmind.config import config
from localmind.db import Database
from localmind.models import MemoryRecord, WriteAnalysis

logger = logging.getLogger(__name__)


class UpdateAction:
    """更新动作"""
    KEEP = "keep"
    UPDATE = "update"
    CONFLICT = "conflict"


def llm_generate(prompt: str, model: Optional[str] = None) -> str:
    """调用 Ollama LLM 生成文本"""
    import requests
    model = model or "qwen2.5:7b"
    try:
        response = requests.post(
            f"{config.ollama_base}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        logger.warning(f"[MemoryUpdater] LLM 调用失败: {e}")
        return ""


class MemoryUpdater:
    """
    记忆更新器 - 判断 keep / update / conflict
    """

    UPDATE_PROMPT_TEMPLATE = """分析以下对话，判断是否需要更新已有记忆。

已有记忆：
- 维度: {dimension_id}
- 内容: {existing_content}
- 置信度: {existing_confidence}

新对话：
{conversation}

分析要求：
1. 如果新对话只是确认/重复已有记忆 → keep
2. 如果新对话补充/深化了已有记忆 → update（返回更新后的内容）
3. 如果新对话与已有记忆矛盾 → conflict（返回冲突说明）

输出格式：
{{
  "action": "keep/update/conflict",
  "reasoning": "判断理由",
  "updated_content": "更新后的内容（仅 update 时需要）",
  "updated_confidence": 0.0-1.0
}}

只输出JSON。"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def analyze_update(
        self,
        existing_record,
        conversation: str,
        model: Optional[str] = None,
    ) -> dict:
        """
        分析单条已有记录是否需要更新

        Args:
            existing_record: 已有 Record 对象
            conversation: 新对话文本

        Returns:
            dict 含 action, reasoning, updated_content 等
        """
        prompt = self.UPDATE_PROMPT_TEMPLATE.format(
            dimension_id=existing_record.dimension_id,
            existing_content=existing_record.content,
            existing_confidence=existing_record.confidence,
            conversation=conversation,
        )

        text = llm_generate(prompt, model)
        if not text:
            return {
                "action": UpdateAction.KEEP,
                "reasoning": "LLM 调用失败，保守保留",
                "updated_content": None,
                "updated_confidence": existing_record.confidence,
            }

        text = text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            for part in parts[1:]:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part:
                    text = part
                    break

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"[MemoryUpdater] JSON 解析失败: {e}")
            return {
                "action": UpdateAction.KEEP,
                "reasoning": f"JSON 解析失败: {e}",
                "updated_content": None,
                "updated_confidence": existing_record.confidence,
            }

        return {
            "action": result.get("action", UpdateAction.KEEP),
            "reasoning": result.get("reasoning", ""),
            "updated_content": result.get("updated_content"),
            "updated_confidence": result.get("updated_confidence", existing_record.confidence),
        }

    def process_updates(
        self,
        analysis: WriteAnalysis,
        conversation: str,
        model: Optional[str] = None,
    ) -> dict:
        """
        处理所有待写入记录，判断 keep/update/conflict

        Args:
            analysis: WriteAnalysis 结果
            conversation: 新对话文本

        Returns:
            {
                "kept": [record_ids],
                "updated": [(record_id, new_content, new_confidence)],
                "conflicted": [(record_id, conflict_reason)],
                "new": [record_ids for new records],
            }
        """
        kept = []
        updated = []
        conflicted = []
        new = []

        for record in analysis.records:
            try:
                existing = self.db.get_records_by_dimension(record.dimension_id)
            except Exception as e:
                logger.warning(f"[MemoryUpdater] 查询已有记录失败 dim={record.dimension_id}: {e}")
                new.append(record.id)
                continue

            if not existing:
                # 新维度，直接写入
                new.append(record.id)
                continue

            # 已有记录，检查是否需要更新
            for ex in existing:
                result = self.analyze_update(ex, conversation, model)

                if result["action"] == UpdateAction.KEEP:
                    kept.append(ex.id)
                elif result["action"] == UpdateAction.UPDATE:
                    updated.append((
                        ex.id,
                        result["updated_content"],
                        result["updated_confidence"],
                    ))
                else:  # conflict
                    conflicted.append((ex.id, result["reasoning"]))

        return {
            "kept": kept,
            "updated": updated,
            "conflicted": conflicted,
            "new": new,
        }
