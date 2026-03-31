"""
记忆分析模块
使用 LLM 分析对话，提取结构化记忆记录
"""

import json
import logging
import requests
from typing import Optional

from localmind.config import config
from localmind.models import MemoryRecord, WriteAnalysis
from localmind.prompts import build_memory_extraction_prompt

logger = logging.getLogger(__name__)


def llm_generate(prompt: str, model: Optional[str] = None) -> str:
    """调用 Ollama LLM 生成文本"""
    model = model or "qwen2.5:7b"
    try:
        response = requests.post(
            f"{config.ollama_base}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        logger.warning("[MemoryAnalyzer] Ollama 连接失败（服务可能未启动）")
        return ""
    except Exception as e:
        logger.error(f"[MemoryAnalyzer] LLM 生成失败: {e}")
        return ""


def llm_json(prompt: str, model: Optional[str] = None) -> dict:
    """调用 Ollama LLM 并解析 JSON 响应"""
    text = llm_generate(prompt, model)
    if not text:
        return {"should_record": False, "reasoning": "LLM 调用失败", "confidence": 0.0, "records": []}

    text = text.strip()

    # 去掉 markdown JSON 包装
    if text.startswith("```"):
        parts = text.split("```")
        for part in parts[1:]:  # 跳过第一部分（可能为空）
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part:
                text = part
                break

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"[MemoryAnalyzer] JSON 解析失败: {e}, 原始: {text[:200]}")
        return {"should_record": False, "reasoning": f"JSON 解析失败: {e}", "confidence": 0.0, "records": []}


class MemoryAnalyzer:
    """
    记忆分析器 - 用 LLM 从对话中提取结构化记忆
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or "qwen2.5:7b"

    def analyze(self, conversation: str) -> WriteAnalysis:
        """
        分析对话，提取值得记忆的信息

        Args:
            conversation: 对话文本

        Returns:
            WriteAnalysis 结果
        """
        prompt = build_memory_extraction_prompt(conversation)

        try:
            result = llm_json(prompt, model=self.model)
        except Exception as e:
            logger.error(f"[MemoryAnalyzer] 分析失败: {e}")
            return WriteAnalysis(
                should_record=False,
                records=[],
                reasoning=f"分析异常: {e}",
                confidence=0.0,
            )

        should_record = result.get("should_record", False)
        reasoning = result.get("reasoning", "")
        confidence = result.get("confidence", 0.0)

        records = []
        for r in result.get("records", []):
            try:
                records.append(
                    MemoryRecord(
                        dimension_id=r["dimension_id"],
                        content=r["content"],
                        evidence=r.get("evidence"),
                        confidence=r.get("confidence", confidence),
                    )
                )
            except (KeyError, TypeError) as e:
                logger.warning(f"[MemoryAnalyzer] 解析记录失败: {r}, 错误: {e}")

        return WriteAnalysis(
            should_record=should_record,
            records=records,
            reasoning=reasoning,
            confidence=confidence,
        )

    def is_significant(self, analysis: WriteAnalysis) -> bool:
        """判断分析结果是否显著值得记录"""
        return analysis.is_significant()
