"""13步全流程 LangGraph 工作流 — 需求调研 → 验收交付

步骤映射 (13步 → 12 Agent):
  步骤1  需求调研   → crew_collaboration_agent (office-hours 在 Claude Code 端前置完成)
  步骤2  需求文档   → prompt_engineer_agent
  步骤3  原型设计   → ux_interaction_agent         ┐
  步骤4  可行性评估 → project_architect_agent       ├─ 并行组1
  步骤5  技术选型   → project_architect_agent       ┘
  步骤6  架构设计   → project_architect_agent       [审批点1]
  步骤7  数据库设计 → secure_code_agent             ┐
  步骤8  接口文档   → secure_code_agent             ├─ 并行组2
  步骤9  编码开发   → secure_code_agent             ┘
  步骤10 代码审查   → code_review_agent             ┐
  步骤11 测试验证   → testing_qa_agent              ├─ 并行组3 [审批点2]
  步骤12 部署上线   → devops_deploy_agent           [审批点3]
  步骤13 验收交付   → crew_collaboration_agent      [审批点4]

特性:
  - SQLite Checkpoint 持久化 (断点恢复)
  - 4 个人工审批节点
  - 3 组并行执行 (组内并步、组间顺序)
  - 步骤间上下文传递 (每步看到前面所有步骤的产出摘要)
"""

import asyncio
import structlog
from datetime import datetime, timezone
from pathlib import Path
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

class FullFlowState(dict):
    """全流程工作流状态 (所有字段被 SQLite Checkpoint 持久化)"""
    thread_id: str
    project_name: str
    requirements: Dict[str, Any]

    # 13 步骤产出
    step1_research: Optional[Dict[str, Any]]      # 需求调研
    step2_prd: Optional[Dict[str, Any]]            # 需求文档
    step3_prototype: Optional[Dict[str, Any]]      # 原型设计
    step4_feasibility: Optional[Dict[str, Any]]    # 可行性评估
    step5_tech_stack: Optional[Dict[str, Any]]     # 技术选型
    step6_architecture: Optional[Dict[str, Any]]   # 架构设计
    step7_database: Optional[Dict[str, Any]]       # 数据库设计
    step8_api_doc: Optional[Dict[str, Any]]        # 接口文档
    step9_code: Optional[Dict[str, Any]]           # 编码开发
    step10_review: Optional[Dict[str, Any]]        # 代码审查
    step11_test: Optional[Dict[str, Any]]          # 测试验证
    step12_deploy: Optional[Dict[str, Any]]        # 部署上线
    step13_delivery: Optional[Dict[str, Any]]      # 验收交付

    # 审批控制
    waiting_approval: bool
    approval_checkpoint: str                       # 当前审批节点名
    human_approvals: Dict[str, Any]                # {checkpoint_name: {decision, modifications}}

    # 状态
    status: str                                    # started/running/waiting_human/completed/failed
    error: Optional[str]
    pipeline_summary: Optional[str]                # 最终汇总

    # 元数据
    started_at: str
    updated_at: str
    completed_steps: List[str]                     # 已完成的步骤名列表


# ==================== 上下文构建工具 ====================

def _preview(text: Any, max_chars: int = 1500) -> str:
    """截取文本预览，避免上下文膨胀"""
    s = str(text) if not isinstance(text, str) else text
    return s[:max_chars] + ("..." if len(s) > max_chars else "")


def _collect_previous_outputs(state: FullFlowState, up_to_step: int) -> str:
    """收集前面所有步骤的产出摘要"""
    step_keys = [
        (1, "step1_research", "需求调研"),
        (2, "step2_prd", "需求文档(PRD)"),
        (3, "step3_prototype", "原型设计"),
        (4, "step4_feasibility", "可行性评估"),
        (5, "step5_tech_stack", "技术选型"),
        (6, "step6_architecture", "架构设计"),
        (7, "step7_database", "数据库设计"),
        (8, "step8_api_doc", "接口文档"),
        (9, "step9_code", "编码开发"),
        (10, "step10_review", "代码审查"),
        (11, "step11_test", "测试验证"),
        (12, "step12_deploy", "部署上线"),
    ]

    parts = []
    for step_num, key, label in step_keys:
        if step_num >= up_to_step:
            break
        val = state.get(key)
        if val:
            parts.append(f"## {label} (步骤{step_num})\n{_preview(val)}")
    return "\n\n".join(parts) if parts else "(无前序产出)"


# ==================== A2A 委托节点工厂 ====================

def _make_delegate_node(step_num: int, step_name: str, agent_name: str,
                        task_builder, result_key: str):
    """创建 A2A 委托节点: 构建任务 → 发送 Agent → 存储结果"""
    async def node(state: FullFlowState) -> Dict[str, Any]:
        logger.info("fullflow_node", step=step_num, name=step_name,
                    agent=agent_name, thread_id=state.get("thread_id"))

        agent_url = agent_registry.get_agent_url(agent_name)
        if not agent_url:
            return {
                result_key: {"error": f"Agent '{agent_name}' 不可用", "status": "failed"},
                "status": "running",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        task = task_builder(state)
        response = await a2a_client.send_task(
            endpoint=agent_url, task=task, agent_name=agent_name,
            context=state.get("requirements", {}).get("context", {}),
        )
        result = response.model_dump()
        completed = list(state.get("completed_steps", [])) + [step_name]

        return {
            result_key: result,
            "completed_steps": completed,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    return node


# ==================== 审批节点工厂 ====================

def _make_review_node(checkpoint_name: str, title: str, description: str):
    """创建人工审批节点 — 工作流在此暂停，等待人工确认"""
    async def node(state: FullFlowState) -> Dict[str, Any]:
        logger.info("fullflow_review", checkpoint=checkpoint_name,
                    thread_id=state.get("thread_id"))

        # 收集当前阶段产出用于审批展示
        review_context = _collect_previous_outputs(
            state,
            {"prd_review": 3, "arch_review": 7, "quality_review": 12, "final_review": 14}[checkpoint_name]
        )

        return {
            "waiting_approval": True,
            "approval_checkpoint": checkpoint_name,
            "status": "waiting_human",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            # 将审批上下文附加到状态中供查询
            f"_{checkpoint_name}_context": {
                "title": title,
                "description": description,
                "summary": _preview(review_context, 2000),
            },
        }
    return node


# ==================== 各步骤任务构建器 ====================

def _build_step1_task(state: FullFlowState) -> Dict[str, Any]:
    """步骤1 需求调研 — 优先使用 office-hours 前置结果"""
    reqs = state.get("requirements", {})
    # 如果 Claude Code 端已通过 office-hours 完成调研，直接使用
    existing = state.get("step1_research") or reqs.get("office_hours_result")
    prefs = _get_prefs(state)

    if existing:
        return {
            "text": f"以下是已完成的YC风格需求调研结果，请基于此结果做进一步分析和整理:\n\n{_preview(existing, 3000)}",
            "task_type": "brainstorming",
            **prefs,
        }

    return {
        "text": f"""你正在进行一个新项目的需求调研。请用YC风格的6个强制问题深入分析:

1. **真正的痛点是什么？** (不是功能需求，而是背后的痛苦)
2. **现状是什么？** (用户今天在做什么来解决)
3. **最窄的切入点？** (能证明价值的最小MVP)
4. **为什么是现在？** (时机判断)
5. **目标用户画像** (谁会使用，愿意付费吗)
6. **成功指标** (如何衡量项目成功)

请逐项回答，最后给出一个简洁的需求调研总结。

项目需求: {reqs.get('text', '')}""",
        "task_type": "brainstorming",
        **prefs,
    }


def _build_step2_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 2)
    reqs = state.get("requirements", {})
    return {
        "text": f"基于调研结果，编写一份结构化的PRD需求文档:\n\n{prev}\n\n原始需求: {reqs.get('text', '')}\n\n请输出: 项目概述、目标用户、功能需求(按优先级)、非功能需求、验收标准。",
        "task_type": "prompt_design",
        "output_format": "markdown",
        **prefs,
    }


def _build_step3_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 3)
    return {
        "text": f"基于PRD进行原型设计。请输出:\n1. 页面结构和导航流程\n2. 核心页面的线框图描述\n3. 关键交互说明\n\n{prev}",
        "task_type": "wireframe",
        **prefs,
    }


def _build_step4_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 4)
    return {
        "text": f"进行项目可行性评估。请从以下维度分析:\n1. 技术可行性 (现有技术栈是否可实现)\n2. 资源评估 (所需人力/时间/基础设施)\n3. 风险评估 (技术风险、市场风险、合规风险)\n4. ROI 估算\n\n{prev}",
        "task_type": "architecture_plan",
        **prefs,
    }


def _build_step5_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 5)
    return {
        "text": f"基于项目需求进行技术选型。请确定:\n1. 前端框架 (React/Vue/Next.js等)\n2. 后端框架 (FastAPI/Django/Express等)\n3. 数据库 (PostgreSQL/MySQL/MongoDB等)\n4. 第三方服务和库\n5. 选型理由和对比\n\n{prev}",
        "task_type": "tech_stack",
        **prefs,
    }


def _build_step6_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 6)
    return {
        "text": f"设计系统整体架构。请输出:\n1. 架构图描述 (分层/微服务/模块划分)\n2. 数据流转设计\n3. 部署架构\n4. 扩展性和可维护性考虑\n5. 安全架构\n\n{prev}",
        "task_type": "system_design",
        **prefs,
    }


def _build_step7_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 7)
    return {
        "text": f"设计数据库结构。请输出:\n1. ER图描述\n2. 核心表结构 (表名/字段/类型/约束)\n3. 索引设计\n4. 表关系说明\n5. 迁移策略\n\n{prev}",
        "task_type": "generic",
        **prefs,
    }


def _build_step8_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 8)
    return {
        "text": f"编写API接口文档。请输出:\n1. RESTful/GraphQL端点列表\n2. 请求/响应格式\n3. 认证方式\n4. 错误码规范\n5. 速率限制策略\n\n{prev}",
        "task_type": "generic",
        **prefs,
    }


def _build_step9_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 9)
    return {
        "text": f"基于架构设计、数据库设计和接口文档，开始编码开发。请生成核心代码:\n\n{prev}\n\n请输出: 项目骨架结构、核心模块代码、数据库迁移脚本、API实现。",
        "task_type": "generic",
        **prefs,
    }


def _build_step10_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    code = state.get("step9_code", {})
    prev = _collect_previous_outputs(state, 10)
    return {
        "text": f"请审查以下代码的质量、安全性和正确性。检查逻辑漏洞、边界条件、安全风险:\n\n{_preview(prev, 1000)}",
        "code": _preview(code, 8000),
        "review_round": 1,
        "task_type": "代码审查",
        **prefs,
    }


def _build_step11_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 11)
    code = state.get("step9_code", {})
    return {
        "text": f"基于代码和需求，生成测试用例和自动化测试:\n\n代码: {_preview(code, 3000)}\n\n需求: {_preview(prev, 2000)}\n\n请输出: 单元测试、集成测试、E2E测试用例、覆盖率目标。",
        "task_type": "unit_test",
        **prefs,
    }


def _build_step12_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 12)
    return {
        "text": f"准备部署上线。请输出:\n1. Docker配置\n2. CI/CD Pipeline (GitHub Actions)\n3. 环境变量配置\n4. 部署检查清单\n5. 回滚方案\n\n{prev}",
        "task_type": "deploy_script",
        **prefs,
    }


def _build_step13_task(state: FullFlowState) -> Dict[str, Any]:
    prefs = _get_prefs(state)
    prev = _collect_previous_outputs(state, 13)
    return {
        "text": f"进行最终验收和交付准备。请输出:\n1. 项目交付清单\n2. 功能验收报告\n3. 技术文档索引\n4. 运维交接说明\n5. 项目总结\n\n{prev}",
        "task_type": "content_writing",
        **prefs,
    }


def _get_prefs(state: FullFlowState) -> Dict[str, Any]:
    reqs = state.get("requirements", {})
    ctx = reqs.get("context", {})
    return {
        "style": ctx.get("style", ""),
        "theme": ctx.get("theme", ""),
        "output_format": ctx.get("output_format", ""),
    }


# ==================== 构建工作流图 ====================

def build_full_flow(checkpointer: Optional[BaseCheckpointSaver] = None) -> StateGraph:
    """构建 13 步全流程 LangGraph 工作流"""

    builder = StateGraph(FullFlowState)

    # ── 注册所有节点 ──

    # 阶段1: 需求分析
    builder.add_node("step1_research",
        _make_delegate_node(1, "需求调研", "crew_collaboration_agent",
                           _build_step1_task, "step1_research"))
    builder.add_node("step2_prd",
        _make_delegate_node(2, "需求文档编写", "prompt_engineer_agent",
                           _build_step2_task, "step2_prd"))
    builder.add_node("human_review_prd",
        _make_review_node("prd_review", "需求文档审批",
                         "请确认 PRD 需求文档，确认后进入设计阶段"))

    # 阶段2: 设计 (步骤3-5 并行)
    builder.add_node("step3_prototype",
        _make_delegate_node(3, "原型设计", "ux_interaction_agent",
                           _build_step3_task, "step3_prototype"))
    builder.add_node("step4_feasibility",
        _make_delegate_node(4, "可行性评估", "project_architect_agent",
                           _build_step4_task, "step4_feasibility"))
    builder.add_node("step5_tech_stack",
        _make_delegate_node(5, "技术选型", "project_architect_agent",
                           _build_step5_task, "step5_tech_stack"))

    # 阶段2续: 架构设计
    builder.add_node("step6_architecture",
        _make_delegate_node(6, "架构设计", "project_architect_agent",
                           _build_step6_task, "step6_architecture"))
    builder.add_node("human_review_arch",
        _make_review_node("arch_review", "架构设计审批",
                         "请确认系统架构设计，确认后进入数据库/接口设计"))

    # 阶段2续: 数据库+接口 (步骤7-8 并行)
    builder.add_node("step7_database",
        _make_delegate_node(7, "数据库设计", "secure_code_agent",
                           _build_step7_task, "step7_database"))
    builder.add_node("step8_api_doc",
        _make_delegate_node(8, "接口文档编写", "secure_code_agent",
                           _build_step8_task, "step8_api_doc"))

    # 阶段3: 开发
    builder.add_node("step9_code",
        _make_delegate_node(9, "编码开发", "secure_code_agent",
                           _build_step9_task, "step9_code"))

    # 阶段4: 质量保障 (步骤10-11 并行)
    builder.add_node("step10_review",
        _make_delegate_node(10, "代码审查", "code_review_agent",
                           _build_step10_task, "step10_review"))
    builder.add_node("step11_test",
        _make_delegate_node(11, "测试验证", "testing_qa_agent",
                           _build_step11_task, "step11_test"))
    builder.add_node("human_review_quality",
        _make_review_node("quality_review", "质量检查审批",
                         "请确认代码审查和测试结果，确认后进入部署"))

    # 阶段5: 部署
    builder.add_node("step12_deploy",
        _make_delegate_node(12, "部署上线", "devops_deploy_agent",
                           _build_step12_task, "step12_deploy"))

    # 阶段5续: 交付
    builder.add_node("step13_delivery",
        _make_delegate_node(13, "验收交付", "crew_collaboration_agent",
                           _build_step13_task, "step13_delivery"))
    builder.add_node("human_review_final",
        _make_review_node("final_review", "最终验收审批",
                         "请确认最终交付物，确认后项目完结"))

    # ── 定义边 (组内并行 + 组间顺序) ──

    builder.set_entry_point("step1_research")

    # 阶段1 顺序
    builder.add_edge("step1_research", "step2_prd")
    builder.add_edge("step2_prd", "human_review_prd")

    # 审批1 → 并行组1 (步骤3-5)
    builder.add_edge("human_review_prd", "step3_prototype")
    builder.add_edge("human_review_prd", "step4_feasibility")
    builder.add_edge("human_review_prd", "step5_tech_stack")

    # 并行组1 → 步骤6 (同步屏障)
    builder.add_edge("step3_prototype", "step6_architecture")
    builder.add_edge("step4_feasibility", "step6_architecture")
    builder.add_edge("step5_tech_stack", "step6_architecture")

    builder.add_edge("step6_architecture", "human_review_arch")

    # 审批2 → 并行组2 (步骤7-8)
    builder.add_edge("human_review_arch", "step7_database")
    builder.add_edge("human_review_arch", "step8_api_doc")

    # 并行组2 → 步骤9 (同步屏障)
    builder.add_edge("step7_database", "step9_code")
    builder.add_edge("step8_api_doc", "step9_code")

    # 步骤9 → 并行组3 (步骤10-11)
    builder.add_edge("step9_code", "step10_review")
    builder.add_edge("step9_code", "step11_test")

    # 并行组3 → 审批3 (同步屏障)
    builder.add_edge("step10_review", "human_review_quality")
    builder.add_edge("step11_test", "human_review_quality")

    # 审批3 → 步骤12
    builder.add_edge("human_review_quality", "step12_deploy")

    # 步骤12 → 步骤13 → 最终审批
    builder.add_edge("step12_deploy", "step13_delivery")
    builder.add_edge("step13_delivery", "human_review_final")
    builder.add_edge("human_review_final", END)

    # ── 编译 ──
    if checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
    else:
        graph = builder.compile()

    logger.info("full_flow_workflow_built", nodes=len(builder.nodes))
    return graph


# ==================== 工作流执行器 ====================

class FullFlowRunner:
    """全流程工作流执行器 — 管理 13 步端到端执行"""

    def __init__(self, checkpointer: Optional[BaseCheckpointSaver] = None):
        self.checkpointer = checkpointer or SQLiteCheckpointer(settings.sqlite_path)
        self.graph = build_full_flow(self.checkpointer)
        self._active: Dict[str, Any] = {}

    async def start(self, user_input: UserInput,
                    thread_id: Optional[str] = None,
                    office_hours_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """启动全流程工作流

        Args:
            user_input: 用户需求输入
            thread_id: 线程ID (不提供则自动生成)
            office_hours_result: office-hours skill 前置调研结果 (可选)
        """
        import uuid
        tid = thread_id or str(uuid.uuid4())

        initial_state: FullFlowState = {
            "thread_id": tid,
            "project_name": user_input.context.get("project_name", ""),
            "requirements": {
                **user_input.model_dump(),
                "office_hours_result": office_hours_result,
            },
            "step1_research": office_hours_result,
            "step2_prd": None,
            "step3_prototype": None,
            "step4_feasibility": None,
            "step5_tech_stack": None,
            "step6_architecture": None,
            "step7_database": None,
            "step8_api_doc": None,
            "step9_code": None,
            "step10_review": None,
            "step11_test": None,
            "step12_deploy": None,
            "step13_delivery": None,
            "waiting_approval": False,
            "approval_checkpoint": "",
            "human_approvals": {},
            "status": "started",
            "error": None,
            "pipeline_summary": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "completed_steps": [],
        }

        config = {"configurable": {"thread_id": tid}}
        logger.info("full_flow_started", thread_id=tid,
                    has_office_hours=bool(office_hours_result))

        events = []
        try:
            async for event in self.graph.astream(initial_state, config):
                events.append(event)
                # 检测是否进入等待审批状态
                for node_name, node_data in event.items():
                    if isinstance(node_data, dict) and node_data.get("waiting_approval"):
                        logger.info("full_flow_waiting_human", thread_id=tid,
                                    checkpoint=node_data.get("approval_checkpoint"))
        except Exception as e:
            logger.error("full_flow_error", thread_id=tid, error=str(e))
            return {
                "thread_id": tid,
                "status": "failed",
                "error": str(e),
                "events": str(events)[:1000],
            }

        final_state = self.checkpointer.get_latest_state(tid)

        return {
            "thread_id": tid,
            "status": final_state.get("status", "unknown") if final_state else "unknown",
            "waiting_approval": final_state.get("waiting_approval", False) if final_state else False,
            "approval_checkpoint": final_state.get("approval_checkpoint", "") if final_state else "",
            "completed_steps": final_state.get("completed_steps", []) if final_state else [],
            "events": [str(e)[:200] for e in events],
            "final_state": final_state,
        }

    async def resume(self, thread_id: str, approval: Dict[str, Any]) -> Dict[str, Any]:
        """从审批节点恢复工作流"""
        config = {"configurable": {"thread_id": thread_id}}

        current = self.checkpointer.get_latest_state(thread_id)
        if not current:
            return {"thread_id": thread_id, "status": "error", "error": "Checkpoint未找到"}

        decision = str(approval.get("decision", "")).lower() if approval.get("decision") else "approve"

        reject_wording = ("reject", "no", "驳回")
        if decision in ("approve", "yes", "ok", "确认", "同意"):
            current["waiting_approval"] = False
            current["human_approvals"][current.get("approval_checkpoint", "unknown")] = {
                "decision": "approved",
                "modifications": approval.get("modifications"),
            }
            current["status"] = "running"
            logger.info("full_flow_approved", thread_id=thread_id,
                        checkpoint=current.get("approval_checkpoint"))
        elif decision in reject_wording:
            current["waiting_approval"] = False
            checkpoint = current.get("approval_checkpoint", "unknown")
            current["human_approvals"][checkpoint] = {
                "decision": "rejected",
                "reason": approval.get("modifications", {}).get("reason", ""),
            }
            current["status"] = "rejected"
            current["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("full_flow_rejected", thread_id=thread_id,
                        checkpoint=checkpoint)
            # 驳回直接终止，不继续执行后续节点
            return {
                "thread_id": thread_id,
                "status": "rejected",
                "approval_checkpoint": checkpoint,
                "completed_steps": current.get("completed_steps", []),
                "message": f"审批节点 '{checkpoint}' 被驳回，工作流已终止",
            }
        else:
            # modify — 注入修改后继续
            current["waiting_approval"] = False
            current["human_approvals"][current.get("approval_checkpoint", "unknown")] = {
                "decision": "modified",
                "modifications": approval.get("modifications", {}),
            }
            current["status"] = "running"
            logger.info("full_flow_modified", thread_id=thread_id,
                        checkpoint=current.get("approval_checkpoint"))

        events = []
        try:
            async for event in self.graph.astream(current, config):
                events.append(event)
                for node_name, node_data in event.items():
                    if isinstance(node_data, dict) and node_data.get("waiting_approval"):
                        logger.info("full_flow_waiting_human_again", thread_id=thread_id,
                                    checkpoint=node_data.get("approval_checkpoint"))
        except Exception as e:
            logger.error("full_flow_resume_error", thread_id=thread_id, error=str(e))
            return {"thread_id": thread_id, "status": "failed", "error": str(e)}

        final_state = self.checkpointer.get_latest_state(thread_id)

        return {
            "thread_id": thread_id,
            "status": final_state.get("status", "unknown") if final_state else "unknown",
            "waiting_approval": final_state.get("waiting_approval", False) if final_state else False,
            "approval_checkpoint": final_state.get("approval_checkpoint", "") if final_state else "",
            "completed_steps": final_state.get("completed_steps", []) if final_state else [],
            "events": [str(e)[:200] for e in events],
            "final_state": final_state,
        }

    def get_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """查询工作流状态和当前步骤"""
        state = self.checkpointer.get_latest_state(thread_id)
        if not state:
            return None

        # 构建可读的状态摘要
        step_status = {}
        step_keys = [
            "step1_research", "step2_prd", "step3_prototype",
            "step4_feasibility", "step5_tech_stack", "step6_architecture",
            "step7_database", "step8_api_doc", "step9_code",
            "step10_review", "step11_test", "step12_deploy", "step13_delivery",
        ]
        for i, key in enumerate(step_keys, 1):
            val = state.get(key)
            step_status[f"step{i}"] = "completed" if val else "pending"

        return {
            "thread_id": thread_id,
            "status": state.get("status", "unknown"),
            "waiting_approval": state.get("waiting_approval", False),
            "approval_checkpoint": state.get("approval_checkpoint", ""),
            "completed_steps": state.get("completed_steps", []),
            "step_status": step_status,
            "updated_at": state.get("updated_at", ""),
        }

    def list_workflows(self, limit: int = 50) -> List[Dict[str, Any]]:
        workflows = []
        for t in list(self.checkpointer.list(None, limit=limit)):
            workflows.append({
                "thread_id": t.config["configurable"]["thread_id"],
                "status": t.metadata.get("status", "unknown"),
                "updated_at": t.checkpoint.get("updated_at", ""),
            })
        return workflows

    def get_approval_context(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取当前审批节点的上下文信息 (供 Claude Code 端展示)"""
        state = self.checkpointer.get_latest_state(thread_id)
        if not state or not state.get("waiting_approval"):
            return None

        checkpoint = state.get("approval_checkpoint", "")
        ctx_key = f"_{checkpoint}_context"
        return {
            "thread_id": thread_id,
            "checkpoint": checkpoint,
            "context": state.get(ctx_key, {}),
            "completed_steps": state.get("completed_steps", []),
        }


# 全局单例
full_flow_runner = FullFlowRunner()
