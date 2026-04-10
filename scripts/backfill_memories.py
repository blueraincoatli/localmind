#!/usr/bin/env python3
"""
LocalMind 历史记忆回填脚本

用途：
1. 从历史对话文件重新提取结构化记忆和 verbatim 片段
2. 从 records.raw_snippet 回灌历史原文
3. 在重建 SQLite / ChromaDB 后重新灌入有价值的历史数据

支持输入：
- 单个 json/jsonl/txt/md 文件
- 目录批量导入
- 从现有 SQLite records.raw_snippet 读取

示例：
    python scripts/backfill_memories.py --input exports/chat_history.json
    python scripts/backfill_memories.py --input exports/conversations --recursive
    python scripts/backfill_memories.py --from-db-raw-snippets
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Iterable, Iterator, Optional

PROJECT_ROOT = Path(__file__).parent.parent

import sys

sys.path.insert(0, str(PROJECT_ROOT))

from localmind.config import config
from write.analyzer import MemoryAnalyzer
from write.writer import MemoryWriter


SUPPORTED_SUFFIXES = {".json", ".jsonl", ".txt", ".md"}


@dataclass
class ConversationItem:
    conversation_id: str
    conversation: str
    source: str


def render_messages(messages: list[dict]) -> str:
    """将 message 列表转换为统一对话文本。"""
    lines = []
    for msg in messages:
        role = str(msg.get("role", "user")).strip().lower()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue

        if role in {"assistant", "system"}:
            speaker = "助手"
        else:
            speaker = "用户"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines).strip()


def normalize_conversation_id(raw_id: str, fallback: str) -> str:
    value = (raw_id or "").strip()
    return value or fallback


def load_json_items(path: Path) -> list[ConversationItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[ConversationItem] = []

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return items

    for index, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            continue

        conversation = ""
        if isinstance(entry.get("conversation"), str):
            conversation = entry["conversation"].strip()
        elif isinstance(entry.get("messages"), list):
            conversation = render_messages(entry["messages"])

        if not conversation:
            continue

        fallback_id = f"{path.stem}-{index}"
        conversation_id = normalize_conversation_id(
            str(entry.get("conversation_id", "")),
            fallback_id,
        )
        items.append(
            ConversationItem(
                conversation_id=conversation_id,
                conversation=conversation,
                source=str(path),
            )
        )

    return items


def load_jsonl_items(path: Path) -> list[ConversationItem]:
    items: list[ConversationItem] = []
    for index, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(entry, dict):
            continue

        conversation = ""
        if isinstance(entry.get("conversation"), str):
            conversation = entry["conversation"].strip()
        elif isinstance(entry.get("messages"), list):
            conversation = render_messages(entry["messages"])

        if not conversation:
            continue

        items.append(
            ConversationItem(
                conversation_id=normalize_conversation_id(
                    str(entry.get("conversation_id", "")),
                    f"{path.stem}-{index}",
                ),
                conversation=conversation,
                source=str(path),
            )
        )

    return items


def load_plain_text_item(path: Path) -> list[ConversationItem]:
    conversation = path.read_text(encoding="utf-8").strip()
    if not conversation:
        return []

    return [
        ConversationItem(
            conversation_id=path.stem,
            conversation=conversation,
            source=str(path),
        )
    ]


def load_conversations_from_path(path: Path) -> list[ConversationItem]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_json_items(path)
    if suffix == ".jsonl":
        return load_jsonl_items(path)
    if suffix in {".txt", ".md"}:
        return load_plain_text_item(path)
    return []


def iter_input_files(path: Path, recursive: bool) -> Iterator[Path]:
    if path.is_file():
        if path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path
        return

    if not path.is_dir():
        return

    iterator: Iterable[Path]
    if recursive:
        iterator = path.rglob("*")
    else:
        iterator = path.iterdir()

    for candidate in iterator:
        if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_SUFFIXES:
            yield candidate


def iter_db_raw_snippets(db_path: Path) -> Iterator[ConversationItem]:
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, raw_snippet, COALESCE(evidence, '')
            FROM records
            WHERE raw_snippet IS NOT NULL AND TRIM(raw_snippet) != ''
            """
        )
        for record_id, raw_snippet, evidence in cursor.fetchall():
            conversation = str(raw_snippet).strip()
            if not conversation:
                continue
            yield ConversationItem(
                conversation_id=f"raw-{record_id}",
                conversation=conversation,
                source=f"db:{record_id}:{evidence}",
            )
    finally:
        conn.close()


def iter_conversations(input_path: Optional[Path], recursive: bool, from_db_raw_snippets: bool) -> Iterator[ConversationItem]:
    seen: set[str] = set()

    if input_path:
        for file_path in iter_input_files(input_path, recursive):
            for item in load_conversations_from_path(file_path):
                digest = sha1(item.conversation.encode("utf-8")).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                yield item

    if from_db_raw_snippets:
        for item in iter_db_raw_snippets(config.db_path):
            digest = sha1(item.conversation.encode("utf-8")).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            yield item


def backfill(items: Iterator[ConversationItem], skip_structured: bool) -> dict[str, int]:
    analyzer = MemoryAnalyzer()
    writer = MemoryWriter()

    stats = {
        "conversations_seen": 0,
        "structured_written": 0,
        "verbatim_written": 0,
        "failed": 0,
    }

    for item in items:
        stats["conversations_seen"] += 1
        try:
            if skip_structured:
                verbatim_ids = writer.write_verbatim(
                    conversation=item.conversation,
                    source=item.source,
                    conversation_id=item.conversation_id,
                )
                stats["verbatim_written"] += len(verbatim_ids)
                continue

            analysis = analyzer.analyze(
                conversation=item.conversation,
                conversation_id=item.conversation_id,
            )
            result = writer.write_analysis_with_verbatim(
                analysis=analysis,
                conversation=item.conversation,
                conversation_id=item.conversation_id,
            )
            stats["structured_written"] += len(result["structured_ids"])
            stats["verbatim_written"] += len(result["verbatim_ids"])
        except Exception as exc:
            stats["failed"] += 1
            print(f"[WARN] 回填失败: {item.conversation_id} ({exc})")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="LocalMind 历史记忆回填脚本")
    parser.add_argument("--input", type=str, help="历史对话文件或目录")
    parser.add_argument("--recursive", action="store_true", help="递归扫描输入目录")
    parser.add_argument("--from-db-raw-snippets", action="store_true", help="从 records.raw_snippet 回填")
    parser.add_argument("--skip-structured", action="store_true", help="只回填 verbatim，不做结构化提取")
    args = parser.parse_args()

    input_path = Path(args.input).resolve() if args.input else None
    if not input_path and not args.from_db_raw_snippets:
        parser.error("至少提供 --input 或 --from-db-raw-snippets 其中之一")

    items = iter_conversations(
        input_path=input_path,
        recursive=args.recursive,
        from_db_raw_snippets=args.from_db_raw_snippets,
    )
    stats = backfill(items, skip_structured=args.skip_structured)

    print("=" * 60)
    print("LocalMind 回填结果")
    print("=" * 60)
    print(f"扫描对话: {stats['conversations_seen']}")
    print(f"结构化写入: {stats['structured_written']}")
    print(f"Verbatim 写入: {stats['verbatim_written']}")
    print(f"失败数: {stats['failed']}")

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
