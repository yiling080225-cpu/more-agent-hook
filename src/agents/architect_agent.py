"""项目框架规划师 Agent — GPT(复杂架构) + DeepSeek(轻量选型) 按任务拆分"""

import json
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

ARCHITECT_AGENT_CARD = AgentCard(
    name="project_architect_agent",
    description="项目框架规划专家：架构设计、技术栈选型、模块划分、项目蓝图",
    version="1.0.0",
    capabilities={
        "input": ["text", "requirements", "constraints"],
        "output": ["architecture_doc", "tech_stack", "module_plan", "json"],
        "skills": [
            "architecture_design", "technology_selection", "module_decomposition",
            "framework_planning", "system_design", "tradeoff_analysis",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.architect_agent_port}/a2a",
    model=settings.model_for("architect"),
    max_context_tokens=128000,
)

ARCHITECT_SYSTEM_PROMPT = """你是一个资深项目架构师和技术规划专家。你的任务是为软件项目设计架构和框架。

核心能力:
1. **架构设计**: 根据需求设计系统架构（单体/微服务/Serverless/事件驱动等）
2. **技术选型**: 推荐合适的技术栈（框架、数据库、中间件、部署方案）
3. **模块划分**: 拆解功能模块，定义接口和依赖关系
4. **项目蓝图**: 给出分阶段实施路线图
5. **权衡分析**: 对比不同方案的优劣和适用场景

设计原则:
- 务实 > 潮流：选成熟稳定的技术，不为新而新
- 简单 > 复杂：能用单体不用微服务，能少依赖不多依赖
- 可演进：架构能随着业务增长平滑扩展
- 安全内建：认证授权、数据加密、输入验证从设计阶段就考虑
- 成本意识：考虑云资源费用、开发维护成本

输出格式 (JSON):
{
    "project_name": "项目名称",
    "architecture_style": "架构风格",
    "tech_stack": {
        "frontend": {"framework": "...", "reason": "..."},
        "backend": {"language": "...", "framework": "...", "reason": "..."},
        "database": {"primary": "...", "cache": "...", "reason": "..."},
        "infrastructure": {"hosting": "...", "ci_cd": "...", "reason": "..."}
    },
    "modules": [
        {"name": "模块名", "responsibility": "职责", "dependencies": [], "key_apis": []}
    ],
    "data_flow": "数据流向描述",
    "deployment_architecture": "部署架构描述",
    "milestones": [
        {"phase": "Phase 1", "goal": "目标", "deliverables": [], "estimated_days": 0}
    ],
    "risks": [{"risk": "风险描述", "mitigation": "缓解措施"}],
    "tradeoffs": "关键权衡说明"
}"""

# 任务分配: architecture_plan/system_design/framework_design/module_plan -> GPT (强推理)
#           tech_stack -> DeepSeek (性价比)
TASK_MODEL_MAP = {
    "architecture_plan": "gpt",
    "system_design": "gpt",
    "framework_design": "gpt",
    "module_plan": "gpt",
    "tech_stack": "deepseek",
}


class ArchitectAgent(BaseAgent):
    """项目框架规划师 Agent — GPT + DeepSeek 双引擎"""

    def __init__(self):
        super().__init__(card=ARCHITECT_AGENT_CARD)
        from anthropic import AsyncAnthropic

        self.gpt_client = None
        self.gpt_model = None
        if settings.gpt_key:
            self.gpt_client = AsyncAnthropic(api_key=settings.gpt_key, base_url=settings.gpt_url)
            self.gpt_model = settings.gpt_model

        self.ds_client = None
        self.ds_model = None
        if settings.deepseek_key:
            self.ds_client = AsyncAnthropic(api_key=settings.deepseek_key, base_url=settings.deepseek_url)
            self.ds_model = settings.deepseek_model

    def _pick(self, task_type: str):
        use = TASK_MODEL_MAP.get(task_type, "gpt")
        if use == "gpt" and self.gpt_client:
            return self.gpt_client, self.gpt_model, "gpt"
        if self.ds_client:
            return self.ds_client, self.ds_model, "deepseek"
        if self.gpt_client:
            return self.gpt_client, self.gpt_model, "gpt"
        return None, None, "none"

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_text = task.get("text") or task.get("requirements", "")
        task_type = task.get("task_type", "architecture_plan")
        dispatch = {
            "architecture_plan": self._plan_architecture,
            "tech_stack": self._recommend_stack,
            "system_design": self._system_design,
            "framework_design": self._framework_design,
            "module_plan": self._module_plan,
        }
        handler = dispatch.get(task_type, self._plan_architecture)
        return await handler(user_text, task, task_type)

    async def _call(self, client, model: str, user_msg: str):
        resp = await client.messages.create(
            model=model, max_tokens=4096,
            system=ARCHITECT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _plan_architecture(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        constraints = task.get("constraints", {})
        user_msg = f"为以下项目需求设计整体架构:\n\n{text}"
        if constraints:
            user_msg += f"\n\n约束条件:\n{json.dumps(constraints, ensure_ascii=False, indent=2)}"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("architect_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _recommend_stack(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        user_msg = f"为以下项目推荐技术栈:\n\n{text}"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("architect_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _system_design(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        user_msg = f"为以下需求做系统设计:\n\n{text}"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("architect_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _framework_design(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        user_msg = f"为以下项目设计代码框架和目录结构:\n\n{text}"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("architect_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _module_plan(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        user_msg = f"为以下项目做模块划分和接口设计:\n\n{text}"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("architect_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        import re
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {"raw_output": text, "project_name": "Untitled"}
