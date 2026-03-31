#!/bin/bash
# LocalMind Hook Wrapper
# 方便直接调用 pre/post hook
#
# 用法:
#   ./wrapper.sh pre "query text" "conv_id"
#   ./wrapper.sh post "conversation text" "conv_id"
#
# 示例:
#   ./wrapper.sh pre "我想学设计" "conv_123"
#   ./wrapper.sh post "用户: 我今天心情不好\n助手: 怎么了？" "conv_123"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "用法: $0 <pre|post> <text> [conversation_id]"
    echo "  pre  - 召回相关记忆（text = query）"
    echo "  post - 写入对话记忆（text = conversation）"
    exit 1
}

if [ $# -lt 2 ]; then
    usage
fi

MODE="$1"
TEXT="$2"
CONV_ID="${3:-default}"

case "$MODE" in
    pre)
        python3 "$SCRIPT_DIR/pre_hook.py" --query "$TEXT" --conversation-id "$CONV_ID"
        ;;
    post)
        python3 "$SCRIPT_DIR/post_hook.py" --conversation "$TEXT" --conversation-id "$CONV_ID"
        ;;
    *)
        echo "错误: 未知模式 '$MODE' (必须是 pre 或 post)"
        usage
        ;;
esac
