"""联邦总调度器: 智能路由 + 任务委托 + Human-in-the-loop"""

import structlog
from typing import Any, Dict, List, Optional

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from ..config import settings
from ..api.schemas import (
    A2ATaskResponse,
    AgentCard,
    TaskStatus,
    UserInput,
)
from .registry import agent_registry
from .a2a_client import a2a_client

logger = structlog.get_logger()

ROUTING_PROMPT = """你是一个多模态 Agent 联邦的任务路由器。根据用户输入，选择最合适的 Agent。

可用 Agent:
- multimodal_design_agent: 处理图像/视频/音频的多模态理解，UI 设计规范生成
- secure_code_agent: 复杂代码生成 (后端 API、数据库、安全相关)，类型安全的开发
- code_review_agent: 代码审查、安全漏洞检测、多轮辩论式审查
- workflow_orchestrator: 长周期多步骤工作流编排 (当任务涉及多个阶段时)

选择规则:
1. 如果用户上传了图片/视频/音频，或要求 UI 设计/页面设计 → multimodal_design_agent
2. 如果用户要求生成代码/开发功能/编写 API → secure_code_agent
3. 如果用户要求审查代码/检查安全性/代码评审 → code_review_agent
4. 如果任务涉及多个阶段 (分析→设计→开发→审查→部署) → workflow_orchestrator
5. 简单问答/说明类请求: 直接回答，不需要委托 Agent

返回 JSON:
{
    "agent": "agent_name 或 null",
    "reason": "选择理由",
    "is_multi_stage": true/false,
    "extracted_requirements": "摘要",
    "task_type": "视觉分析/代码生成/代码审查/多阶段工作流/直接回答"
}"""


class FederationSupervisor:
    """联邦总调度器"""

    def __init__(self):
        self.router_client = None
        self.router_anthropic = None
        self.router_model = settings.router_model

        # 优先 Gemini
        if settings.gemini_api_key and HAS_GENAI:
            try:
                self.router_client = genai.Client(api_key=settings.gemini_api_key)
                logger.info("supervisor_router_using_gemini")
            except Exception:
                pass

        # 无 Gemini 时用 Anthropic/DeepSeek
        if not self.router_client and settings.anthropic_api_key:
            try:
                from anthropic import AsyncAnthropic
                kwargs = {"api_key": settings.anthropic_api_key}
                if settings.anthropic_base_url:
                    kwargs["base_url"] = settings.anthropic_base_url
                self.router_anthropic = AsyncAnthropic(**kwargs)
                logger.info("supervisor_router_using_anthropic")
            except Exception:
                pass

        self._active_workflows: Dict[str, Dict[str, Any]] = {}

    async def route_and_execute(self, user_input: UserInput) -> Dict[str, Any]:
        """
        分析用户输入，路由到最合适的 Agent 并执行

        返回:
        {
            "routing": {...},
            "result": A2ATaskResponse,
            "requires_human_review": bool,
        }
        """
        # 1. 智能路由
        routing = await self._route_task(user_input)

        # 2. 如果不需要 Agent (直接问答)
        if routing["agent"] is None:
            return {
                "routing": routing,
                "result": {
                    "status": "completed",
                    "message": routing.get("direct_response", "任务已理解，无需委托 Agent"),
                },
                "requires_human_review": False,
            }

        # 3. 委托给目标 Agent
        agent_name = routing["agent"]
        agent_url = agent_registry.get_agent_url(agent_name)

        if not agent_url:
            return {
                "routing": routing,
                "result": {"status": "failed", "error": f"Agent '{agent_name}' 未注册或不可用"},
                "requires_human_review": False,
            }

        # 构建任务
        task = {
            "text": user_input.text,
            "images": user_input.images,
            "videos": user_input.videos,
            "audio": user_input.audio,
            "files": user_input.files,
            "task_type": routing.get("task_type", ""),
            "extracted_requirements": routing.get("extracted_requirements", ""),
            **user_input.context,
        }

        # 4. 发送 A2A 请求
        response = await a2a_client.send_task(
            endpoint=agent_url,
            task=task,
            agent_name=agent_name,
            context=user_input.context,
        )

        # 5. 判断是否需要人工审查
        needs_review = self._assess_review_need(agent_name, response)

        return {
            "routing": routing,
            "result": response.model_dump(),
            "requires_human_review": needs_review,
        }

    async def _route_task(self, user_input: UserInput) -> Dict[str, Any]:
        """使用 LLM 智能路由 (优先 Gemini，回退 Anthropic/DeepSeek)"""
        has_multimodal = bool(
            user_input.images or user_input.videos or user_input.audio or user_input.files
        )
        extra = " [用户上传了图片/视频/音频/文件]" if has_multimodal else ""

        # 策略 1: Gemini 路由
        if self.router_client:
            return await self._route_via_gemini(user_input, extra, has_multimodal)

        # 策略 2: Anthropic/DeepSeek 路由
        if self.router_anthropic:
            return await self._route_via_anthropic(user_input, extra, has_multimodal)

        # 策略 3: 关键词降级
        logger.warning("no_routing_llm_available")
        return self._keyword_routing(user_input, has_multimodal)

    async def _route_via_gemini(self, user_input: UserInput, extra: str, has_multimodal: bool) -> Dict[str, Any]:
        try:
            resp = self.router_client.models.generate_content(
                model=self.router_model,
                contents=f"{ROUTING_PROMPT}\n\n用户输入: {user_input.text}{extra}",
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=512,
                    response_mime_type="application/json",
                ),
            )
            import json
            routing = json.loads(resp.text)
            if has_multimodal and routing.get("agent") is None:
                routing["agent"] = "multimodal_design_agent"
            return routing
        except Exception as e:
            logger.warning("gemini_routing_failed", error=str(e))
            return self._keyword_routing(user_input, has_multimodal)

    async def _route_via_anthropic(self, user_input: UserInput, extra: str, has_multimodal: bool) -> Dict[str, Any]:
        try:
            resp = await self.router_anthropic.messages.create(
                model=self.router_model,
                max_tokens=512,
                messages=[{"role": "user", "content": f"{ROUTING_PROMPT}\n\n用户输入: {user_input.text}{extra}"}],
            )
            import json
            text = resp.content[0].text
            # Try to extract JSON
            try:
                routing = json.loads(text)
            except json.JSONDecodeError:
                import re
                match = re.search(r'\{[\s\S]*\}', text)
                routing = json.loads(match.group()) if match else {"agent": None}
            if has_multimodal and routing.get("agent") is None:
                routing["agent"] = "multimodal_design_agent"
            return routing
        except Exception as e:
            logger.warning("anthropic_routing_failed", error=str(e))
            return self._keyword_routing(user_input, has_multimodal)

    def _keyword_routing(self, user_input: UserInput, has_multimodal: bool) -> Dict[str, Any]:
        """降级路由: 关键词匹配"""
        text = user_input.text

        if has_multimodal:
            return {"agent": "multimodal_design_agent", "reason": "包含多模态输入", "is_multi_stage": False, "task_type": "多模态分析"}

        code_keywords = ["代码", "开发", "实现", "API", "接口", "生成", "创建", "写", "build", "create", "implement"]
        review_keywords = ["审查", "review", "检查", "安全", "漏洞", "bug", "评审"]
        workflow_keywords = ["部署", "deploy", "工作流", "workflow", "流程", "全栈", "从零", "项目"]

        if any(kw in text for kw in workflow_keywords):
            return {"agent": "workflow_orchestrator", "reason": "多阶段工作流", "is_multi_stage": True, "task_type": "多阶段工作流"}
        elif any(kw in text for kw in review_keywords):
            return {"agent": "code_review_agent", "reason": "代码审查需求", "is_multi_stage": False, "task_type": "代码审查"}
        elif any(kw in text for kw in code_keywords):
            return {"agent": "secure_code_agent", "reason": "代码生成需求", "is_multi_stage": False, "task_type": "代码生成"}
        else:
            return {"agent": None, "reason": "直接回答", "is_multi_stage": False, "task_type": "直接回答"}

    def _assess_review_need(self, agent_name: str, response: A2ATaskResponse) -> bool:
        """评估是否需要人工审查"""
        # 高风险 Agent: 始终需要审查
        high_risk = ["secure_code_agent", "code_review_agent"]
        if agent_name in high_risk:
            return True

        # 失败状态: 需要人工介入
        if response.status == TaskStatus.FAILED:
            return True

        # Agent 标记需要审查
        if response.requires_human_review:
            return True

        return False

    def track_workflow(self, thread_id: str, state: Dict[str, Any]):
        """追踪工作流状态"""
        self._active_workflows[thread_id] = state

    def get_workflow_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        return self._active_workflows.get(thread_id)


# 全局单例
supervisor = FederationSupervisor()
