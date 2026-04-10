# 2026-04-10 开发修改记录

本文档记录 2026-04-10 在开发机上对 LocalMind 做的主要修改、原因和验证结果。

## 目标

本轮工作的目标不是继续扩新功能，而是把 Phase 4-8 从“代码存在但受环境阻塞”推进到“开发机可继续验证”。

主要阻塞有三类：

1. 开发机未配置 `.env` 自动加载，DeepSeek key 虽存在于本地文件，但项目运行时读不到。
2. 开发机没有可用的 Ollama embedding 服务，`/api/embeddings` 持续返回 `503`。
3. 默认 `data/` 目录在当前环境里出现 SQLite/Chroma `disk I/O error`，影响测试和 benchmark。

## 本次修改概览

### 1. 配置层与开发环境隔离

修改文件：
- [config.py](/D:/localmind/localmind/config.py)
- [.env.example](/D:/localmind/.env.example)

主要变更：
- 增加项目根目录 `.env` 自动加载逻辑，不依赖额外库。
- 支持通过 `LOCALMIND_DATA_DIR` 指定数据目录。
- 从环境变量读取 `LOCALMIND_LLM_PROVIDER`、`DEEPSEEK_API_KEY`、`LOCALMIND_DEEPSEEK_MODEL` 等配置。

目的：
- 让开发机可以安全使用本地 `.env` 里的 DeepSeek key。
- 让开发机与部署机可以使用不同的数据目录，避免互相污染。

### 2. 数据初始化脚本修复

修改文件：
- [init_db.py](/D:/localmind/scripts/init_db.py)

主要变更：
- 初始化脚本改为复用 `config.db_path` 和 `config.dimensions_dir`，不再硬编码 `data/`。
- 输出改为纯文本，避免 Windows GBK 控制台因 emoji 报错。

目的：
- 支持 `LOCALMIND_DATA_DIR`。
- 让脚本在 Windows 控制台稳定运行。

### 3. 历史数据回填脚本

新增文件：
- [backfill_memories.py](/D:/localmind/scripts/backfill_memories.py)
- [test_backfill.py](/D:/localmind/tests/test_backfill.py)

主要功能：
- 支持从 `json/jsonl/txt/md` 文件回填历史对话。
- 支持目录递归扫描。
- 支持从 `records.raw_snippet` 回灌。
- 支持“只写 verbatim”或“结构化 + verbatim”。

目的：
- 为后续部署机重建库、迁移数据、重新清洗历史对话提供工具。

### 4. 写入阶段维度约束与归一化

修改文件：
- [prompts.py](/D:/localmind/localmind/prompts.py)
- [analyzer.py](/D:/localmind/write/analyzer.py)

主要变更：
- 在记忆提取提示词中注入 55 个可用维度，明确要求模型只能从现有维度中选择。
- 为 LLM 输出的 `dimension_id` 增加归一化逻辑。
- 将如 `personal_info.identity`、`personality.traits`、`activity.learning` 等非法或不兼容的维度映射到现有维度。

目的：
- 修复 DeepSeek 生成“仓库里不存在的 dimension_id”导致写入后召回不到的问题。

### 5. 结构化召回降级路径

修改文件：
- [db.py](/D:/localmind/localmind/db.py)
- [semantic.py](/D:/localmind/recall/semantic.py)
- [test_fallbacks.py](/D:/localmind/tests/test_fallbacks.py)

主要变更：
- `Database` 增加 `get_all_records()`。
- `Record` dataclass 接收 `raw_snippet` 字段，兼容当前 schema。
- `SemanticRecall` 在 embedding 不可用时自动回退到 SQLite 词面匹配。
- 新增对词面相似度和维度归一化的测试。

目的：
- 让开发机在没有 Ollama 的情况下，依然能完成基本写入、搜索和 benchmark。

### 6. Verbatim SQLite fallback

修改文件：
- [verbatim_store.py](/D:/localmind/localmind/verbatim_store.py)
- [test_verbatim.py](/D:/localmind/tests/test_verbatim.py)

主要变更：
- `VerbatimStore` 现在支持双路径：
  - 有 embedding：走 Chroma
  - 无 embedding：回退到 SQLite 表 `verbatim_snippets`
- 为 `store_conversation`、`search`、`search_by_keywords`、`count`、`get_stats`、`delete_by_source` 增加 fallback。
- 新增专门的 SQLite fallback 测试。

目的：
- 让 Phase 6 在开发机无 Ollama 时也能真正存 verbatim、搜 verbatim。

### 7. Phase 8 API 收口

修改文件：
- [main.py](/D:/localmind/api/main.py)
- [test_api.py](/D:/localmind/tests/test_api.py)
- [README.md](/D:/localmind/README.md)

主要变更：
- API 改成懒初始化，避免导入时就绑定坏数据目录。
- 补上 `/api/v1/search` 路由。
- API 测试同步更新，覆盖 `search` 路由和模型。
- README 补充 FastAPI/uvicorn 依赖和开发机数据目录说明。

目的：
- 让 Phase 8 在开发机上可以真正导入和测试。

## 验证结果

### 已通过

- `python tests/test_backfill.py`
- `python tests/test_fallbacks.py`
- `python tests/test_api.py`
- `python tests/test_verbatim.py`（在脱离沙箱、`data_bench` 环境下通过）
- `python tests/test_integration.py`（在脱离沙箱、`data_dev` 环境下通过）

### Benchmark

在 `LOCALMIND_DATA_DIR=D:\localmind\data_bench` 且无 Ollama embedding 的开发机上：

- 初始状态：`R@5 = 0%`
- 加入维度归一化 + lexical fallback 后，mini benchmark 最高达到：
  - `R@1 = 80%`
  - `R@5 = 100%`
  - `R@10 = 100%`

后续又因数据状态不同出现过一次：
- `R@1 = 80%`
- `R@5 = 80%`
- `R@10 = 100%`

结论：
- 开发机无 Ollama 时，Phase 7 已不再是完全阻塞状态。
- 真实语义向量效果仍需在有 Ollama embedding 的环境中验证。

## 当前已知限制

1. 开发机当前没有可用的 Ollama embedding 服务，Chroma 语义路径仍会报 `503`。
2. 默认 `data/` 目录在当前环境中不适合作为测试目录，应优先使用 `data_dev` / `data_bench`。
3. 开发机现在主要验证的是：
   - SQLite 结构化写入
   - lexical fallback 召回
   - verbatim SQLite fallback
4. 部署机若要验证真实向量效果，仍建议启用 Ollama embedding。

## 推荐后续动作

1. 本地 `.env` 固定写入 `LOCALMIND_DATA_DIR=D:/localmind/data_dev`
2. 开发机日常测试使用 `data_dev`
3. benchmark 单独使用 `data_bench`
4. 部署机若重建数据，使用回填脚本重新清洗旧对话
