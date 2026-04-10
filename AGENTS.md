# LocalMind - AGENTS.md

## 项目概述

LocalMind 是一个**完全本地化的结构化 AI 记忆系统**，基于 HeyCube 思路复刻，为 OpenClaw 等 AI 应用提供智能记忆能力。

### 核心特性

- **完全本地化** - 不依赖任何第三方 API（除 Ollama 外），所有数据存储在本地
- **结构化存储** - 8 大域分类，55 个维度，SQLite + ChromaDB 双存储
- **语义召回** - 基于向量的精准语义搜索（使用 Ollama + nomic-embed-text）
- **多路召回** - 语义 + 历史 + 热度 + 共现 + 空白检测 5 路召回
- **自动进化** - 记忆越用越准，支持 LLM 分析提取（Ollama 或 DeepSeek）

### 8 大域分类

| 域 | 维度数 | 说明 |
|----|--------|------|
| identity (身份认知) | 6 | 姓名、性格、自我认知等 |
| psychology (心理结构) | 7 | 思维方式、决策风格、情绪模式等 |
| aesthetic (审美偏好) | 7 | 视觉、音乐、设计品味等 |
| career (职业画像) | 7 | 技能树、工作风格、行业背景等 |
| goals (计划目标) | 6 | 短期/长期目标、项目计划等 |
| schedule (日程节奏) | 6 | 作息、能量曲线、高效时段等 |
| misc (杂项偏好) | 8 | 饮食、运动、爱好、宠物等 |
| relations (关系网络) | 8 | 家人、朋友、同事、社交风格等 |

---

## 技术栈

| 组件 | 技术选型 | 版本要求 |
|------|----------|----------|
| 语言 | Python | >= 3.10 |
| 结构化数据库 | SQLite | 3.x |
| 向量数据库 | ChromaDB | >= 0.4.x |
| Embedding | Ollama + nomic-embed-text/bge-m3 | 最新 |
| LLM | Ollama (本地) 或 DeepSeek API | 可选 |

### 依赖安装

```bash
# Python 依赖
pip install chromadb requests pyyaml

# Ollama 安装
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull nomic-embed-text  # 或 bge-m3:latest
ollama pull qwen2.5:7b        # 或其他 LLM（如使用本地 LLM）
```

---

## 项目结构

```
localmind/
├── localmind/              # 核心代码包
│   ├── __init__.py
│   ├── config.py           # 配置管理（含全局 config 实例）
│   ├── db.py               # SQLite 操作（Database 类）
│   ├── models.py           # 数据模型（Record, RecallResult 等）
│   ├── prompts.py          # LLM 提示词模板
│   └── vector_store.py     # ChromaDB 封装（VectorStore 类）
│
├── recall/                 # 召回引擎
│   ├── __init__.py
│   ├── engine.py           # 召回引擎主入口（RecallEngine 类）
│   ├── semantic.py         # 语义召回（SemanticRecall）
│   ├── history.py          # 历史召回
│   ├── popularity.py       # 热度召回
│   ├── cooccurrence.py     # 共现召回
│   ├── gaps.py             # 空白检测
│   └── ranker.py           # 排序器（RecallRanker，HeyCube 公式）
│
├── write/                  # 写入引擎
│   ├── __init__.py
│   ├── analyzer.py         # LLM 分析提取（MemoryAnalyzer）
│   ├── writer.py           # 双重写入（MemoryWriter）
│   └── updater.py          # 记忆更新
│
├── hooks/                  # OpenClaw Hook 集成
│   ├── pre_hook.py         # Pre-hook：召回记忆
│   ├── post_hook.py        # Post-hook：写入记忆
│   ├── config.py           # Hook 配置
│   └── wrapper.sh          # Bash 包装脚本
│
├── dimensions/             # 8 大域 YAML 定义
│   ├── identity.yaml
│   ├── psychology.yaml
│   ├── aesthetics.yaml
│   ├── career.yaml
│   ├── goals.yaml
│   ├── schedule.yaml
│   ├── misc.yaml
│   └── relations.yaml
│
├── scripts/                # 初始化脚本
│   ├── init_db.py          # SQLite schema 初始化
│   ├── setup_ollama.py     # Ollama 环境检查
│   └── setup_chromadb.py   # ChromaDB 初始化
│
├── tests/                  # 测试文件
│   ├── test_db.py          # 数据库测试
│   ├── test_dimensions.py  # 维度定义测试
│   ├── test_ollama.py      # Ollama 测试
│   ├── test_chromadb.py    # ChromaDB 测试
│   ├── test_recall.py      # 召回引擎测试
│   ├── test_write.py       # 写入引擎测试
│   ├── test_hooks.py       # Hook 测试
│   └── test_integration.py # 端到端集成测试
│
├── data/                   # 数据存储（gitignore）
│   ├── personal.db         # SQLite 数据库
│   └── chroma_db/          # ChromaDB 向量库
│
├── README.md               # 项目说明
├── SPEC.md                 # 详细规格文档
├── PLANNING.md             # 规划文档
└── AGENTS.md               # 本文件
```

---

## 数据库 Schema

### dimensions 表 - 维度定义

```sql
CREATE TABLE dimensions (
    id TEXT PRIMARY KEY,          -- 如 identity.personality
    domain TEXT NOT NULL,         -- 如 identity
    domain_name TEXT NOT NULL,    -- 如 身份认知
    name TEXT NOT NULL,           -- 如 性格特点
    focus_prompt TEXT NOT NULL,   -- 召回焦点提示词
    created_at INTEGER
);
```

### records 表 - 记忆记录

```sql
CREATE TABLE records (
    id TEXT PRIMARY KEY,          -- UUID
    dimension_id TEXT NOT NULL,   -- 关联维度
    content TEXT NOT NULL,        -- 记忆内容
    evidence TEXT,                -- 证据/来源
    confidence REAL DEFAULT 0.5,  -- 置信度 0-1
    created_at INTEGER,
    last_used_at INTEGER,         -- 最后使用时间
    use_count INTEGER DEFAULT 0   -- 使用次数
);
```

### 辅助表

- **record_vectors** - 向量映射（SQLite 与 ChromaDB 同步）
- **cooccurrence** - 维度共现关系
- **conversation_history** - 对话历史记录

---

## 初始化流程

### 1. 数据库初始化

```bash
# 创建 SQLite schema，加载 55 个维度定义
python scripts/init_db.py
```

### 2. Ollama 环境检查

```bash
# 检查 Ollama 服务，验证 embedding 模型
python scripts/setup_ollama.py
```

### 3. ChromaDB 初始化

```bash
# 创建 ChromaDB collection
python scripts/setup_chromadb.py
```

---

## 核心 API 使用

### 配置管理

```python
from localmind.config import config

# 路径
config.data_dir          # data/ 目录
config.db_path           # data/personal.db
config.chroma_path       # data/chroma_db/
config.dimensions_dir    # dimensions/ 目录

# 模型配置
config.embed_model       # bge-m3:latest
config.llm_provider      # "ollama" 或 "deepseek"
config.ollama_base       # http://localhost:11434
config.ollama_model      # qwen2.5:7b

# 召回参数（HeyCube 公式权重）
config.recall_alpha      # rel_llm 权重 (0.4)
config.recall_beta       # hist 权重 (0.2)
config.recall_gamma      # pop 权重 (0.15)
config.recall_delta      # cooc 权重 (0.15)
config.recall_lambda     # fatigue 惩罚 (0.05)
config.recall_mu         # over_coverage 惩罚 (0.05)
```

### 数据库操作

```python
from localmind.db import Database

db = Database()

# 维度操作
dims = db.get_all_dimensions()
dim = db.get_dimension("identity.personality")

# 记录操作
db.add_record("uuid", "identity.personality", "用户很内向", "对话记录", 0.8)
records = db.get_records_by_dimension("identity.personality")
db.increment_record_usage("record_id")

# 统计
stats = db.get_stats()
```

### 向量存储

```python
from localmind.vector_store import VectorStore

vs = VectorStore()

# 添加记忆
embedding_id = vs.add_memory(
    dimension_id="identity.personality",
    content="用户性格内向",
    record_id="record_uuid",
    metadata={"confidence": 0.8}
)

# 语义搜索
results = vs.search(
    query="用户性格如何",
    n_results=5,
    dimension_filter="identity.personality"  # 可选
)
```

### 召回引擎

```python
from recall.engine import RecallEngine

engine = RecallEngine()
ctx = engine.recall(
    query="我是一个内向的人",
    conversation_id="conv_123",
    top_k=5,
    include_gaps=True,
)

# 结果
for result in ctx.recalled_results:
    print(f"维度: {result.dimension_name}")
    print(f"得分: {result.score}")
    print(f"记录: {result.records[0].content}")

# 生成注入 prompt
injection = ctx.to_injection_prompt()
```

### 记忆写入

```python
from write.analyzer import MemoryAnalyzer
from write.writer import MemoryWriter

# 分析对话
analyzer = MemoryAnalyzer()
analysis = analyzer.analyze("用户: 我是个内向的人\n助手: 了解")

if analysis.is_significant():
    # 写入记忆
    writer = MemoryWriter()
    written_ids = writer.write_analysis(analysis)
```

---

## OpenClaw Hook 集成

### Pre-Hook（对话前召回）

```bash
# CLI 调用
python hooks/pre_hook.py \
    --query "我想学设计" \
    --conversation-id "conv_123"

# 输出到 stdout: 注入上下文的 prompt
# 输出到 stderr: 日志
```

### Post-Hook（对话后写入）

```bash
# CLI 调用
python hooks/post_hook.py \
    --conversation "用户: 我是个内向的人\n助手: 了解" \
    --conversation-id "conv_123"

# 输出到 stdout: 状态摘要
# 输出到 stderr: 日志
```

### Wrapper 脚本

```bash
# Pre-hook
./hooks/wrapper.sh pre "query text" "conv_id"

# Post-hook
./hooks/wrapper.sh post "conversation text" "conv_id"
```

### OpenClaw 配置示例

```json
{
  "hooks": {
    "pre": {
      "enabled": true,
      "path": "/path/to/hooks/pre_hook.py",
      "args": ["--query", "{query}", "--conversation-id", "{conversation_id}"]
    },
    "post": {
      "enabled": true,
      "path": "/path/to/hooks/post_hook.py",
      "args": ["--conversation", "{conversation}", "--conversation-id", "{conversation_id}"]
    }
  }
}
```

---

## 测试

### 运行单个测试

```bash
python tests/test_db.py
python tests/test_dimensions.py
python tests/test_ollama.py
python tests/test_chromadb.py
```

### 运行集成测试

```bash
# 端到端测试（需要 Ollama 服务运行）
python tests/test_integration.py
```

### 测试前置条件

- Ollama 服务运行中（http://localhost:11434）
- SQLite 数据库已初始化（data/personal.db）
- ChromaDB 已初始化（data/chroma_db/）

---

## 代码规范

### 命名约定

- **类名**: PascalCase（如 `RecallEngine`, `MemoryWriter`）
- **函数/方法**: snake_case（如 `recall()`, `write_analysis()`）
- **常量**: UPPER_CASE（如 `RECALL_ALPHA`）
- **私有**: 下划线前缀（如 `_get_client()`）

### 模块组织

- 每个模块有清晰的文档字符串说明用途
- 使用 `logging` 模块记录日志，logger 命名：`__name__`
- 错误处理：捕获异常后记录到 stderr，stdout 保持干净（Hook 要求）

### 数据模型

使用 `@dataclass` 定义数据模型：

```python
@dataclass
class MemoryRecord:
    dimension_id: str
    content: str
    evidence: Optional[str] = None
    confidence: float = 0.5
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

---

## 配置覆盖

### 环境变量

```bash
# LLM Provider
export LOCALMIND_LLM_PROVIDER="deepseek"  # 或 "ollama"

# DeepSeek API Key
export DEEPSEEK_API_KEY="your-api-key"

# Hook 配置
export LOCALMIND_HOOK_ENABLED="true"
export LOCALMIND_RECALL_TOP_K="5"
export LOCALMIND_WRITE_ENABLED="true"
```

---

## 注意事项

1. **Graceful Degradation** - Hook 执行失败时不应影响主对话流程，错误只输出到 stderr
2. **stdout 干净** - Pre-hook 的 stdout 会被用作注入上下文，必须保持干净（只输出有效内容或空）
3. **隐私优先** - 所有数据存储在本地，不依赖外部 API（除非配置 DeepSeek）
4. **双重写入** - 记忆写入必须同时写入 SQLite 和 ChromaDB
5. **维度 ID 格式** - 使用 `domain.subdimension` 格式（如 `identity.personality`）

---

## 开发计划

- **Phase 1** ✅ - 基础架构：数据库、维度定义、Ollama/ChromaDB 集成
- **Phase 2** ✅ - 召回引擎、写入引擎、LLM 分析
- **Phase 3** ✅ - OpenClaw Hook 集成、端到端测试
- **Phase 4** (未来) - Web API（FastAPI）、配置优化、Web UI

---

## License

MIT
