#!/usr/bin/env python3
"""
LocalMind MCP 服务器 (Phase 5)
提供 MemPalace 级别的工具生态，支持 Claude Code / Cursor 等原生集成

工具列表:
- localmind_status: 记忆库概览
- localmind_wake_up: 分层唤醒（L0+L1+L2）
- localmind_recall: 深度召回
- localmind_remember: 手动写入记忆
- localmind_search: 语义搜索
- localmind_list_dimensions: 列出维度
- localmind_get_dimension: 获取维度详情
- localmind_stats: 记忆统计
- localmind_add_critical_fact: 添加关键事实
- localmind_get_stats: 获取统计信息

使用方法:
    # 安装到 Claude Code
    claude mcp add localmind -- python -m localmind.mcp_server
    
    # 或直接运行
    python -m localmind.mcp_server
"""

import json
import logging
from typing import Any
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import config
from .db import Database
from .layers import LayerManager, wake_up
from .models import MemoryRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mcp] %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


class LocalMindContext:
    """MCP 服务器上下文"""
    def __init__(self):
        self.db = Database()
        self.layer_manager = LayerManager(self.db)


@asynccontextmanager
async def app_lifespan(server: Server) -> AsyncIterator[LocalMindContext]:
    """应用生命周期管理"""
    logger.info("LocalMind MCP Server 启动")
    context = LocalMindContext()
    try:
        yield context
    finally:
        logger.info("LocalMind MCP Server 关闭")


# 创建 MCP 服务器
app = Server("localmind", lifespan=app_lifespan)


# ========== 工具定义 ==========

TOOLS = [
    Tool(
        name="localmind_status",
        description="获取 LocalMind 记忆库的整体状态概览，包括记忆数量、维度统计等",
        inputSchema={"type": "object", "properties": {}}
    ),
    Tool(
        name="localmind_wake_up",
        description="分层冷启动唤醒，返回 L0(身份) + L1(关键) + L2(上下文) 的记忆内容",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "当前对话查询，用于加载相关的 L2 上下文"
                },
                "conversation_id": {
                    "type": "string",
                    "description": "对话 ID（可选）"
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="localmind_recall",
        description="深度召回记忆，使用5路召回引擎（语义+历史+热度+共现+空白检测）",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "查询内容"
                },
                "conversation_id": {
                    "type": "string",
                    "description": "对话 ID（可选）"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回维度数量",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="localmind_search",
        description="语义搜索记忆内容，基于向量相似度",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "n_results": {
                    "type": "integer",
                    "description": "返回结果数",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="localmind_remember",
        description="手动写入一条记忆到指定维度",
        inputSchema={
            "type": "object",
            "properties": {
                "dimension_id": {
                    "type": "string",
                    "description": "维度 ID，如 identity.personality"
                },
                "content": {
                    "type": "string",
                    "description": "记忆内容"
                },
                "evidence": {
                    "type": "string",
                    "description": "证据/来源（可选）"
                },
                "confidence": {
                    "type": "number",
                    "description": "置信度 0-1（可选）",
                    "default": 0.8
                }
            },
            "required": ["dimension_id", "content"]
        }
    ),
    Tool(
        name="localmind_list_dimensions",
        description="列出所有可用的记忆维度",
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "指定域过滤（可选），如 identity"
                }
            }
        }
    ),
    Tool(
        name="localmind_get_dimension",
        description="获取指定维度的详细信息",
        inputSchema={
            "type": "object",
            "properties": {
                "dimension_id": {
                    "type": "string",
                    "description": "维度 ID，如 identity.personality"
                }
            },
            "required": ["dimension_id"]
        }
    ),
    Tool(
        name="localmind_add_critical_fact",
        description="添加关键事实到 L0(身份) 或 L1(关键) 层",
        inputSchema={
            "type": "object",
            "properties": {
                "fact_type": {
                    "type": "string",
                    "description": "事实类型: identity 或 critical",
                    "enum": ["identity", "critical"]
                },
                "content": {
                    "type": "string",
                    "description": "事实内容"
                },
                "priority": {
                    "type": "integer",
                    "description": "优先级（越高越重要）",
                    "default": 0
                }
            },
            "required": ["fact_type", "content"]
        }
    ),
    Tool(
        name="localmind_get_stats",
        description="获取详细的记忆统计数据",
        inputSchema={"type": "object", "properties": {}}
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用工具"""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """处理工具调用"""
    ctx = app.request_context.lifespan_context
    
    try:
        if name == "localmind_status":
            return await handle_status(ctx)
        elif name == "localmind_wake_up":
            return await handle_wake_up(ctx, arguments)
        elif name == "localmind_recall":
            return await handle_recall(ctx, arguments)
        elif name == "localmind_search":
            return await handle_search(ctx, arguments)
        elif name == "localmind_remember":
            return await handle_remember(ctx, arguments)
        elif name == "localmind_list_dimensions":
            return await handle_list_dimensions(ctx, arguments)
        elif name == "localmind_get_dimension":
            return await handle_get_dimension(ctx, arguments)
        elif name == "localmind_add_critical_fact":
            return await handle_add_critical_fact(ctx, arguments)
        elif name == "localmind_get_stats":
            return await handle_get_stats(ctx)
        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]
    except Exception as e:
        logger.error(f"工具调用失败 {name}: {e}")
        return [TextContent(type="text", text=f"错误: {str(e)}")]


# ========== 工具处理函数 ==========

async def handle_status(ctx: LocalMindContext) -> list[TextContent]:
    """处理状态查询"""
    stats = ctx.db.get_stats()
    
    text = f"""LocalMind 记忆库状态
==================

总记录数: {stats.get('total_records', 0)}
维度总数: {stats.get('total_dimensions', 0)}

各域分布:
"""
    for domain, count in stats.get('records_by_domain', {}).items():
        text += f"  - {domain}: {count} 条\n"
    
    text += f"\n热门维度:\n"
    for dim in stats.get('top_dimensions', [])[:5]:
        text += f"  - {dim['dimension']}: {dim['uses']} 次使用\n"
    
    return [TextContent(type="text", text=text)]


async def handle_wake_up(ctx: LocalMindContext, args: dict) -> list[TextContent]:
    """处理分层唤醒"""
    query = args.get("query", "")
    conversation_id = args.get("conversation_id")
    
    wake_ctx = ctx.layer_manager.wake_up(query, conversation_id)
    
    text = f"""分层唤醒结果
===============

L0 (身份认知): {wake_ctx.l0.token_estimate if wake_ctx.l0 else 0} tokens
{'=' * 40}
{wake_ctx.l0.content if wake_ctx.l0 else '(无)'}

L1 (关键记忆): {wake_ctx.l1.token_estimate if wake_ctx.l1 else 0} tokens
{'=' * 40}
{wake_ctx.l1.content if wake_ctx.l1 else '(无)'}

L2 (上下文): {wake_ctx.l2.token_estimate if wake_ctx.l2 else 0} tokens
{'=' * 40}
{wake_ctx.l2.content if wake_ctx.l2 else '(无)'}

总计: {wake_ctx.total_tokens} tokens
"""
    return [TextContent(type="text", text=text)]


async def handle_recall(ctx: LocalMindContext, args: dict) -> list[TextContent]:
    """处理深度召回"""
    from recall.engine import RecallEngine
    
    query = args.get("query", "")
    conversation_id = args.get("conversation_id")
    top_k = args.get("top_k", 5)
    
    engine = RecallEngine(db=ctx.db)
    recall_ctx = engine.recall(query, conversation_id, top_k=top_k)
    
    text = f"深度召回结果: {len(recall_ctx.recalled_results)} 个维度\n"
    text += "=" * 50 + "\n\n"
    
    for i, result in enumerate(recall_ctx.recalled_results, 1):
        text += f"{i}. [{result.dimension_name}] (得分: {result.score:.3f})\n"
        if result.records:
            text += f"   内容: {result.records[0].content[:100]}...\n"
        text += "\n"
    
    return [TextContent(type="text", text=text)]


async def handle_search(ctx: LocalMindContext, args: dict) -> list[TextContent]:
    """处理语义搜索"""
    from .vector_store import VectorStore
    
    query = args.get("query", "")
    n_results = args.get("n_results", 5)
    
    try:
        vs = VectorStore()
        matches = vs.search(query, n_results=n_results)
        
        text = f"语义搜索结果: {len(matches)} 条\n"
        text += "=" * 50 + "\n\n"
        
        for i, match in enumerate(matches, 1):
            similarity = match.get("similarity", 0)
            content = match.get("content", "")[:150]
            dim_id = match.get("dimension_id", "unknown")
            text += f"{i}. [相似度: {similarity:.3f}] ({dim_id})\n"
            text += f"   {content}...\n\n"
        
        return [TextContent(type="text", text=text)]
    except Exception as e:
        return [TextContent(type="text", text=f"搜索失败: {e}")]


async def handle_remember(ctx: LocalMindContext, args: dict) -> list[TextContent]:
    """处理手动写入"""
    from write.writer import MemoryWriter
    
    dimension_id = args.get("dimension_id")
    content = args.get("content")
    evidence = args.get("evidence")
    confidence = args.get("confidence", 0.8)
    
    record = MemoryRecord(
        dimension_id=dimension_id,
        content=content,
        evidence=evidence,
        confidence=confidence
    )
    
    writer = MemoryWriter(db=ctx.db)
    success = writer.write(record)
    
    if success:
        # 同时更新关键事实
        ctx.layer_manager.update_from_records(record)
        text = f"✓ 记忆已写入\n维度: {dimension_id}\n内容: {content[:100]}...\nID: {record.id}"
    else:
        text = "✗ 写入失败"
    
    return [TextContent(type="text", text=text)]


async def handle_list_dimensions(ctx: LocalMindContext, args: dict) -> list[TextContent]:
    """处理维度列表"""
    domain = args.get("domain")
    
    if domain:
        dims = ctx.db.get_dimensions_by_domain(domain)
    else:
        dims = ctx.db.get_all_dimensions()
    
    text = f"维度列表 ({len(dims)} 个)\n"
    text += "=" * 50 + "\n\n"
    
    current_domain = None
    for dim in dims:
        if dim.domain != current_domain:
            current_domain = dim.domain
            text += f"\n【{dim.domain_name}】\n"
        text += f"  - {dim.id}: {dim.name}\n"
    
    return [TextContent(type="text", text=text)]


async def handle_get_dimension(ctx: LocalMindContext, args: dict) -> list[TextContent]:
    """处理维度详情"""
    dimension_id = args.get("dimension_id")
    dim = ctx.db.get_dimension(dimension_id)
    
    if not dim:
        return [TextContent(type="text", text=f"维度不存在: {dimension_id}")]
    
    # 获取该维度的记录
    records = ctx.db.get_records_by_dimension(dimension_id)
    
    text = f"""维度详情
========

ID: {dim.id}
名称: {dim.name}
域: {dim.domain} ({dim.domain_name})

召回焦点:
{dim.focus_prompt}

记忆记录 ({len(records)} 条):
"""
    for i, rec in enumerate(records[:5], 1):
        text += f"\n{i}. {rec.content[:100]}...\n"
        text += f"   置信度: {rec.confidence}, 使用: {rec.use_count}次\n"
    
    return [TextContent(type="text", text=text)]


async def handle_add_critical_fact(ctx: LocalMindContext, args: dict) -> list[TextContent]:
    """处理添加关键事实"""
    fact_type = args.get("fact_type")
    content = args.get("content")
    priority = args.get("priority", 0)
    
    success = ctx.layer_manager.add_critical_fact(fact_type, content, priority)
    
    if success:
        text = f"✓ 关键事实已添加\n类型: {fact_type}\n内容: {content}\n优先级: {priority}"
    else:
        text = "✗ 添加失败"
    
    return [TextContent(type="text", text=text)]


async def handle_get_stats(ctx: LocalMindContext) -> list[TextContent]:
    """处理统计查询"""
    db_stats = ctx.db.get_stats()
    layer_stats = ctx.layer_manager.get_stats()
    
    text = f"""LocalMind 详细统计
===================

数据库:
  - 总记录: {db_stats.get('total_records', 0)}
  - 维度数: {db_stats.get('total_dimensions', 0)}

分层:
  - L0 限制: {layer_stats['l0_max_tokens']} tokens
  - L1 限制: {layer_stats['l1_max_tokens']} tokens
  - L2 限制: {layer_stats['l2_max_tokens']} tokens
  - Identity 事实: {layer_stats.get('critical_facts', {}).get('identity', 0)}
  - Critical 事实: {layer_stats.get('critical_facts', {}).get('critical', 0)}

配置:
  - 分层唤醒: {'启用' if config.enable_layered_wake else '禁用'}
  - 模型: {config.llm_provider}
"""
    return [TextContent(type="text", text=text)]


# ========== 主入口 ==========

async def main():
    """主函数 - 启动 MCP 服务器"""
    async with stdio_server(server=app) as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
