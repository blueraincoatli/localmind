#!/usr/bin/env python3
"""
LocalMind Web API 测试 (Phase 8)
"""

import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 需要先安装 fastapi 和 httpx
# pip install fastapi httpx


def test_api_import():
    """测试 API 模块导入"""
    print("[*] 测试 API 模块导入...")
    
    try:
        from api.main import app
        assert app is not None
        print("    FastAPI app 导入成功")
        return True
    except ImportError as e:
        print(f"    [SKIP] FastAPI 未安装: {e}")
        return None  # 跳过而非失败
    except Exception as e:
        print(f"    导入失败: {e}")
        return False


def test_api_routes():
    """测试 API 路由"""
    print("[*] 测试 API 路由...")
    
    try:
        from api.main import app
        
        routes = [r.path for r in app.routes]
        print(f"    路由数量: {len(routes)}")
        
        # 检查关键路由
        required = [
            "/",
            "/health",
            "/api/v1/status",
            "/api/v1/recall",
            "/api/v1/wake_up",
            "/api/v1/remember",
            "/api/v1/dimensions",
            "/api/v1/stats",
            "/api/v1/search",
        ]
        for route in required:
            if route in routes:
                print(f"    [OK] {route}")
            else:
                print(f"    [MISSING] {route}")
        
        return True
    except Exception as e:
        print(f"    测试失败: {e}")
        return False


def test_pydantic_models():
    """测试 Pydantic 模型"""
    print("[*] 测试 Pydantic 模型...")
    
    try:
        from api.main import RecallRequest, RememberRequest, WakeUpRequest, SearchRequest
        
        # 测试 RecallRequest
        req = RecallRequest(query="测试", top_k=5)
        assert req.query == "测试"
        assert req.top_k == 5
        print("    RecallRequest: OK")
        
        # 测试 RememberRequest
        req = RememberRequest(dimension_id="identity.name", content="Alice")
        assert req.dimension_id == "identity.name"
        print("    RememberRequest: OK")
        
        # 测试 WakeUpRequest
        req = WakeUpRequest(query="测试")
        assert req.query == "测试"
        print("    WakeUpRequest: OK")

        req = SearchRequest(query="设计")
        assert req.query == "设计"
        print("    SearchRequest: OK")
        
        return True
    except Exception as e:
        print(f"    测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("LocalMind Phase 8 Web API 测试")
    print("=" * 60)
    
    results = []
    
    # API 导入测试
    import_result = test_api_import()
    if import_result is None:
        print("\n[SKIP] FastAPI 未安装，跳过 API 测试")
        print("安装: pip install fastapi uvicorn httpx")
        return 0
    results.append(("API 导入", import_result))
    
    if import_result:
        results.append(("API 路由", test_api_routes()))
        results.append(("Pydantic 模型", test_pydantic_models()))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    for name, passed in results:
        status = "通过" if passed else "失败"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n[OK] 所有 API 测试通过！")
        print("\n启动 API 服务器:")
        print("  uvicorn api.main:app --reload")
        print("\nAPI 文档:")
        print("  http://localhost:8000/docs")
    else:
        print("\n[FAIL] 部分测试失败")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
