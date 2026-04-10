"""
LocalMind 配置管理
"""

import os
from pathlib import Path
from dataclasses import dataclass, field


def _load_local_env(env_path: Path) -> None:
    """从项目根目录加载简单的 .env 文件，不覆盖已有环境变量。"""
    if not env_path.exists():
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or key in os.environ:
                continue

            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]

            os.environ[key] = value
    except OSError:
        # .env 读取失败时静默降级，避免影响主流程
        return


@dataclass
class Config:
    """LocalMind 配置"""
    
    # 项目根目录
    project_root: Path = Path(__file__).parent.parent
    
    # 数据目录
    data_dir: Path = field(init=False)
    
    # 数据库路径
    db_path: Path = field(init=False)
    
    # ChromaDB 路径
    chroma_path: Path = field(init=False)
    
    # 维度定义目录
    dimensions_dir: Path = field(init=False)
    
    # Embedding 模型（Ollama）
    embed_model: str = "bge-m3:latest"
    
    # LLM Provider: "ollama" 或 "deepseek"
    llm_provider: str = "deepseek"
    
    # Ollama 配置
    ollama_base: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    
    # DeepSeek 配置
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    
    # 召回参数
    recall_top_k: int = 5
    recall_alpha: float = 0.4   # rel_llm 权重
    recall_beta: float = 0.2    # hist 权重
    recall_gamma: float = 0.15  # pop 权重
    recall_delta: float = 0.15   # cooc 权重
    recall_lambda: float = 0.05 # fatigue 惩罚
    recall_mu: float = 0.05     # over_coverage 惩罚
    
    # 分层唤醒参数 (Phase 4)
    enable_layered_wake: bool = True  # 启用分层冷启动
    l0_max_tokens: int = 50           # Identity 层
    l1_max_tokens: int = 120          # Critical 层  
    l2_max_tokens: int = 500          # Contextual 层
    l2_enable: bool = True            # 是否启用 L2 按需加载
    
    # Verbatim 存储参数 (Phase 6)
    enable_verbatim_storage: bool = True  # 启用原始对话存储
    verbatim_collection: str = "localmind_verbatim"
    verbatim_max_snippets_per_conv: int = 20  # 每对话最大片段数
    
    def __post_init__(self):
        """初始化路径"""
        _load_local_env(self.project_root / ".env")

        data_dir_override = os.environ.get("LOCALMIND_DATA_DIR", "").strip()
        if data_dir_override:
            self.data_dir = Path(data_dir_override)
        else:
            self.data_dir = self.project_root / "data"
        self.db_path = self.data_dir / "personal.db"
        self.chroma_path = self.data_dir / "chroma_db"
        self.dimensions_dir = self.project_root / "dimensions"
        
        # 从环境变量读取配置
        self.embed_model = os.environ.get("LOCALMIND_EMBED_MODEL", self.embed_model)
        self.llm_provider = os.environ.get("LOCALMIND_LLM_PROVIDER", self.llm_provider)
        self.ollama_base = os.environ.get("LOCALMIND_OLLAMA_BASE", self.ollama_base)
        self.ollama_model = os.environ.get("LOCALMIND_OLLAMA_MODEL", self.ollama_model)
        self.deepseek_model = os.environ.get("LOCALMIND_DEEPSEEK_MODEL", self.deepseek_model)
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", self.deepseek_api_key)
    
    def ensure_dirs(self):
        """确保所有目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)


# 全局配置实例
config = Config()
