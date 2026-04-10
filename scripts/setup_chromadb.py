#!/usr/bin/env python3
"""
LocalMind ChromaDB 初始化脚本
验证/创建 ChromaDB 向量数据库
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma_db"


def check_chromadb_installed() -> bool:
    """检查 ChromaDB 是否已安装"""
    try:
        import chromadb
        return True
    except ImportError:
        return False


def install_chromadb() -> bool:
    """安装 ChromaDB"""
    import subprocess
    print("[*] 正在安装 ChromaDB...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "chromadb", "-q"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def init_chromadb(persist_dir: Path) -> bool:
    """初始化 ChromaDB"""
    try:
        import chromadb
                
        # 创建持久化目录
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化 ChromaDB 客户端（使用 PersistentClient 实现持久化）
        client = chromadb.PersistentClient(path=str(persist_dir))
        
        # 创建或获取 collection
        collection = client.get_or_create_collection(
            name="localmind_memories",
            metadata={"description": "LocalMind 结构化记忆向量库"}
        )
        
        print(f"[+] ChromaDB 初始化完成")
        print(f"    路径：{persist_dir}")
        print(f"    Collection：localmind_memories")
        
        # 测试添加和查询
        test_id = "test_vector"
        test_embedding = [0.1] * 768  # 占位向量，实际维度由模型决定
        test_metadata = {"dimension": "test", "content": "测试记录"}
        
        collection.add(
            ids=[test_id],
            embeddings=[test_embedding],
            metadatas=[test_metadata]
        )
        
        results = collection.query(
            query_embeddings=[test_embedding],
            n_results=1
        )
        
        # 清理测试数据
        collection.delete(ids=[test_id])
        
        print("[+] 向量添加和查询测试通过")
        return True
        
    except Exception as e:
        print(f"[-] ChromaDB 初始化失败：{e}")
        return False


def check_ollama_for_embedding() -> bool:
    """验证 Ollama 是否能提供 embedding 服务（用于生成向量）"""
    try:
        import requests
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": "test"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding", [])
            return len(embedding) > 0
        return False
    except Exception:
        return False


def main():
    print("=" * 50)
    print("LocalMind - ChromaDB 环境检查")
    print("=" * 50)
    
    # 检查 ChromaDB
    print("\n[*] 检查 ChromaDB 安装...")
    if not check_chromadb_installed():
        print("[-] ChromaDB 未安装")
        if install_chromadb():
            print("[+] ChromaDB 安装成功")
        else:
            print("[-] ChromaDB 安装失败，请手动执行：pip install chromadb")
            sys.exit(1)
    else:
        print("[+] ChromaDB 已安装")
    
    # 检查 Ollama embedding
    print("\n[*] 检查 Ollama Embedding 服务...")
    if check_ollama_for_embedding():
        print("[+] Ollama Embedding 服务正常")
    else:
        print("[-] Ollama Embedding 服务不可用")
        print("    请先运行 scripts/setup_ollama.py 检查 Ollama")
    
    # 初始化 ChromaDB
    print(f"\n[*] 初始化 ChromaDB...")
    if init_chromadb(CHROMA_PATH):
        print("\n✅ ChromaDB 环境检查通过！")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
