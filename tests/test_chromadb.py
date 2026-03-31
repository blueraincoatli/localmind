#!/usr/bin/env python3
"""
LocalMind ChromaDB 测试
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_chromadb_import():
    """测试 ChromaDB 导入"""
    print("[*] 测试 ChromaDB 导入...")
    try:
        import chromadb
        print(f"[+] ChromaDB 版本：{chromadb.__version__}")
        return True
    except ImportError as e:
        print(f"[-] ChromaDB 未安装：{e}")
        return False


def test_chromadb_init():
    """测试 ChromaDB 初始化"""
    print("[*] 测试 ChromaDB 初始化...")
    
    from localmind.config import config
    from localmind.vector_store import VectorStore
    
    # 确保目录存在
    config.ensure_dirs()
    
    vs = VectorStore()
    collection = vs.get_collection()
    assert collection is not None
    print(f"[+] Collection 已创建/获取：{collection.name}")
    print(f"    当前向量数：{vs.count_memories()}")
    return True


def test_vector_add_search():
    """测试向量添加和搜索"""
    print("[*] 测试向量添加和搜索...")
    
    from localmind.vector_store import VectorStore
    import uuid
    
    vs = VectorStore()
    
    # 生成唯一ID
    test_id = str(uuid.uuid4())[:8]
    record_id = f"test_record_{test_id}"
    embedding_id = None
    
    try:
        # 添加测试向量
        embedding_id = vs.add_memory(
            dimension_id="identity.name",
            content="用户名叫张三",
            record_id=record_id
        )
        print(f"[+] 向量添加成功：{embedding_id}")
        
        # 搜索
        results = vs.search("这个人的名字是什么", n_results=3)
        assert len(results) > 0, "应该能找到至少1个结果"
        print(f"[+] 语义搜索成功，找到 {len(results)} 个结果")
        
        # 检查第一个结果的相似度
        top = results[0]
        print(f"    Top1 内容：{top['content']}")
        print(f"    相似度：{top['similarity']:.3f}")
        
        # 清理测试数据
        if embedding_id:
            vs.delete_memory(embedding_id)
            print("[+] 测试数据已清理")
        
        return True
        
    except Exception as e:
        print(f"[-] 向量操作失败：{e}")
        if embedding_id:
            try:
                vs.delete_memory(embedding_id)
            except:
                pass
        return False


def main():
    print("=" * 50)
    print("LocalMind ChromaDB 测试")
    print("=" * 50)
    
    if not test_chromadb_import():
        print("\n[-] 请先安装 ChromaDB：pip install chromadb")
        sys.exit(1)
    
    if not test_chromadb_init():
        print("\n[-] ChromaDB 初始化失败")
        sys.exit(1)
    
    if not test_vector_add_search():
        print("\n[-] 向量操作测试失败")
        sys.exit(1)
    
    print("\n✅ ChromaDB 测试全部通过！")


if __name__ == "__main__":
    main()
