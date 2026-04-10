"""
记忆分析模块
使用 LLM 分析对话，提取结构化记忆记录
"""

import json
import logging
import re
import requests
from typing import Optional

from localmind.db import Database
from localmind.config import config
from localmind.models import MemoryRecord, WriteAnalysis
from localmind.prompts import build_memory_extraction_prompt

logger = logging.getLogger(__name__)


def llm_ollama(prompt: str, model: str) -> str:
    """调用本地 Ollama LLM"""
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
        logger.error(f"[MemoryAnalyzer] Ollama LLM 调用失败: {e}")
        return ""


def llm_deepseek(prompt: str, model: str) -> str:
    """调用 DeepSeek API"""
    api_key = config.deepseek_api_key
    if not api_key:
        logger.warning("[MemoryAnalyzer] DeepSeek API Key 未配置")
        return ""
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or config.deepseek_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"[MemoryAnalyzer] DeepSeek API 调用失败: {e}")
        return ""


def llm_generate(prompt: str, model: Optional[str] = None) -> str:
    """根据配置调用 LLM（Ollama 或 DeepSeek）"""
    provider = config.llm_provider
    
    if provider == "ollama":
        model = model or config.ollama_model
        return llm_ollama(prompt, model)
    elif provider == "deepseek":
        # DeepSeek 使用配置的模型，不接受外部传入的 Ollama 模型名
        return llm_deepseek(prompt, config.deepseek_model)
    else:
        logger.warning(f"[MemoryAnalyzer] 未知的 LLM provider: {provider}，使用 Ollama")
        return llm_ollama(prompt, model or config.ollama_model)


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
        # 如果没指定模型，根据 provider 使用各自默认值
        if model:
            self.model = model
        elif config.llm_provider == "deepseek":
            self.model = config.deepseek_model
        else:
            self.model = config.ollama_model
        self.db = Database()
        self._dimensions = self.db.get_all_dimensions()
        self._dimension_ids = {d.id for d in self._dimensions}

    def analyze(self, conversation: str, conversation_id: Optional[str] = None) -> WriteAnalysis:
        """
        分析对话，提取值得记忆的信息

        Args:
            conversation: 对话文本
            conversation_id: 可选的对话 ID，用于溯源

        Returns:
            WriteAnalysis 结果
        """
        prompt = build_memory_extraction_prompt(conversation, self._dimensions)

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
                dimension_id = self._normalize_dimension_id(
                    str(r.get("dimension_id", "")),
                    str(r.get("content", "")),
                )
                if not dimension_id:
                    logger.warning(f"[MemoryAnalyzer] 跳过无效维度: {r.get('dimension_id')}")
                    continue

                # 构建 evidence，溯源信息优先
                ev_parts = []
                if conversation_id:
                    ev_parts.append(f"conversation_id: {conversation_id}")
                orig_evidence = r.get("evidence")
                if orig_evidence:
                    ev_parts.append(orig_evidence)
                evidence = "\n".join(ev_parts) if ev_parts else None

                records.append(
                    MemoryRecord(
                        dimension_id=dimension_id,
                        content=r["content"],
                        evidence=evidence,
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

    def _normalize_dimension_id(self, raw_dimension_id: str, content: str) -> Optional[str]:
        """将 LLM 输出的维度 ID 归一化到已定义维度。"""
        dim_id = raw_dimension_id.strip().lower()
        if dim_id in self._dimension_ids:
            return dim_id

        content_lc = content.strip().lower()
        alias_map = {
            "personal_info.identity": "identity.basic_info",
            "personal_info.name": "identity.name",
            "personal_info.profile": "identity.basic_info",
            "preference.design": "aesthetics.design_style",
            "preference.design_style": "aesthetics.design_style",
            "preference.visual": "aesthetics.visual",
            "activity.learning": "goals.short_term",
            "interest.current_learning": "goals.short_term",
            "personality.traits": "identity.personality",
            "personality.social_preference": "identity.personality",
            "identity.profession": "career.profession",
        }
        if dim_id in alias_map:
            return alias_map[dim_id]

        if any(token in dim_id for token in ("name", "nickname")) or re.search(r"\b(i am|i'm|my name is)\b", content_lc):
            return "identity.name"
        if "profession" in dim_id or any(word in content_lc for word in ("设计师", "工程师", "产品经理", "designer", "developer")):
            return "career.profession"
        if "skill" in dim_id or any(word in content_lc for word in ("python", "编程", "设计", "写作", "工具")):
            return "career.skills"
        if "design" in dim_id or "aesthetic" in dim_id or any(word in content_lc for word in ("极简", "简约", "风格", "配色", "排版")):
            return "aesthetics.design_style"
        if "personality" in dim_id or any(word in content_lc for word in ("内向", "外向", "独处", "社交", "性格")):
            return "identity.personality"
        if "goal" in dim_id or "learning" in dim_id or any(word in content_lc for word in ("学习", "目标", "计划", "想要")):
            return "goals.short_term"

        return None
