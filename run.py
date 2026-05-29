#!/usr/bin/env python3
"""
多模态 Agent 联邦 MVP — 统一启动入口

启动方式:
  python run.py              # 启动所有服务 (Gateway + 3 Agent)
  python run.py --gateway    # 仅启动 Gateway
  python run.py --agents     # 仅启动 3 个 Agent 服务
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

    # 错误处理
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

    # 添加 Dashboard 路由
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


async def run_all():
    """启动所有服务"""
    from src.agents.multimodal_agent import MultimodalAgent
    from src.agents.code_agent import CodeAgent
    from src.agents.review_agent import ReviewAgent
    from src.agents.prompt_agent import PromptAgent
    from src.agents.architect_agent import ArchitectAgent

    # 并行启动 6 个服务
    await asyncio.gather(
        run_gateway(8000),
        run_agent(MultimodalAgent, "multimodal_design_agent", 8001),
        run_agent(CodeAgent, "secure_code_agent", 8002),
        run_agent(ReviewAgent, "code_review_agent", 8003),
        run_agent(PromptAgent, "prompt_engineer_agent", 8004),
        run_agent(ArchitectAgent, "project_architect_agent", 8005),
    )


def main():
    parser = argparse.ArgumentParser(description="多模态 Agent 联邦 MVP")
    parser.add_argument("--gateway", action="store_true", help="仅启动 Gateway")
    parser.add_argument("--agents", action="store_true", help="仅启动 Agent 服务")
    parser.add_argument("--port", type=int, default=8000, help="Gateway 端口")

    args = parser.parse_args()

    print("=" * 60)
    print("  多模态 Agent 联邦 MVP v1.0")
    print("  Agent Federation — 哪个 Agent 能力强就用哪个")
    print("=" * 60)

    if args.agents:
        from src.agents.multimodal_agent import MultimodalAgent
        from src.agents.code_agent import CodeAgent
        from src.agents.review_agent import ReviewAgent
        from src.agents.prompt_agent import PromptAgent
        from src.agents.architect_agent import ArchitectAgent

        print("\n  启动 Agent 服务...")
        print(f"  - Multimodal Agent   : http://127.0.0.1:8001")
        print(f"  - Code Agent         : http://127.0.0.1:8002")
        print(f"  - Review Agent       : http://127.0.0.1:8003")
        print(f"  - Prompt Engineer    : http://127.0.0.1:8004")
        print(f"  - Project Architect  : http://127.0.0.1:8005")
        print()

        asyncio.run(asyncio.gather(
            run_agent(MultimodalAgent, "multimodal_design_agent", 8001),
            run_agent(CodeAgent, "secure_code_agent", 8002),
            run_agent(ReviewAgent, "code_review_agent", 8003),
            run_agent(PromptAgent, "prompt_engineer_agent", 8004),
            run_agent(ArchitectAgent, "project_architect_agent", 8005),
        ))
    elif args.gateway:
        print(f"\n  启动 Gateway...")
        print(f"  - API       : http://127.0.0.1:{args.port}")
        print(f"  - Dashboard : http://127.0.0.1:{args.port}/dashboard")
        print(f"  - API Docs  : http://127.0.0.1:{args.port}/docs")
        print()
        asyncio.run(run_gateway(args.port))
    else:
        print(f"\n  启动全部服务...")
        print(f"  - Gateway           : http://127.0.0.1:8000")
        print(f"  - Dashboard         : http://127.0.0.1:8000/dashboard")
        print(f"  - API Docs          : http://127.0.0.1:8000/docs")
        print(f"  - Multimodal Agent  : http://127.0.0.1:8001")
        print(f"  - Code Agent        : http://127.0.0.1:8002")
        print(f"  - Review Agent      : http://127.0.0.1:8003")
        print(f"  - Prompt Engineer   : http://127.0.0.1:8004")
        print(f"  - Project Architect : http://127.0.0.1:8005")
        print()
        asyncio.run(run_all())


if __name__ == "__main__":
    main()
