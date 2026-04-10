"""
LocalMind Web API (Phase 8)
FastAPI 实现的 RESTful API

端点:
- POST /api/v1/recall        # 召回记忆
- POST /api/v1/remember      # 写入记忆
- GET  /api/v1/status        # 系统状态
- GET  /api/v1/dimensions    # 维度列表
- GET  /api/v1/stats         # 统计信息
- POST /api/v1/search        # 语义搜索
- POST /api/v1/wake_up       # 分层唤醒

运行:
    uvicorn api.main:app --reload
"""

import sys
from pathlib import Path
from typing import Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from localmind.config import config
from localmind.db import Database
from localmind.layers import LayerManager
from localmind.models import MemoryRecord
from recall.engine import RecallEngine
from recall.semantic import SemanticRecall
from write.writer import MemoryWriter

# 创建 FastAPI 应用
app = FastAPI(
    title="LocalMind API",
    description="结构化 AI 记忆系统 API",
    version="1.0.0",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db() -> Database:
    return Database()


def get_engine() -> RecallEngine:
    return RecallEngine()


def get_writer() -> MemoryWriter:
    return MemoryWriter()


def get_layer_manager() -> LayerManager:
    return LayerManager()


def get_semantic() -> SemanticRecall:
    return SemanticRecall()


# ========== Pydantic 模型 ==========

class RecallRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    top_k: int = 5
    use_layered: bool = True


class RecallResponse(BaseModel):
    query: str
    total_tokens: int
    results: List[dict]
    layered_context: Optional[str] = None


class RememberRequest(BaseModel):
    dimension_id: str
    content: str
    evidence: Optional[str] = None
    confidence: float = 0.8


class RememberResponse(BaseModel):
    success: bool
    record_id: Optional[str] = None


class WakeUpRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None


class WakeUpResponse(BaseModel):
    l0_tokens: int
    l1_tokens: int
    l2_tokens: int
    total_tokens: int
    context: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResponse(BaseModel):
    query: str
    results: List[dict]


# ========== API 端点 ==========

@app.get("/")
async def root():
    """根路径 - API 信息"""
    return {
        "name": "LocalMind API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/status")
async def get_status():
    """获取系统状态"""
    try:
        db = get_db()
        layer_manager = get_layer_manager()
        stats = db.get_stats()
        layer_stats = layer_manager.get_stats()
        
        return {
            "status": "running",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "stats": {**stats, **layer_stats}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recall", response_model=RecallResponse)
async def recall_memory(request: RecallRequest):
    """召回记忆"""
    try:
        engine = get_engine()
        if request.use_layered:
            wake_ctx, full_ctx = engine.recall_with_wake(
                query=request.query,
                conversation_id=request.conversation_id,
                top_k=request.top_k
            )
            
            results = []
            for r in full_ctx.recalled_results:
                results.append({
                    "dimension_id": r.dimension_id,
                    "dimension_name": r.dimension_name,
                    "domain": r.domain,
                    "score": r.score,
                    "records": [
                        {"content": rec.content, "confidence": rec.confidence}
                        for rec in r.records[:3]
                    ]
                })
            
            return RecallResponse(
                query=request.query,
                total_tokens=wake_ctx.total_tokens,
                results=results,
                layered_context=wake_ctx.to_prompt()
            )
        else:
            ctx = engine.recall(
                query=request.query,
                conversation_id=request.conversation_id,
                top_k=request.top_k
            )
            
            results = []
            for r in ctx.recalled_results:
                results.append({
                    "dimension_id": r.dimension_id,
                    "dimension_name": r.dimension_name,
                    "domain": r.domain,
                    "score": r.score,
                    "records": [
                        {"content": rec.content, "confidence": rec.confidence}
                        for rec in r.records[:3]
                    ]
                })
            
            return RecallResponse(
                query=request.query,
                total_tokens=0,
                results=results,
                layered_context=None
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/wake_up", response_model=WakeUpResponse)
async def wake_up(request: WakeUpRequest):
    """分层唤醒"""
    try:
        layer_manager = get_layer_manager()
        wake_ctx = layer_manager.wake_up(
            query=request.query,
            conversation_id=request.conversation_id
        )
        
        return WakeUpResponse(
            l0_tokens=wake_ctx.l0.token_estimate if wake_ctx.l0 else 0,
            l1_tokens=wake_ctx.l1.token_estimate if wake_ctx.l1 else 0,
            l2_tokens=wake_ctx.l2.token_estimate if wake_ctx.l2 else 0,
            total_tokens=wake_ctx.total_tokens,
            context=wake_ctx.to_prompt()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/remember", response_model=RememberResponse)
async def remember(request: RememberRequest):
    """写入记忆"""
    try:
        writer = get_writer()
        record = MemoryRecord(
            dimension_id=request.dimension_id,
            content=request.content,
            evidence=request.evidence,
            confidence=request.confidence
        )
        
        success = writer.write(record)
        
        return RememberResponse(
            success=success,
            record_id=record.id if success else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/dimensions")
async def list_dimensions(domain: Optional[str] = None):
    """列出维度"""
    try:
        db = get_db()
        if domain:
            dims = db.get_dimensions_by_domain(domain)
        else:
            dims = db.get_all_dimensions()
        
        return {
            "count": len(dims),
            "dimensions": [
                {"id": d.id, "name": d.name, "domain": d.domain}
                for d in dims
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats")
async def get_stats():
    """获取统计"""
    try:
        db = get_db()
        layer_manager = get_layer_manager()
        return {
            "database": db.get_stats(),
            "layers": layer_manager.get_stats(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/search", response_model=SearchResponse)
async def search_memory(request: SearchRequest):
    """搜索记忆。优先语义检索，embedding 不可用时自动退化到词面匹配。"""
    try:
        db = get_db()
        semantic = get_semantic()
        dimensions = db.get_all_dimensions()
        results = semantic.recall_global(
            query=request.query,
            dimensions=dimensions,
            top_k=request.top_k,
        )

        payload: list[dict[str, Any]] = []
        for result in results:
            payload.append({
                "dimension_id": result.dimension_id,
                "dimension_name": result.dimension_name,
                "domain": result.domain,
                "score": result.score,
                "records": [
                    {
                        "id": record.id,
                        "content": record.content,
                        "confidence": record.confidence,
                    }
                    for record in result.records[:3]
                ],
            })

        return SearchResponse(query=request.query, results=payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 启动
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
