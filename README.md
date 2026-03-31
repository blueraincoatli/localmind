# LocalMind - 结构化 AI 记忆系统

基于 HeyCube 思路的完全本地化复刻方案，为 OpenClaw 提供结构化记忆能力。

## 核心特性

- **完全本地化** - 不依赖任何第三方 API（除 Ollama 外）
- **结构化存储** - 8 大域分类，55 个维度，SQLite + ChromaDB
- **语义召回** - 基于向量的精准语义搜索
- **多路召回** - 语义 + 历史 + 热度 + 共现 + 空白检测
- **自动进化** - 记忆越用越准

## 8 大域分类

| 域 | 维度数 | 说明 |
|----|--------|------|
| 身份认知 | 6 | 姓名、性格、自我认知等 |
| 心理结构 | 7 | 思维方式、决策风格、情绪模式等 |
| 审美偏好 | 7 | 视觉、音乐、设计品味等 |
| 职业画像 | 7 | 技能树、工作风格、行业背景等 |
| 计划目标 | 6 | 短期/长期目标、项目计划等 |
| 日程节奏 | 6 | 作息、能量曲线、高效时段等 |
| 杂项偏好 | 8 | 饮食、运动、爱好、宠物等 |
| 关系网络 | 8 | 家人、朋友、同事、社交风格等 |

## 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install chromadb requests pyyaml

# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull nomic-embed-text
ollama pull qwen2.5:7b  # 或其他 LLM
```

### 2. 初始化

```bash
# 初始化数据库
python scripts/init_db.py

# 验证 Ollama
python scripts/setup_ollama.py

# 验证 ChromaDB
python scripts/setup_chromadb.py
```

### 3. 运行测试

```bash
python tests/test_db.py
python tests/test_dimensions.py
```

## 项目结构

```
LocalMind/
├── dimensions/           # 8 大域 YAML 定义
├── localmind/            # 核心代码包
│   ├── config.py         # 配置管理
│   ├── db.py             # SQLite 操作
│   ├── vector_store.py   # ChromaDB 封装
│   ├── models.py         # 数据模型
│   └── prompts.py        # LLM 提示词
├── scripts/              # 初始化脚本
├── tests/                # 测试文件
└── data/                 # 数据存储
    ├── personal.db       # SQLite 数据库
    └── chroma_db/        # ChromaDB 向量库
```

## 核心模块

### 召回引擎（Phase 2 开发中）

```
score(d) = α·rel_llm + β·hist + γ·pop + δ·cooc - λ·fatigue - μ·over_coverage
```

### 写入引擎（Phase 2 开发中）

对话结束 → LLM 分析 → 结构化提取 → 双重写入 SQLite + ChromaDB

## License

MIT
