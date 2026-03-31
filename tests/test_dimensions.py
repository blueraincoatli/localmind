#!/usr/bin/env python3
"""
LocalMind 维度定义测试
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from localmind.config import config


def test_dimensions_exist():
    """测试维度文件是否存在"""
    print("[*] 检查维度文件...")
    assert config.dimensions_dir.exists()
    
    expected_domains = [
        "identity", "psychology", "aesthetics",
        "career", "goals", "schedule", "misc", "relations"
    ]
    
    for domain in expected_domains:
        file_path = config.dimensions_dir / f"{domain}.yaml"
        assert file_path.exists(), f"缺失维度文件：{file_path}"
    
    print(f"[+] 所有 {len(expected_domains)} 个域的维度文件都存在")


def test_dimensions_structure():
    """测试维度文件结构"""
    print("[*] 测试维度文件结构...")
    
    total_dims = 0
    
    for yaml_file in sorted(config.dimensions_dir.glob("*.yaml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # 检查必要字段
        assert "domain" in data, f"{yaml_file.name} 缺少 domain"
        assert "domain_name" in data, f"{yaml_file.name} 缺少 domain_name"
        assert "dimensions" in data, f"{yaml_file.name} 缺少 dimensions"
        assert isinstance(data["dimensions"], list), f"{yaml_file.name} dimensions 应为列表"
        assert len(data["dimensions"]) > 0, f"{yaml_file.name} 至少有1个维度"
        
        # 检查每个维度
        for dim in data["dimensions"]:
            assert "id" in dim
            assert "name" in dim
            assert "focus_prompt" in dim
            assert dim["id"].startswith(data["domain"] + ".")
            total_dims += 1
        
        print(f"    {data['domain_name']}: {len(data['dimensions'])} 个维度")
    
    print(f"[+] 共 {total_dims} 个维度定义")


def test_all_dimensions_loadable():
    """测试所有维度可被数据库加载"""
    print("[*] 测试维度加载...")
    
    from localmind.db import Database
    
    db = Database()
    dims = db.get_all_dimensions()
    
    assert len(dims) > 0, "数据库应至少有1个维度"
    print(f"[+] 数据库中有 {len(dims)} 个维度")
    
    # 验证维度完整性
    dim_ids = [d.id for d in dims]
    for yaml_file in config.dimensions_dir.glob("*.yaml"):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for dim in data["dimensions"]:
            assert dim["id"] in dim_ids, f"缺失维度：{dim['id']}"
    
    print("[+] 所有 YAML 维度都已加载到数据库")


def main():
    print("=" * 50)
    print("LocalMind 维度定义测试")
    print("=" * 50)
    
    test_dimensions_exist()
    test_dimensions_structure()
    test_all_dimensions_loadable()
    
    print("\n✅ 维度定义测试全部通过！")


if __name__ == "__main__":
    main()
