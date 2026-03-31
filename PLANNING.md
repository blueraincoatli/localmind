# LocalMind PLANNING.md

## HeyCube 架构分析

HeyCube 是一个 AI 记忆系统，核心架构：

### 8 大域分类
1. **身份认知** - 用户是谁、基本信息、性格特点
2. **心理结构** - 情绪模式、思维方式、心理偏好
3. **审美偏好** - 视觉、音乐、设计等审美倾向
4. **职业画像** - 工作背景、技能树、项目经验
5. **计划目标** - 短期/长期目标、待办事项
6. **日程节奏** - 日常规律、时间习惯
7. **杂项偏好** - 零散的个人喜好
8. **关系网络** - 人际关系、联系人信息

### 召回流程 (Recall)
```
对话前输入 → 语义搜索 → 历史搜索 → 热度排序 → 共现分析 → 空白检测
→ 加权排序 → Top-K 选取 → 上下文注入
```

**排序公式：**
```
score(d) = α·rel_llm + β·hist + γ·pop + δ·cooc - λ·fatigue - μ·over_coverage
```
- `rel_llm`: LLM 相关性评分
- `hist`: 历史访问频率
- `pop`: 热度/热门程度
- `cooc`: 共现权重（多域同时出现的记录）
- `fatigue`: 疲劳惩罚（近期频繁出现的降权）
- `over_coverage`: 过度覆盖惩罚（已有类似记忆的降权）

### 写入流程 (Write)
```
对话结束 → LLM 分析 → 结构化 Record → SQLite 存储 + ChromaDB 向量存储
```

### 技术栈
- **数据库**: SQLite（结构化数据）+ ChromaDB（向量检索）
- **Embedding**: Ollama + nomic-embed-text
- **LLM**: Ollama（本机运行）
- **语言**: Python 3

---

## LocalMind 复刻方案

### 核心差异
| 项目 | HeyCube | LocalMind |
|------|---------|-----------|
| 部署 | 服务器 | 完全本地 |
| API | 依赖外部 | 仅 Ollama |
| 数据 | 云端存储 | 本地 SQLite |
| 向量 | 云端服务 | ChromaDB (本地) |

### Phase 1 目标（当前）
- ✅ 项目目录结构建立
- ✅ SQLite 数据库 schema 初始化
- ✅ 8 大域 YAML 定义文件
- ✅ Ollama 连接验证
- ✅ ChromaDB 初始化脚本
- ✅ 基础测试文件

### Phase 2（后续）
- Recall 引擎实现
- Write 引擎实现
- LLM 分析集成

### Phase 3（后续）
- API 服务封装
- Web UI（可选）

---

## 文件结构设计

```
LocalMind/
├── PLANNING.md
├── SPEC.md
├── README.md
├── dimensions/           # 8大域 YAML 定义
│   ├── identity.yaml     # 身份认知
│   ├── psychology.yaml   # 心理结构
│   ├── aesthetic.yaml    # 审美偏好
│   ├── career.yaml       # 职业画像
│   ├── goals.yaml         # 计划目标
│   ├── schedule.yaml      # 日程节奏
│   ├── misc.yaml          # 杂项偏好
│   └── relations.yaml     # 关系网络
├── scripts/
│   ├── init_db.py        # SQLite 初始化
│   ├── setup_ollama.py   # Ollama 验证
│   └── setup_chromadb.py # ChromaDB 初始化
├── tests/
│   ├── test_db.py
│   ├── test_dimensions.py
│   ├── test_ollama.py
│   └── test_chromadb.py
└── localmind/            # 核心代码包
    ├── __init__.py
    ├── config.py         # 配置管理
    ├── db.py             # 数据库操作
    ├── vector_store.py   # ChromaDB 封装
    ├── models.py         # 数据模型
    └── prompts.py        # 提示词模板
```

---

## Phase 1 交付物

1. `PLANNING.md` - 本文件
2. `SPEC.md` - 详细规格文档
3. `dimensions/*.yaml` - 8 个域定义
4. `scripts/init_db.py` - SQLite schema 初始化
5. `scripts/setup_ollama.py` - Ollama 验证脚本
6. `scripts/setup_chromadb.py` - ChromaDB 初始化
7. `tests/*.py` - 基础测试文件
8. `localmind/` - 核心代码包框架
