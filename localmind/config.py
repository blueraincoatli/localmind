"""
LocalMind 配置管理
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


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
    
    # Ollama 配置
    ollama_base: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    
    # 召回参数
    recall_top_k: int = 5
    recall_alpha: float = 0.4   # rel_llm 权重
    recall_beta: float = 0.2    # hist 权重
    recall_gamma: float = 0.15  # pop 权重
    recall_delta: float = 0.15   # cooc 权重
    recall_lambda: float = 0.05 # fatigue 惩罚
    recall_mu: float = 0.05     # over_coverage 惩罚
    
    def __post_init__(self):
        """初始化路径"""
        self.data_dir = self.project_root / "data"
        self.db_path = self.data_dir / "personal.db"
        self.chroma_path = self.data_dir / "chroma_db"
        self.dimensions_dir = self.project_root / "dimensions"
    
    def ensure_dirs(self):
        """确保所有目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)


# 全局配置实例
config = Config()
