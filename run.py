#!/usr/bin/env python3
"""
多模态 Agent 联邦 MVP — 统一启动入口 (12 Agent + Gateway)

启动方式:
  python run.py              # 启动所有服务 (Gateway + 12 Agent)
  python run.py --gateway    # 仅启动 Gateway
  python run.py --agents     # 仅启动 12 个 Agent 服务
  python run.py --layer design    # 仅启动设计层 (8001-8003)
  python run.py --layer engineering  # 仅启动工程层 (8004-8007)
  python run.py --layer strategy     # 仅启动战略层 (8008-8010)
  python run.py --layer foundation   # 仅启动基础层 (8011-8012)
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# 确保项目根目录在 Python path
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
import structlog
from dotenv import load_dotenv

load_dotenv()

# 配置日志: 使用标准 logging + structlog 简洁输出
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def create_agent_app(agent_class, name: str, port: int):
    """为 Agent 创建独立的 FastAPI 应用"""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from src.api.schemas import A2ATaskRequest

    agent = agent_class()
    app = FastAPI(title=f"Agent: {name}")

    @app.get("/.well-known/agent.json")
    async def card():
        return agent.get_agent_card()

    @app.post("/a2a")
    async def handle(request: A2ATaskRequest):
        result = await agent.handle_a2a_task(request)
        return result.model_dump()

    @app.get("/health")
    async def health():
        return {"status": "healthy", "agent": name}

    @app.exception_handler(Exception)
    async def global_error(request: Request, exc: Exception):
        logger.error(f"{name}_error", error=str(exc))
        return JSONResponse(status_code=500, content={"error": str(exc)})

    return app


async def run_agent(agent_class, name: str, port: int):
    """在后台运行 Agent 服务"""
    app = create_agent_app(agent_class, name, port)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    logger.info(f"agent_starting", name=name, port=port)
    await server.serve()


async def run_gateway(port: int = 8000):
    """运行 Gateway (主 API 服务)"""
    from src.api.routes import create_app
    from pathlib import Path

    app = create_app()

    dashboard_path = Path(__file__).parent / "src" / "ui" / "dashboard.html"
    if dashboard_path.exists():
        from fastapi.responses import HTMLResponse

        @app.get("/")
        @app.get("/dashboard")
        async def dashboard():
            return HTMLResponse(dashboard_path.read_text(encoding="utf-8"))

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    logger.info("gateway_starting", port=port, dashboard=f"http://127.0.0.1:{port}/dashboard")
    await server.serve()


# ── 12 Agent 注册表: (类, 名称, 端口) ──

AGENTS = {
    # 设计层
    "multimodal": ("src.agents.multimodal_agent", "MultimodalAgent", "multimodal_design_agent", 8001),
    "ux":          ("src.agents.ux_agent", "UXAgent", "ux_interaction_agent", 8002),
    "brand":       ("src.agents.brand_agent", "BrandAgent", "brand_creative_agent", 8003),
    # 工程层
    "code":        ("src.agents.code_agent", "CodeAgent", "secure_code_agent", 8004),
    "test":        ("src.agents.test_agent", "TestAgent", "testing_qa_agent", 8005),
    "devops":      ("src.agents.devops_agent", "DevOpsAgent", "devops_deploy_agent", 8006),
    "review":      ("src.agents.review_agent", "ReviewAgent", "code_review_agent", 8007),
    # 战略层
    "architect":   ("src.agents.architect_agent", "ArchitectAgent", "project_architect_agent", 8008),
    "prompt":      ("src.agents.prompt_agent", "PromptAgent", "prompt_engineer_agent", 8009),
    "crew":        ("src.agents.crew_agent", "CrewAgent", "crew_collaboration_agent", 8010),
    # 基础层
    "knowledge":   ("src.agents.knowledge_agent", "KnowledgeAgent", "knowledge_rag_agent", 8011),
    "security":    ("src.agents.security_agent", "SecurityAgent", "security_audit_agent", 8012),
}

LAYERS = {
    "design":      ["multimodal", "ux", "brand"],
    "engineering": ["code", "test", "devops", "review"],
    "strategy":    ["architect", "prompt", "crew"],
    "foundation":  ["knowledge", "security"],
}


def _import_agent(key: str):
    """懒加载 Agent 类"""
    import importlib
    module_path, class_name, _, _ = AGENTS[key]
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


async def run_all():
    """启动全部 12 Agent + Gateway"""
    tasks = [run_gateway(8000)]
    for key in AGENTS:
        _, _, name, port = AGENTS[key]
        agent_cls = _import_agent(key)
        tasks.append(run_agent(agent_cls, name, port))
    await asyncio.gather(*tasks)


async def run_agents_only(layer: str = None):
    """启动 Agent 服务 (可选指定层)"""
    keys = LAYERS.get(layer, list(AGENTS.keys())) if layer else list(AGENTS.keys())
    tasks = []
    for key in keys:
        _, _, name, port = AGENTS[key]
        agent_cls = _import_agent(key)
        tasks.append(run_agent(agent_cls, name, port))
    await asyncio.gather(*tasks)


def main():
    parser = argparse.ArgumentParser(description="多模态 Agent 联邦 — 12 Agent 版")
    parser.add_argument("--gateway", action="store_true", help="仅启动 Gateway")
    parser.add_argument("--agents", action="store_true", help="仅启动 12 Agent 服务")
    parser.add_argument("--layer", choices=list(LAYERS.keys()), help="仅启动指定层")
    parser.add_argument("--port", type=int, default=8000, help="Gateway 端口")

    args = parser.parse_args()

    print("=" * 65)
    print("  多模态 Agent 联邦 v2.0 — 12 Agent 四层架构")
    print("  Agent Federation — 哪个 Agent 能力强就用哪个")
    print("=" * 65)

    if args.agents or args.layer:
        layer_info = f" ({args.layer} 层)" if args.layer else ""
        print(f"\n  启动 Agent 服务{layer_info}...")
        layout = [
            ("设计层", ["multimodal", "ux", "brand"]),
            ("工程层", ["code", "test", "devops", "review"]),
            ("战略层", ["architect", "prompt", "crew"]),
            ("基础层", ["knowledge", "security"]),
        ]
        keys_to_run = LAYERS.get(args.layer, list(AGENTS.keys())) if args.layer else list(AGENTS.keys())
        for layer_name, layer_keys in layout:
            active = [k for k in layer_keys if k in keys_to_run]
            if active:
                print(f"  [{layer_name}]")
                for k in active:
                    _, _, name, port = AGENTS[k]
                    print(f"    {name:<28} http://127.0.0.1:{port}")
        print()
        asyncio.run(run_agents_only(args.layer))

    elif args.gateway:
        print(f"\n  启动 Gateway...")
        print(f"  - API       : http://127.0.0.1:{args.port}")
        print(f"  - Dashboard : http://127.0.0.1:{args.port}/dashboard")
        print(f"  - API Docs  : http://127.0.0.1:{args.port}/docs")
        print()
        asyncio.run(run_gateway(args.port))

    else:
        print(f"\n  启动全部服务 (Gateway + 12 Agent)...")
        print(f"  [Gateway]")
        print(f"    Dashboard   : http://127.0.0.1:8000/dashboard")
        print(f"    API Docs    : http://127.0.0.1:8000/docs")
        layout = [
            ("设计层", ["multimodal", "ux", "brand"]),
            ("工程层", ["code", "test", "devops", "review"]),
            ("战略层", ["architect", "prompt", "crew"]),
            ("基础层", ["knowledge", "security"]),
        ]
        for layer_name, layer_keys in layout:
            print(f"  [{layer_name}]")
            for k in layer_keys:
                _, _, name, port = AGENTS[k]
                print(f"    {name:<28} http://127.0.0.1:{port}")
        print()
        asyncio.run(run_all())


if __name__ == "__main__":
    main()
