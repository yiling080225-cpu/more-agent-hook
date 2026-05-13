"""LangGraph 端到端工作流: 需求 → 分析 → 代码生成 → 审查 → 完成"""

import structlog
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from ..api.schemas import UserInput
from ..gateway.a2a_client import a2a_client
from ..gateway.registry import agent_registry
from ..config import settings
from .checkpoint import SQLiteCheckpointer

logger = structlog.get_logger()


# ==================== 工作流状态 ====================

class WorkflowState(dict):
    """工作流状态 (所有字段会被持久化)"""
    thread_id: str
    requirements: Dict[str, Any]
    # 分析阶段
    ui_spec: Optional[Dict[str, Any]]
    backend_spec: Optional[Dict[str, Any]]
    # 审批
    human_approvals: Dict[str, bool]
    waiting_approval: bool
    # 代码生成
    code_frontend: Optional[Dict[str, Any]]
    code_backend: Optional[Dict[str, Any]]
    # 审查
    review_results: List[Dict[str, Any]]
    review_round: int
    review_passed: bool
    # 结果
    deployment_url: str
    status: str
    error: Optional[str]
    # 元数据
    started_at: str
    updated_at: str


# ==================== 工厂函数: 创建节点 ====================

def create_parse_requirements_node(supervisor_router=None):
    """节点 1: 解析用户需求"""
    async def parse_requirements(state: WorkflowState) -> Dict[str, Any]:
        logger.info("node_parse_requirements", thread_id=state.get("thread_id"))

        reqs = state.get("requirements", {})
        text = reqs.get("text", "")

        # 如果有 Supervisor 路由结果，使用它
        routing = reqs.get("_routing", {})

        # 构建分析结果
        result = {
            "status": "analyzing",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "backend_spec": {
                "project_type": "ecommerce" if any(
                    w in text.lower() for w in ["电商", "商店", "shop", "ecommerce", "商品"]
                ) else "web_app",
                "features": _extract_features(text),
                "parsed_from": text[:500],
            },
            "routing": routing,
        }

        logger.info("parse_requirements_done", thread_id=state.get("thread_id"))
        return result
    return parse_requirements


def create_a2a_delegate_node(agent_name: str, task_builder, result_key: str):
    """工厂函数: 创建 A2A 委托节点"""
    async def delegate(state: WorkflowState) -> Dict[str, Any]:
        logger.info("node_a2a_delegate", agent=agent_name, key=result_key, thread_id=state.get("thread_id"))

        agent_url = agent_registry.get_agent_url(agent_name)
        if not agent_url:
            logger.warning("agent_not_found", name=agent_name)
            return {
                result_key: {"error": f"Agent '{agent_name}' 不可用"},
                "status": "running",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        # 构建任务
        task = task_builder(state)

        # 发送 A2A 请求
        response = await a2a_client.send_task(
            endpoint=agent_url,
            task=task,
            agent_name=agent_name,
        )

        result = response.model_dump()
        logger.info("a2a_delegate_done", agent=agent_name, status=response.status)

        return {
            result_key: result,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    return delegate


def _build_multimodal_task(state: WorkflowState) -> Dict[str, Any]:
    """构建多模态分析任务"""
    reqs = state.get("requirements", {})
    return {
        "text": reqs.get("text", "分析需求并生成 UI 设计规范"),
        "images": reqs.get("images", []),
        "task_type": "ui_design",
    }


def _build_code_frontend_task(state: WorkflowState) -> Dict[str, Any]:
    """构建前端代码生成任务"""
    ui_spec = state.get("ui_spec", {})
    reqs = state.get("requirements", {})
    return {
        "type": "frontend",
        "spec": {
            "ui_spec": ui_spec,
            "requirements": reqs.get("text", ""),
            "tech_stack": "Next.js 14 + TypeScript + Tailwind CSS",
        },
    }


def _build_code_backend_task(state: WorkflowState) -> Dict[str, Any]:
    """构建后端代码生成任务"""
    backend_spec = state.get("backend_spec", {})
    reqs = state.get("requirements", {})
    return {
        "type": "backend",
        "spec": {
            "backend_spec": backend_spec,
            "requirements": reqs.get("text", ""),
            "tech_stack": "FastAPI + Python 3.12 + SQLAlchemy + PostgreSQL",
        },
    }


def create_human_review_node(checkpoint_key: str):
    """节点: 人工审批"""
    async def human_review(state: WorkflowState) -> Dict[str, Any]:
        logger.info("node_human_review", key=checkpoint_key, thread_id=state.get("thread_id"))
        # 设置等待人工审批状态
        return {
            "waiting_approval": True,
            "status": "waiting_human",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    return human_review


def create_review_node():
    """节点: AutoGen 风格的对话式代码审查"""
    async def code_review(state: WorkflowState) -> Dict[str, Any]:
        review_round = state.get("review_round", 0)
        max_rounds = 3
        thread_id = state.get("thread_id", "unknown")

        logger.info("node_code_review", round=review_round + 1, thread_id=thread_id)

        # 收集待审查的代码
        code_frontend = state.get("code_frontend", {})
        code_backend = state.get("code_backend", {})

        code_parts = {}
        if code_frontend and not isinstance(code_frontend.get("error"), str):
            code_parts["frontend"] = code_frontend
        if code_backend and not isinstance(code_backend.get("error"), str):
            code_parts["backend"] = code_backend

        if not code_parts:
            return {
                "review_results": state.get("review_results", []) + [{"verdict": "approved", "summary": "无代码需要审查"}],
                "review_passed": True,
                "status": "reviewed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        # 委托给 Review Agent
        review_agent_url = agent_registry.get_agent_url("code_review_agent")
        if review_agent_url:
            review_task = {
                "code": code_parts,
                "review_round": review_round + 1,
                "previous_comments": state.get("review_results", []),
                "task_id": thread_id,
            }
            response = await a2a_client.send_task(
                endpoint=review_agent_url,
                task=review_task,
                agent_name="code_review_agent",
            )
            review_result = response.result or response.model_dump()
        else:
            # 降级: 本地简单检查
            review_result = _local_code_review(code_parts)

        review_results = state.get("review_results", [])
        review_results.append(review_result)

        verdict = review_result.get("verdict", "changes_requested")
        passed = verdict == "approved" or review_round + 1 >= max_rounds

        new_round = review_round + 1

        return {
            "review_results": review_results,
            "review_round": new_round,
            "review_passed": passed,
            "status": "reviewed" if passed else "reviewing",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    return code_review


def _local_code_review(code_parts: Dict[str, Any]) -> Dict[str, Any]:
    """本地代码检查 (Review Agent 不可用时的降级方案)"""
    issues = []
    for part_name, part_data in code_parts.items():
        code_str = str(part_data)
        # 基础安全检查
        if "eval(" in code_str:
            issues.append({"severity": "critical", "file": part_name, "description": "使用了 eval()，存在代码注入风险"})
        if "password" in code_str.lower() and "os.environ" not in code_str:
            issues.append({"severity": "warning", "file": part_name, "description": "可能存在硬编码密码"})
        if "SELECT *" in code_str.upper():
            issues.append({"severity": "info", "file": part_name, "description": "建议避免 SELECT *，明确指定列名"})

    return {
        "verdict": "approved" if not any(i["severity"] == "critical" for i in issues) else "changes_requested",
        "issues": issues,
        "summary": f"本地检查发现 {len(issues)} 个问题",
        "score": max(1, 10 - len(issues) * 2),
    }


def create_deploy_node():
    """节点: 部署通知 (MVP 中生成部署摘要，不实际部署)"""
    async def deploy(state: WorkflowState) -> Dict[str, Any]:
        logger.info("node_deploy", thread_id=state.get("thread_id"))

        # 生成部署摘要
        code_frontend = state.get("code_frontend", {})
        code_backend = state.get("code_backend", {})
        review_results = state.get("review_results", [])

        summary = {
            "status": "completed",
            "frontend_files": _count_files(code_frontend),
            "backend_files": _count_files(code_backend),
            "review_rounds": len(review_results),
            "final_verdict": review_results[-1].get("verdict", "unknown") if review_results else "no_review",
            "preview_url": "http://localhost:3000  (本地预览)",
            "deployment_ready": True,
        }

        return {
            "deployment_url": summary["preview_url"],
            "status": "completed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deployment_summary": summary,
        }
    return deploy


def _count_files(code_result: Any) -> int:
    """统计生成的代码文件数"""
    if isinstance(code_result, dict):
        result = code_result.get("result", code_result)
        code = result.get("code", {}) if isinstance(result, dict) else {}
        files = code.get("files", []) if isinstance(code, dict) else []
        return len(files)
    return 0


def _extract_features(text: str) -> List[str]:
    """从需求文本中提取功能列表"""
    keywords = {
        "支付": "payment", "商品": "product", "购物车": "cart",
        "用户": "user_auth", "登录": "user_auth", "搜索": "search",
        "订单": "order", "库存": "inventory", "评论": "review",
        "API": "api", "管理": "admin", "部署": "deployment",
    }
    features = []
    for cn, en in keywords.items():
        if cn in text:
            features.append(en)
    return features or ["web_app"]


# ==================== 构建工作流图 ====================

def build_workflow(checkpointer: Optional[BaseCheckpointSaver] = None) -> StateGraph:
    """构建 LangGraph 端到端工作流"""

    builder = StateGraph(WorkflowState)

    # 注册节点
    builder.add_node("parse_requirements", create_parse_requirements_node())
    builder.add_node("multimodal_analysis", create_a2a_delegate_node(
        "multimodal_design_agent", _build_multimodal_task, "ui_spec"
    ))
    builder.add_node("human_review_ui", create_human_review_node("ui_spec"))
    builder.add_node("generate_frontend", create_a2a_delegate_node(
        "secure_code_agent", _build_code_frontend_task, "code_frontend"
    ))
    builder.add_node("generate_backend", create_a2a_delegate_node(
        "secure_code_agent", _build_code_backend_task, "code_backend"
    ))
    builder.add_node("code_review", create_review_node())
    builder.add_node("deploy", create_deploy_node())

    # 设置入口
    builder.set_entry_point("parse_requirements")

    # 定义边
    builder.add_edge("parse_requirements", "multimodal_analysis")
    builder.add_edge("multimodal_analysis", "human_review_ui")

    # 人工审批后 → 代码生成
    builder.add_edge("human_review_ui", "generate_frontend")
    builder.add_edge("human_review_ui", "generate_backend")

    # 代码生成后 → 审查
    builder.add_edge("generate_frontend", "code_review")
    builder.add_edge("generate_backend", "code_review")

    # 审查条件边
    def after_review(state: WorkflowState) -> str:
        if state.get("review_passed", False):
            return "deploy"
        elif state.get("review_round", 0) < 3:
            return "generate_backend"
        else:
            return "deploy"

    builder.add_conditional_edges("code_review", after_review, {
        "deploy": "deploy",
        "generate_backend": "generate_backend",
    })

    builder.add_edge("deploy", END)

    # 编译
    if checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
    else:
        graph = builder.compile()

    logger.info("workflow_built", nodes=len(builder.nodes))
    return graph


# ==================== 工作流执行器 ====================

class WorkflowRunner:
    """工作流执行器: 管理端到端执行"""

    def __init__(self, checkpointer: Optional[BaseCheckpointSaver] = None):
        self.checkpointer = checkpointer or SQLiteCheckpointer(settings.sqlite_path)
        self.graph = build_workflow(self.checkpointer)
        self._active_runs: Dict[str, Any] = {}

    async def start(self, user_input: UserInput, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """启动新工作流"""
        import uuid

        tid = thread_id or str(uuid.uuid4())

        initial_state: WorkflowState = {
            "thread_id": tid,
            "requirements": user_input.model_dump(),
            "ui_spec": None,
            "backend_spec": None,
            "human_approvals": {},
            "waiting_approval": False,
            "code_frontend": None,
            "code_backend": None,
            "review_results": [],
            "review_round": 0,
            "review_passed": False,
            "deployment_url": "",
            "status": "started",
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        config = {"configurable": {"thread_id": tid}}

        logger.info("workflow_started", thread_id=tid)

        events = []
        try:
            async for event in self.graph.astream(initial_state, config):
                events.append(event)
                logger.info("workflow_event", thread_id=tid, event=str(event)[:200])
        except Exception as e:
            logger.error("workflow_error", thread_id=tid, error=str(e))
            return {
                "thread_id": tid,
                "status": "failed",
                "error": str(e),
                "events": str(events)[:500],
            }

        # 获取最终状态
        final_state = self.checkpointer.get_latest_state(tid)

        return {
            "thread_id": tid,
            "status": final_state.get("status", "unknown") if final_state else "unknown",
            "events": [str(e)[:200] for e in events],
            "final_state": final_state,
        }

    async def resume(self, thread_id: str, approval: Dict[str, Any]) -> Dict[str, Any]:
        """从 Checkpoint 恢复工作流 (人工审批后)"""
        config = {"configurable": {"thread_id": thread_id}}

        # 获取当前状态
        current = self.checkpointer.get_latest_state(thread_id)
        if not current:
            return {"thread_id": thread_id, "status": "error", "error": "Checkpoint 未找到"}

        # 注入审批结果
        if "approve" in str(approval.get("decision", "")).lower():
            current["waiting_approval"] = False
            current["human_approvals"][approval.get("checkpoint_key", "default")] = True
            current["status"] = "running"

        logger.info("workflow_resumed", thread_id=thread_id)

        events = []
        try:
            async for event in self.graph.astream(current, config):
                events.append(event)
        except Exception as e:
            logger.error("workflow_resume_error", thread_id=thread_id, error=str(e))
            return {"thread_id": thread_id, "status": "failed", "error": str(e)}

        final_state = self.checkpointer.get_latest_state(thread_id)

        return {
            "thread_id": thread_id,
            "status": final_state.get("status", "unknown") if final_state else "unknown",
            "events": [str(e)[:200] for e in events],
            "final_state": final_state,
        }

    def get_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """查询工作流状态"""
        return self.checkpointer.get_latest_state(thread_id)

    def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        workflows = []
        for t in list(self.checkpointer.list(None, limit=100)):
            workflows.append({
                "thread_id": t.config["configurable"]["thread_id"],
                "status": t.metadata.get("status", "unknown"),
                "updated_at": t.checkpoint.get("updated_at", ""),
            })
        return workflows


# 全局单例
workflow_runner = WorkflowRunner()
