# 开发机运行说明 + 部署机回填说明

本文档分两部分：

1. 当前开发机如何稳定运行 LocalMind
2. 部署机在重建数据库或迁移后如何回填历史数据

## 一、开发机运行说明

### 1. 当前环境前提

开发机当前特点：

- 已有本地 `.env`
- 可使用 DeepSeek API
- 没有稳定可用的 Ollama embedding 服务
- 默认 `data/` 目录不建议继续作为测试目录

因此开发机推荐运行模式是：

- LLM 提取：DeepSeek
- 结构化写入：SQLite
- 结构化召回：SQLite lexical fallback
- Verbatim：SQLite fallback
- 数据目录：`data_dev` 或 `data_bench`

### 2. 推荐 `.env`

开发机建议在项目根目录 `D:\localmind\.env` 中至少包含：

```env
LOCALMIND_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的_deepseek_key
LOCALMIND_DEEPSEEK_MODEL=deepseek-chat
LOCALMIND_DATA_DIR=D:/localmind/data_dev
```

说明：
- `LOCALMIND_DATA_DIR` 建议固定为 `data_dev`
- benchmark 时可以临时切到 `data_bench`

### 3. 初始化开发机数据库

PowerShell：

```powershell
$env:LOCALMIND_DATA_DIR="D:\localmind\data_dev"
python scripts/init_db.py
```

如果是 benchmark：

```powershell
$env:LOCALMIND_DATA_DIR="D:\localmind\data_bench"
python scripts/init_db.py
```

### 4. 常用测试命令

开发机建议先设置：

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
$env:LOCALMIND_DATA_DIR="D:\localmind\data_dev"
```

然后运行：

```powershell
python tests/test_backfill.py
python tests/test_fallbacks.py
python tests/test_api.py
python tests/test_verbatim.py
python tests/test_integration.py
```

说明：
- 在当前环境下，某些涉及 SQLite/Chroma 落盘的测试如果在受限沙箱中执行，可能报 `disk I/O error`
- 这类情况优先在正常本机 PowerShell 中执行

### 5. 启动 API

```powershell
$env:LOCALMIND_DATA_DIR="D:\localmind\data_dev"
uvicorn api.main:app --reload
```

接口文档：

```text
http://localhost:8000/docs
```

当前 API 端点：

- `GET /`
- `GET /health`
- `GET /api/v1/status`
- `POST /api/v1/recall`
- `POST /api/v1/wake_up`
- `POST /api/v1/remember`
- `GET /api/v1/dimensions`
- `GET /api/v1/stats`
- `POST /api/v1/search`

### 6. 跑 benchmark

推荐使用独立目录，避免污染开发库：

```powershell
$env:LOCALMIND_DATA_DIR="D:\localmind\data_bench"
python scripts/init_db.py
python benchmarks/longmemeval_bench.py
```

当前开发机无 Ollama 时，benchmark 主要测的是：

- DeepSeek 提取
- 维度归一化
- SQLite lexical fallback

不是完整的向量召回能力。

### 7. 当前开发机的已知限制

1. 没有 Ollama embedding，`http://localhost:11434/api/embeddings` 可能返回 `503`
2. 因此 Chroma 路径可能失败，但系统会自动回退到 SQLite
3. 真实语义检索质量需要在部署机或有 Ollama 的机器上复测

## 二、部署机回填说明

### 1. 适用场景

部署机需要回填时，通常有以下几种情况：

1. 重建了 `personal.db` / `chroma_db`
2. 新增了提取策略，想对旧对话重新清洗
3. 从旧版本迁移到新版本，需要把历史对话重新灌入记忆系统

### 2. 回填脚本

使用脚本：

- [backfill_memories.py](/D:/localmind/scripts/backfill_memories.py)

支持来源：

- 单个 `json`
- 单个 `jsonl`
- 单个 `txt`
- 单个 `md`
- 一个目录（可递归）
- `records.raw_snippet`

### 3. 标准回填流程

#### 情况 A：从导出的历史对话文件回填

```powershell
python scripts/backfill_memories.py --input exports/chat_history.json
```

目录批量回填：

```powershell
python scripts/backfill_memories.py --input exports/conversations --recursive
```

#### 情况 B：从数据库 `raw_snippet` 回灌

```powershell
python scripts/backfill_memories.py --from-db-raw-snippets
```

#### 情况 C：只回填 verbatim，不做结构化提取

```powershell
python scripts/backfill_memories.py --input exports/conversations --recursive --skip-structured
```

### 4. 推荐顺序

如果部署机要完全重建：

1. 先备份旧数据
2. 初始化新库

```powershell
python scripts/init_db.py
```

3. 执行回填

```powershell
python scripts/backfill_memories.py --input exports/conversations --recursive
```

4. 再运行必要测试或抽样检查召回效果

### 5. 输入格式建议

#### JSON

支持如下格式：

```json
[
  {
    "conversation_id": "conv_001",
    "messages": [
      {"role": "user", "content": "我叫 Alice"},
      {"role": "assistant", "content": "你好 Alice"}
    ]
  }
]
```

也支持：

```json
[
  {
    "conversation_id": "conv_002",
    "conversation": "用户: 我喜欢简约风格\n助手: 收到"
  }
]
```

#### JSONL

每行一个 JSON 对象，字段与上面一致。

#### TXT / MD

直接存放对话文本，例如：

```text
用户: 我最近在学习 Python
助手: 好的
用户: 我喜欢简约风格
```

### 6. 回填后的预期结果

执行回填后，脚本会输出：

- 扫描对话数
- 结构化写入数
- Verbatim 写入数
- 失败数

如果部署机有 Ollama embedding：
- 结构化记忆会写入 SQLite + Chroma
- verbatim 会写入 Chroma 或 fallback

如果部署机暂时没有 Ollama embedding：
- 结构化记忆仍会写入 SQLite
- 结构化召回走 lexical fallback
- verbatim 会回退到 SQLite 存储

### 7. 重要注意事项

1. 回填不是简单复制旧数据库，而是“重新清洗旧对话”
2. 回填质量会受当前 LLM 提取策略影响
3. 如果你更新了 prompt 或维度映射规则，建议重新跑回填
4. benchmark 和生产库建议分开目录，避免互相污染
