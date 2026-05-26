#!/usr/bin/env python3
"""首次启动校验 — 检查 Python 版本、依赖、API Key 配置"""

import sys

def main():
    all_ok = True

    # 1. Python 版本
    v = sys.version_info
    if v >= (3, 11):
        print(f"  [PASS] Python {v.major}.{v.minor}.{v.micro}")
    else:
        print(f"  [FAIL] Python {v.major}.{v.minor}.{v.micro} — 需要 3.11+")
        all_ok = False

    # 2. 核心依赖
    for mod, name in [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic_settings", "pydantic-settings"),
        ("httpx", "httpx"),
        ("structlog", "structlog"),
        ("dotenv", "python-dotenv"),
        ("langgraph", "langgraph"),
        ("click", "click"),
        ("rich", "rich"),
    ]:
        try:
            __import__(mod)
            print(f"  [PASS] {name}")
        except ImportError:
            print(f"  [FAIL] {name} — 未安装，运行: pip install -e .")
            all_ok = False

    # 3. 可选依赖
    for mod, name in [
        ("anthropic", "anthropic"),
        ("google.genai", "google-genai"),
        ("markitdown", "markitdown"),
    ]:
        try:
            __import__(mod)
            print(f"  [PASS] {name}")
        except ImportError:
            print(f"  [WARN] {name} — 可选依赖未安装，部分功能不可用")

    # 4. API Key
    from dotenv import load_dotenv
    import os
    load_dotenv()

    has_key = False
    for var in ["DEEPSEEK_KEY", "GLM_KEY", "GEMINI_KEY"]:
        val = os.getenv(var, "")
        if val and val != f"sk-your-{var.lower().replace('_', '-')}-here" and not val.startswith("your-"):
            print(f"  [PASS] {var} 已配置")
            has_key = True

    if not has_key:
        print(f"  [WARN] 未检测到有效的 API Key")
        print(f"         请复制 .env.example 为 .env 并填入 API Key:")
        print(f"           cp .env.example .env")
        print(f"         获取 DeepSeek Key: https://platform.deepseek.com/api_keys")

    # 5. .env 文件
    from pathlib import Path
    env_file = Path(".env")
    if env_file.exists():
        print(f"  [PASS] .env 文件存在")
    else:
        print(f"  [WARN] .env 文件不存在，将使用默认值（不含 API Key）")
        print(f"         运行: cp .env.example .env")

    if all_ok:
        print("\n  校验通过，运行 python run.py 启动服务")
    else:
        print("\n  请先修复以上 FAIL 项再启动")
        sys.exit(1)


if __name__ == "__main__":
    main()
