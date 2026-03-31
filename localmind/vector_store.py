"""
LocalMind 向量存储模块
封装 ChromaDB 操作，提供语义召回能力
"""

import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .config import config


class VectorStore:
    """ChromaDB 向量存储封装"""
    
    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir or config.chroma_path
        self._client = None
        self._collection = None
    
    def _get_client(self):
        """获取 ChromaDB 客户端"""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings
            
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            
            self._client = chromadb.Client(Settings(
                persist_directory=str(self.persist_dir),
                anonymized_telemetry=False
            ))
        return self._client
    
    def get_collection(self):
        """获取记忆 collection"""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name="localmind_memories",
                metadata={"description": "LocalMind 结构化记忆向量库"}
            )
        return self._collection
    
    def _generate_embedding(self, text: str) -> List[float]:
        """使用 Ollama 生成文本向量"""
        import requests
        
        response = requests.post(
            f"{config.ollama_base}/api/embeddings",
            json={
                "model": config.embed_model,
                "prompt": text
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["embedding"]
    
    def add_memory(
        self,
        dimension_id: str,
        content: str,
        record_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加记忆到向量库
        
        Args:
            dimension_id: 维度ID
            content: 记忆内容文本
            record_id: 对应的数据库记录ID
            metadata: 额外元数据
        
        Returns:
            embedding_id: ChromaDB 内的向量ID
        """
        collection = self.get_collection()
        
        # 生成向量
        embedding = self._generate_embedding(content)
        
        # 构建元数据
        meta = {
            "dimension_id": dimension_id,
            "record_id": record_id,
            "content": content
        }
        if metadata:
            meta.update(metadata)
        
        embedding_id = str(uuid.uuid4())
        
        collection.add(
            ids=[embedding_id],
            embeddings=[embedding],
            metadatas=[meta],
            documents=[content]
        )
        
        return embedding_id
    
    def search(
        self,
        query: str,
        dimension_filter: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        语义搜索记忆
        
        Args:
            query: 查询文本
            dimension_filter: 可选，限定搜索的维度ID
            n_results: 返回结果数量
        
        Returns:
            匹配的记录列表
        """
        collection = self.get_collection()
        
        # 生成查询向量
        query_embedding = self._generate_embedding(query)
        
        # 构建 where 过滤条件
        where = None
        if dimension_filter:
            where = {"dimension_id": dimension_filter}
        
        # 执行查询
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["metadatas", "documents", "distances"]
        )
        
        # 格式化结果
        matches = []
        if results["ids"] and len(results["ids"]) > 0:
            for i, embedding_id in enumerate(results["ids"][0]):
                matches.append({
                    "embedding_id": embedding_id,
                    "record_id": results["metadatas"][0][i].get("record_id"),
                    "dimension_id": results["metadatas"][0][i].get("dimension_id"),
                    "content": results["metadatas"][0][i].get("content"),
                    "distance": results["distances"][0][i],
                    "similarity": 1 - results["distances"][0][i]  # 转换为民义上的相似度
                })
        
        return matches
    
    def delete_memory(self, embedding_id: str) -> bool:
        """删除记忆"""
        collection = self.get_collection()
        try:
            collection.delete(ids=[embedding_id])
            return True
        except Exception:
            return False
    
    def get_memories_by_dimension(self, dimension_id: str) -> List[Dict[str, Any]]:
        """获取指定维度的所有记忆"""
        collection = self.get_collection()
        
        results = collection.get(
            where={"dimension_id": dimension_id},
            include=["metadatas", "documents"]
        )
        
        memories = []
        if results["ids"]:
            for i, embedding_id in enumerate(results["ids"]):
                memories.append({
                    "embedding_id": embedding_id,
                    "record_id": results["metadatas"][i].get("record_id"),
                    "dimension_id": results["metadatas"][i].get("dimension_id"),
                    "content": results["metadatas"][i].get("content"),
                })
        
        return memories
    
    def count_memories(self) -> int:
        """统计记忆总数"""
        collection = self.get_collection()
        return collection.count()
