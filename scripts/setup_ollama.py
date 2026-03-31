#!/usr/bin/env python3
"""
LocalMind Ollama 验证脚本
检查 Ollama 服务状态，验证 nomic-embed-text 模型可用性
"""

import requests
import sys
import json

OLLAMA_BASE = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"


def check_ollama_running() -> bool:
    """检查 Ollama 服务是否运行"""
    try:
        response = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_models() -> list:
    """列出已安装的模型"""
    try:
        response = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        return []
    except Exception:
        return []


def check_embed_model() -> bool:
    """检查 nomic-embed-text 是否已安装"""
    models = list_models()
    return any(EMBED_MODEL in m for m in models)


def pull_embed_model() -> bool:
    """拉取 nomic-embed-text 模型"""
    print(f"[*] 正在拉取 {EMBED_MODEL} 模型...")
    try:
        response = requests.post(
            f"{OLLAMA_BASE}/api/pull",
            json={"name": EMBED_MODEL},
            stream=True,
            timeout=300
        )
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    status = data.get("status", "")
                    if status == "success":
                        print(f"[+] 模型拉取成功")
                        return True
                    elif status == "pulling":
                        digest = data.get("digest", "")[:20]
                        print(f"\r[*] 拉取中... {digest}", end="", flush=True)
                except json.JSONDecodeError:
                    pass
        return check_embed_model()
    except Exception as e:
        print(f"[-] 拉取失败：{e}")
        return False


def test_embedding() -> bool:
    """测试 embedding 功能"""
    try:
        response = requests.post(
            f"{OLLAMA_BASE}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": "测试文本"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding", [])
            if embedding and len(embedding) > 0:
                print(f"[+] Embedding 测试成功！向量维度：{len(embedding)}")
                return True
        return False
    except Exception as e:
        print(f"[-] Embedding 测试失败：{e}")
        return False


def main():
    print("=" * 50)
    print("LocalMind - Ollama 环境检查")
    print("=" * 50)
    
    # 检查 Ollama 服务
    print(f"\n[*] 检查 Ollama 服务 ({OLLAMA_BASE})...")
    if not check_ollama_running():
        print("[-] Ollama 服务未运行！")
        print("    请先启动 Ollama：ollama serve")
        sys.exit(1)
    print("[+] Ollama 服务运行中")
    
    # 列出已安装模型
    models = list_models()
    print(f"\n[*] 已安装模型 ({len(models)} 个)：")
    for m in models:
        print(f"    - {m}")
    
    # 检查 nomic-embed-text
    print(f"\n[*] 检查 {EMBED_MODEL}...")
    if check_embed_model():
        print("[+] nomic-embed-text 已安装")
    else:
        print("[-] nomic-embed-text 未安装")
        print("[*] 正在安装...")
        if not pull_embed_model():
            print("[-] 模型安装失败，请手动执行：ollama pull nomic-embed-text")
            sys.exit(1)
    
    # 测试 embedding
    print("\n[*] 测试 Embedding 功能...")
    if test_embedding():
        print("\n✅ Ollama 环境检查通过！")
    else:
        print("\n[-] Embedding 功能测试失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
