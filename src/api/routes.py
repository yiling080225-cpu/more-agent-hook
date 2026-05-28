"""FastAPI 路由: A2A 端点 + 管理 API + 工作流控制 + 监控"""

import uuid
import structlog
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from ..config import settings
from ..api.schemas import (
    A2ATaskRequest,
    A2ATaskResponse,
    AgentCard,
    HumanReviewRequest,
    HumanReviewResponse,
    TaskStatus,
    UserInput,
    WorkflowStartRequest,
)
from ..gateway.registry import agent_registry
from ..gateway.supervisor import supervisor
from ..gateway.a2a_client import a2a_client
from ..workflow.ecommerce_workflow import workflow_runner
from ..mcp.registry import mcp_registry

logger = structlog.get_logger()

router = APIRouter()

# ==================== A2A 端点 ====================

@router.get("/.well-known/agent.json")
async def supervisor_card():
    """Supervisor 的 Agent Card"""
    return {
        "name": "federation_supervisor",
        "description": "多模态 Agent 联邦总调度器，通过 A2A 协议协调各专项 Agent",
        "version": "1.0.0-mvp",
        "capabilities": {
            "input": ["text", "image", "video", "audio"],
            "output": ["text", "json", "code"],
            "skills": [
                "task_routing",
                "agent_coordination",
                "human_in_the_loop",
                "multimodal_understanding",
                "workflow_orchestration",
            ],
        },
        "endpoint": f"http://{settings.host}:{settings.port}/a2a",
        "supported_agents": [c.name for c in agent_registry.list_all()],
    }


@router.post("/a2a", response_model=A2ATaskResponse)
async def handle_a2a_task(request: A2ATaskRequest):
    """A2A 协议标准端点: 接收其他 Agent 的任务委托"""
    logger.info("a2a_request_received", agent=request.agent_name, task_id=request.task_id)

    try:
        # 如果是工作流类型的任务，启动工作流
        if request.agent_name == "workflow_orchestrator":
            user_input = UserInput(**request.task)
            result = await workflow_runner.start(user_input)
            return A2ATaskResponse(
                task_id=request.task_id,
                agent_name="workflow_orchestrator",
                status=TaskStatus.COMPLETED,
                result=result,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        # 否则通过 Supervisor 路由
        user_input = UserInput(text=request.task.get("text", ""), **(request.task))
        routing_result = await supervisor.route_and_execute(user_input)

        return A2ATaskResponse(
            task_id=request.task_id,
            agent_name=request.agent_name,
            status=TaskStatus.COMPLETED if routing_result.get("result", {}).get("status") != "failed"
            else TaskStatus.FAILED,
            result=routing_result,
            requires_human_review=routing_result.get("requires_human_review", False),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.error("a2a_handler_error", error=str(e))
        return A2ATaskResponse(
            task_id=request.task_id,
            agent_name=request.agent_name,
            status=TaskStatus.FAILED,
            error=str(e),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


# ==================== 工作流 API ====================

@router.post("/workflow/start")
async def start_workflow(request: WorkflowStartRequest):
    """启动端到端工作流"""
    logger.info("workflow_start_api", text=request.input.text[:100])
    result = await workflow_runner.start(
        user_input=request.input,
        thread_id=request.thread_id,
    )
    return result


@router.get("/workflow/{thread_id}/status")
async def workflow_status(thread_id: str):
    """查询工作流状态"""
    status = workflow_runner.get_status(thread_id)
    if not status:
        raise HTTPException(status_code=404, detail="工作流未找到")
    return {"thread_id": thread_id, "status": status}


@router.post("/workflow/{thread_id}/resume")
async def resume_workflow(thread_id: str, approval: HumanReviewResponse):
    """人工审批后恢复工作流"""
    logger.info("workflow_resume_api", thread_id=thread_id, decision=approval.decision)
    result = await workflow_runner.resume(thread_id, approval.model_dump())
    return result


@router.get("/workflows")
async def list_workflows():
    """列出所有工作流"""
    return {"workflows": workflow_runner.list_workflows()}


# ==================== Agent 管理 API ====================

@router.get("/agents")
async def list_agents():
    """列出所有已注册 Agent"""
    agents = []
    for card in agent_registry.list_all():
        agents.append(card.model_dump())
    return {"agents": agents}


@router.get("/agents/{name}/card")
async def get_agent_card(name: str):
    """获取指定 Agent 的 Agent Card"""
    card = agent_registry.get(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' 未注册")
    return card.model_dump()


@router.post("/agents/health-check")
async def health_check_agents():
    """对所有 Agent 执行健康检查"""
    status = await agent_registry.health_check()
    return {"status": status, "summary": agent_registry.get_status_summary()}


# ==================== 调度 API ====================

@router.post("/supervisor/route")
async def route_task(user_input: UserInput):
    """分析用户输入并路由 (不执行)"""
    routing = await supervisor._route_task(user_input)
    return routing


@router.post("/supervisor/execute")
async def execute_task(user_input: UserInput):
    """路由并执行任务"""
    result = await supervisor.route_and_execute(user_input)
    return result


# ==================== MCP 工具 API ====================

@router.get("/mcp/tools")
async def list_mcp_tools():
    """列出所有 MCP 工具"""
    return {"tools": mcp_registry.list_tools()}


@router.post("/mcp/tools/{tool_name}/call")
async def call_mcp_tool(tool_name: str, request: Dict[str, Any]):
    """调用 MCP 工具"""
    result = await mcp_registry.call_tool(
        tool_name=tool_name,
        arguments=request.get("arguments", {}),
        approved=request.get("approved", False),
    )
    return result


# ==================== 系统 API ====================

@router.get("/health")
async def health():
    """系统健康检查"""
    return {
        "status": "healthy",
        "service": "multimodal_agent_federation_mvp",
        "version": "1.0.0-mvp",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agents_registered": len(agent_registry.list_all()),
    }


@router.get("/system/info")
async def system_info():
    """系统信息"""
    agent_status = await agent_registry.health_check()
    return {
        "config": {
            "host": settings.host,
            "port": settings.port,
            "multimodal_model": settings.model_for("multimodal"),
            "code_model": settings.model_for("code"),
            "review_model": settings.model_for("review"),
        },
        "agents": agent_registry.get_status_summary(),
        "mcp_tools": len(mcp_registry.list_tools()),
        "active_workflows": len(workflow_runner._active_runs),
    }


# ==================== App 工厂 ====================

def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="多模态 Agent 联邦 MVP",
        description="Agent Federation — 哪个 Agent 能力强就用哪个",
        version="1.0.0-mvp",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_error", path=str(request.url), error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "path": str(request.url)},
        )

    # 注册路由
    app.include_router(router)

    # 静态文件
    from pathlib import Path
    ui_dir = Path(__file__).parent.parent / "ui"
    if ui_dir.exists():
        app.mount("/static", StaticFiles(directory=str(ui_dir)), name="static")

    return app
