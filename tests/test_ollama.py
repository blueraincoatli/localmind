#!/usr/bin/env python3
"""
LocalMind Ollama 测试
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests


def test_ollama_running():
    """测试 Ollama 服务是否运行"""
    print("[*] 检查 Ollama 服务...")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        assert response.status_code == 200
        print("[+] Ollama 服务运行正常")
        return True
    except Exception as e:
        print(f"[-] Ollama 服务不可用：{e}")
        return False


def test_embed_model():
    """测试 embedding 模型"""
    print("[*] 测试 nomic-embed-text 模型...")
    
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": "测试文本"},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        embedding = data.get("embedding", [])
        assert len(embedding) > 0, "应该返回非空向量"
        print(f"[+] Embedding 测试成功！向量维度：{len(embedding)}")
        return True
    except Exception as e:
        print(f"[-] Embedding 测试失败：{e}")
        return False


def test_text_generation():
    """测试文本生成（用于 LLM 分析）"""
    print("[*] 测试文本生成（LLM）...")
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:7b",  # 默认模型
                "prompt": "你好，请回复 OK",
                "stream": False
            },
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        print(f"[+] LLM 测试成功！回复：{data['response'][:50]}")
        return True
    except Exception as e:
        print(f"[-] LLM 测试失败：{e}")
        return False


def main():
    print("=" * 50)
    print("LocalMind Ollama 环境测试")
    print("=" * 50)
    
    if not test_ollama_running():
        print("\n[-] Ollama 服务未运行，请先启动：ollama serve")
        sys.exit(1)
    
    if not test_embed_model():
        print("\n[-] Embedding 模型不可用，请先安装：ollama pull nomic-embed-text")
        sys.exit(1)
    
    # LLM 测试是可选的
    print("\n[*] LLM 测试（可选）...")
    test_text_generation()
    
    print("\n✅ Ollama 环境检查完成！")


if __name__ == "__main__":
    main()
