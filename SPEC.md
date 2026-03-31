# LocalMind SPEC.md - 详细规格文档

## 1. 项目概述

**项目名称**: LocalMind  
**项目类型**: 本地化 AI 记忆系统  
**核心功能**: 结构化存储用户记忆，对话时智能召回相关记忆片段  
**目标用户**: 希望在本地部署 AI 个人记忆系统的用户  

---

## 2. 技术规格

### 2.1 技术栈

| 组件 | 技术选型 | 版本要求 |
|------|----------|----------|
| 语言 | Python | >= 3.10 |
| 结构化数据库 | SQLite | 3.x |
| 向量数据库 | ChromaDB | >= 0.4.x |
| Embedding 模型 | Ollama + nomic-embed-text | 最新 |
| LLM | Ollama | 最新 |

### 2.2 数据目录结构

```
~/.local/localmind/
├── localmind.db        # SQLite 数据库
├── chroma_db/          # ChromaDB 数据目录
└── config.yaml         # 本地配置文件
```

---

## 3. 数据库 Schema

### 3.1 dimensions 表

存储 8 大域的定义。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PRIMARY KEY | 域 ID，如 `identity_name` |
| domain | TEXT NOT NULL | 域分类，如 `identity` |
| name | TEXT NOT NULL | 中文名称，如 `姓名` |
| focus_prompt | TEXT NOT NULL | 召回焦点提示词 |
| description | TEXT | 域描述 |
| created_at | TIMESTAMP | 创建时间 |

**8 大域分类**:
- `identity` - 身份认知
- `psychology` - 心理结构
- `aesthetic` - 审美偏好
- `career` - 职业画像
- `goals` - 计划目标
- `schedule` - 日程节奏
- `misc` - 杂项偏好
- `relations` - 关系网络

### 3.2 records 表

存储记忆记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PRIMARY KEY | UUID |
| dimension_id | TEXT NOT NULL | 关联的 dimension |
| content | TEXT NOT NULL | 记忆内容原文 |
| summary | TEXT | LLM 生成的摘要 |
| keywords | TEXT | 关键词列表（JSON 数组） |
| metadata | TEXT | 附加元数据（JSON 对象） |
| importance | REAL DEFAULT 0.5 | 重要程度 0-1 |
| access_count | INTEGER DEFAULT 0 | 访问次数 |
| last_accessed | TIMESTAMP | 最后访问时间 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 3.3 record_vectors 表

存储向量映射（ChromaDB 的 SQLite 映射表）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PRIMARY KEY | record_id |
| chroma_id | TEXT NOT NULL | ChromaDB 中的 vector ID |
| dimension_id | TEXT NOT NULL | 关联的 dimension |
| created_at | TIMESTAMP | 创建时间 |

---

## 4. Dimension YAML 定义格式

每个域一个 YAML 文件，格式如下：

```yaml
domain: identity
name: 身份认知
description: 用户的基本身份信息和性格特点
dimensions:
  - id: identity_name
    name: 姓名
    focus_prompt: 用户如何称呼，喜欢被怎么叫，是否有昵称

  - id: identity_basic
    name: 基本信息
    focus_prompt: 用户的年龄、性别、职业等基本信息
```

### 4.1 8 大域详细定义

#### identity (身份认知)
- `identity_name` - 姓名/昵称
- `identity_basic` - 基本信息（年龄、职业等）
- `identity_personality` - 性格特点
- `identity_background` - 背景经历

#### psychology (心理结构)
- `psychology_emotion` - 情绪模式
- `psychology_thinking` - 思维方式
- `psychology_preference` - 心理偏好
- `psychology_trigger` - 敏感触发点

#### aesthetic (审美偏好)
- `aesthetic_visual` - 视觉审美
- `aesthetic_music` - 音乐偏好
- `aesthetic_design` - 设计偏好
- `aesthetic_lifestyle` - 生活方式审美

#### career (职业画像)
- `career_background` - 职业背景
- `career_skills` - 技能树
- `career_projects` - 项目经验
- `career_goals` - 职业目标

#### goals (计划目标)
- `goals_short_term` - 短期目标
- `goals_long_term` - 长期目标
- `goals_todo` - 待办事项
- `goals_idea` - 想法/点子

#### schedule (日程节奏)
- `schedule_daily` - 日常规律
- `schedule_work` - 工作节奏
- `schedule_rest` - 休息习惯
- `schedule_habit` - 习惯性行为

#### misc (杂项偏好)
- `misc_food` - 食物偏好
- `misc_entertainment` - 娱乐偏好
- `misc_reading` - 阅读偏好
- `misc_other` - 其他偏好

#### relations (关系网络)
- `relations_family` - 家庭关系
- `relations_friend` - 朋友关系
- `relations_colleague` - 同事关系
- `relations_other` - 其他关系

---

## 5. API/接口规格

### 5.1 配置管理

```python
# localmind/config.py
class Config:
    DATA_DIR: Path = ~/.local/localmind
    DB_PATH: Path = DATA_DIR / "localmind.db"
    CHROMA_PATH: Path = DATA_DIR / "chroma_db"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    DEFAULT_COLLECTION: str = "localmind_memories"
```

### 5.2 数据库操作

```python
# localmind/db.py
class Database:
    def init_schema(self) -> None: ...
    def insert_record(self, record: Record) -> str: ...
    def get_record(self, record_id: str) -> Optional[Record]: ...
    def update_record(self, record_id: str, **kwargs) -> None: ...
    def delete_record(self, record_id: str) -> None: ...
    def search_by_dimension(self, dimension_id: str, limit: int = 10) -> List[Record]: ...
    def increment_access(self, record_id: str) -> None: ...
```

### 5.3 向量存储操作

```python
# localmind/vector_store.py
class VectorStore:
    def __init__(self, collection_name: str = "localmind_memories"): ...
    def add_text(self, text: str, record_id: str, metadata: dict) -> str: ...
    def search(self, query: str, n_results: int = 5, filter: dict = None) -> List[dict]: ...
    def delete(self, vector_id: str) -> None: ...
    def count(self) -> int: ...
```

---

## 6. Ollama 集成

### 6.1 验证脚本 (setup_ollama.py)

```bash
# 检查 Ollama 服务是否运行
curl http://localhost:11434/api/version

# 检查 nomic-embed-text 模型是否可用
curl http://localhost:11434/api/show -d '{"name": "nomic-embed-text"}'

# 如不可用，拉取模型
ollama pull nomic-embed-text
```

### 6.2 Ollama API 调用方式

```python
import ollama

# Embedding 生成
response = ollama.embeddings(
    model="nomic-embed-text",
    prompt="要嵌入的文本"
)
embedding = response["embedding"]

# LLM 调用（未来使用）
response = ollama.generate(
    model="llama3.2",
    prompt="用户输入"
)
```

---

## 7. ChromaDB 集成

### 7.1 初始化脚本 (setup_chromadb.py)

```python
import chromadb
from chromadb.config import Settings

# 创建持久化客户端
client = chromadb.PersistentClient(
    path=str(CHROMA_PATH),
    settings=Settings(anonymized_telemetry=False)
)

# 创建或获取集合
collection = client.get_or_create_collection(
    name="localmind_memories",
    metadata={"description": "LocalMind 记忆向量存储"}
)
```

### 7.2 Collection 元数据

```python
{
    "name": "localmind_memories",
    "description": "LocalMind 记忆向量存储",
    "dimension": 768,  # nomic-embed-text 输出维度
    "metric": "cosine"
}
```

---

## 8. 测试规格

### 8.1 test_db.py

- `test_init_schema`: 测试数据库初始化
- `test_insert_record`: 测试记录插入
- `test_get_record`: 测试记录查询
- `test_update_record`: 测试记录更新
- `test_delete_record`: 测试记录删除
- `test_search_by_dimension`: 测试按域搜索

### 8.2 test_dimensions.py

- `test_load_all_dimensions`: 测试加载所有域定义
- `test_dimension_schema`: 测试域 YAML 格式
- `test_dimension_count`: 测试域数量（应为 8）

### 8.3 test_ollama.py

- `test_ollama_running`: 测试 Ollama 服务运行状态
- `test_embedding_model`: 测试 embedding 生成
- `test_embedding_dimension`: 测试向量维度

### 8.4 test_chromadb.py

- `test_chromadb_connection`: 测试 ChromaDB 连接
- `test_collection_creation`: 测试创建集合
- `test_vector_operations`: 测试向量添加/搜索

---

## 9. 项目约束

1. **本地化**: 所有数据存储在本地，不依赖任何第三方 API（Ollama 除外）
2. **隐私优先**: 不上传任何用户数据
3. **简单部署**: 依赖项最小化，易于安装
4. **可扩展**: 架构支持未来功能扩展

---

## 10. OpenClaw Hook 集成（Phase 3）

### 10.1 Hook 机制说明

OpenClaw 支持 Pre-Hook 和 Post-Hook 脚本，通过 `openclaw.json` 配置：

```json
{
  "hooks": {
    "pre": {
      "enabled": true,
      "path": "/home/ra001/clawd/LocalMind/hooks/pre_hook.py",
      "args": ["--query", "{query}", "--conversation-id", "{conversation_id}"]
    },
    "post": {
      "enabled": true,
      "path": "/home/ra001/clawd/LocalMind/hooks/post_hook.py",
      "args": ["--conversation", "{conversation}", "--conversation-id", "{conversation_id}"]
    }
  }
}
```

**变量说明**：
- `{query}` — 当前对话的用户输入
- `{conversation}` — 完整对话历史（多轮 JSON 字符串）
- `{conversation_id}` — 会话唯一 ID

### 10.2 Hook 接口规格

#### Pre-Hook (`pre_hook.py`)

对话前执行，召回相关记忆，输出注入上下文。

**CLI 参数**：
```
--query           当前对话查询（必填）
--conversation-id 对话 ID（默认: "default"）
```

**输出**：
- `stdout`: 注入 prompt（空或 `"[相关记忆]\n"` 时 OpenClaw 不注入）
- `stderr`: 日志

**示例**：
```bash
python3 hooks/pre_hook.py --query "我想学设计" --conversation-id "conv_123"
```

#### Post-Hook (`post_hook.py`)

对话后执行，分析对话并写入记忆。

**CLI 参数**：
```
--conversation    完整对话文本（必填，支持多轮 JSON 或纯文本）
--conversation-id 对话 ID（默认: "default"）
```

**输出**：
- `stdout`: 状态摘要（如 `"写入 3 条记忆"` 或 `"无需记录"`）
- `stderr`: 日志

**示例**：
```bash
python3 hooks/post_hook.py --conversation "用户: 我内向\n助手: 了解" --conversation-id "conv_123"
```

### 10.3 Hook 包装器

`hooks/wrapper.sh` 提供简化的直接调用接口：

```bash
# Pre-hook
./hooks/wrapper.sh pre "query text" "conv_id"

# Post-hook
./hooks/wrapper.sh post "用户: ...\n助手: ..." "conv_id"
```

### 10.4 OpenClaw 配置步骤

1. 找到 OpenClaw 配置文件 `openclaw.json`
2. 在 `hooks` 字段添加以上配置
3. 重启 OpenClaw Gateway：`openclaw gateway restart`
4. 验证 hooks 工作：`python3 hooks/pre_hook.py --query "test" --conversation-id "test"`

### 10.5 行为约束

- Pre-hook 输出为空或仅含 `"[相关记忆]"` 时，不注入（避免噪声）
- Post-hook 执行失败时 `exit 0`（graceful，不影响主对话流程）
- 所有异常捕获后打印到 stderr，不污染 stdout

---

## 11. 端到端测试（Phase 3）

### 11.1 测试文件

`tests/test_integration.py` — 完整 recall → write 生命周期测试

### 11.2 运行方法

```bash
cd /home/ra001/clawd/LocalMind
python3 tests/test_integration.py
```

### 11.3 测试用例

| 测试函数 | 验证内容 |
|---------|---------|
| `test_pre_hook_recall_personality` | "我是一个内向的人" 召回 → identity.personality 被命中 |
| `test_pre_hook_empty_query` | 空 query graceful 处理 |
| `test_post_hook_significant_conversation` | 显著对话 → SQLite 记录数增加 |
| `test_post_hook_trivial_conversation` | 闲聊对话不触发写入 |
| `test_hook_cli_pre` | CLI 调用 pre_hook.py 返回码 0 |
| `test_hook_cli_post` | CLI 调用 post_hook.py 返回码 0 |
| `test_wrapper_script` | wrapper.sh pre/post 均返回码 0 |

### 11.4 前置条件

- Ollama 服务运行中（`http://localhost:11434`）
- ChromaDB 已初始化（`data/chroma_db` 目录存在）
- SQLite 数据库已初始化（`data/personal.db`）
- Ollama 模型可用：`bge-m3:latest`（embedding）、`qwen2.5:7b`（LLM 分析）

---

## 12. 未来扩展 (Phase 2+)

- Recall 引擎：语义 + 历史 + 热度 + 共现 + 空白检测 ✅（Phase 2）
- Write 引擎：LLM 分析 + 结构化提取 ✅（Phase 2）
- OpenClaw Hook 集成 ✅（Phase 3）
- Web API：FastAPI 封装
- 配置优化：排序公式参数可调
