#!/bin/bash
# LocalMind Hook Wrapper
# 方便命令行调用 hook 脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# 默认参数
CONVERSATION_ID="${1:-default}"
QUERY="${2:-}"
RESPONSE="${3:-}"

if [ "$0" == *pre* ]; then
    # Pre-hook: 召回
    echo "=== LocalMind Pre-Hook ===" >&2
    exec python3 "$SCRIPT_DIR/pre_hook.py" "$CONVERSATION_ID" "$QUERY"
else
    # Post-hook: 写入
    echo "=== LocalMind Post-Hook ===" >&2
    exec python3 "$SCRIPT_DIR/post_hook.py" "$CONVERSATION_ID" "$QUERY" "$RESPONSE"
fi
