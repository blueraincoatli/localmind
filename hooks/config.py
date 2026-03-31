"""
LocalMind OpenClaw Hook 配置

Hook 约定格式说明：
- OpenClaw 支持 pre_hook / post_hook 脚本
- pre_hook: 对话前执行，输出会被注入为 system prompt
- post_hook: 对话后执行，接收对话内容
- 脚本通过 stdin/stdout 与 OpenClaw 通信
"""

from localmind.config import config

# Hook 配置
HOOK_CONFIG = {
    "enabled": True,
    # 召回配置
    "recall": {
        "top_k": 5,
        "include_gaps": True,
    },
    # 写入配置
    "write": {
        "enabled": True,
        "significance_threshold": 0.4,
    },
    # 上下文注入
    "injection": {
        "max_dimensions": 5,
        "max_records_per_dimension": 3,
        "prefix": "[相关记忆]",
    },
}

# 环境变量覆盖（支持通过环境变量配置）
import os


def get_hook_config() -> dict:
    """获取 hook 配置（支持环境变量覆盖）"""
    cfg = HOOK_CONFIG.copy()
    if os.getenv("LOCALMIND_HOOK_ENABLED"):
        cfg["enabled"] = os.getenv("LOCALMIND_HOOK_ENABLED") == "true"
    if os.getenv("LOCALMIND_RECALL_TOP_K"):
        cfg["recall"]["top_k"] = int(os.getenv("LOCALMIND_RECALL_TOP_K"))
    if os.getenv("LOCALMIND_WRITE_ENABLED"):
        cfg["write"]["enabled"] = os.getenv("LOCALMIND_WRITE_ENABLED") == "true"
    return cfg
