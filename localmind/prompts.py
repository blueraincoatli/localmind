"""
LocalMind 提示词模板
定义 LLM 分析用的各类提示词
"""

# ========== 召回阶段 ==========

RECALL_ANALYSIS_PROMPT = """你是一个记忆分析专家。根据用户的当前对话，分析需要从哪些维度召回相关记忆。

当前对话：
{query}

可用维度：
{available_dimensions}

分析要求：
1. 判断当前对话涉及哪些维度（可能0-5个）
2. 对每个维度，给出召回理由
3. 输出格式：JSON数组，每个元素{{"dimension_id": "...", "reason": "..."}}

只输出JSON，不要其他内容。"""

RECALL_RANKING_PROMPT = """你是一个记忆排序专家。根据多路召回结果，对候选维度进行最终排序。

候选维度及其得分：
{candidate_info}

最终选取前 {top_k} 个维度。

输出格式：JSON数组，只包含维度ID列表，如：["dim1", "dim2", "dim3"]
只输出JSON。"""


# ========== 写入阶段 ==========

MEMORY_EXTRACTION_PROMPT = """你是一个记忆提取专家。分析对话内容，提取值得记忆的信息。

对话内容：
{conversation}

可用维度（必须严格从下面选择 dimension_id，不能自造新 ID）：
{available_dimensions}

分析要求：
1. 判断是否包含值得记录的信息（大部分对话不需要记录）
2. 如果有，提取结构化的记忆条目
3. 每个记忆条目包含：dimension_id, content, evidence, confidence

重要原则：
- 只记录对理解用户有价值的信息
- 重复的信息不要重复记录（检查是否已存在）
- 模糊/不确定的信息降低confidence
- 一句话能说清楚的不拆分成多条

输出格式：
{{
  "should_record": true/false,
  "reasoning": "分析理由",
  "confidence": 0.0-1.0,
  "records": [
    {{
      "dimension_id": "domain.subdimension",
      "content": "记忆内容（简洁）",
      "evidence": "来源对话摘要",
      "confidence": 0.0-1.0
    }}
  ]
}}

只输出JSON。"""

MEMORY_UPDATE_PROMPT = """分析以下对话，更新已有的用户记忆。

已有记忆：
{existing_memories}

新对话：
{conversation}

分析要求：
1. 判断是否需要更新/补充已有记忆
2. 判断是否与已有记忆矛盾
3. 如果有更新，返回更新后的内容

输出格式：
{{
  "action": "keep/update/conflict",
  "updated_records": [...] // 如果有更新
}}

只输出JSON。"""


# ========== 格式生成 ==========

FOCUS_PROMPT_TEMPLATE = """[{dimension_name}]
{focus_content}

（此信息来自你的记忆档案，供你参考）"""


# ========== 辅助函数 ==========

def build_recall_analysis_prompt(query: str, dimensions: list) -> str:
    """构建召回分析提示词"""
    dim_list = "\n".join([
        f"- {d.id}: {d.name}（{d.focus_prompt[:50]}...）"
        for d in dimensions
    ])
    return RECALL_ANALYSIS_PROMPT.format(
        query=query,
        available_dimensions=dim_list
    )


def build_memory_extraction_prompt(conversation: str, dimensions: list | None = None) -> str:
    """构建记忆提取提示词"""
    available_dimensions = "未提供维度列表"
    if dimensions:
        available_dimensions = "\n".join(
            f"- {d.id}: {d.name}"
            for d in dimensions
        )
    return MEMORY_EXTRACTION_PROMPT.format(
        conversation=conversation,
        available_dimensions=available_dimensions,
    )


def build_focus_prompt(dimension_name: str, content: str) -> str:
    """构建单个维度的 focus prompt"""
    return FOCUS_PROMPT_TEMPLATE.format(
        dimension_name=dimension_name,
        focus_content=content
    )
