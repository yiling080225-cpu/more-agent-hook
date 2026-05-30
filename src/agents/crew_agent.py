"""Crew 协作 Agent: 多角色对话、内容文案、市场分析、头脑风暴、角色模拟"""

import json
import re
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

CREW_AGENT_CARD = AgentCard(
    name="crew_collaboration_agent",
    description="创意协作引导师，多角色对话、内容文案、市场分析、头脑风暴、角色模拟",
    version="1.0.0",
    capabilities={
        "input": ["text", "brief", "scenario"],
        "output": ["text", "dialogue", "report", "json"],
        "skills": [
            "content_writing",
            "market_analysis",
            "brainstorming",
            "persona_simulation",
            "multi_role_dialogue",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.crew_agent_port}/a2a",
    model=settings.model_for("crew"),
    max_context_tokens=128000,
)

CREW_SYSTEM_PROMPT = """你是一个资深创意协作引导师，擅长组织和引导多角色团队的创意协作。你的任务是根据需求模拟多角色对话、生成创意内容或进行市场分析。

核心能力:
1. **内容文案**: 根据品牌调性和目标受众撰写高质量的营销文案、产品描述、广告语
2. **市场分析**: 分析市场规模、竞争格局、用户画像、SWOT 分析
3. **头脑风暴**: 引导多视角创意发散，生成结构化的创意点子集
4. **角色模拟**: 模拟特定角色（CEO/产品经理/用户/投资人等）的思维和对话方式
5. **多角色对话**: 编排多个角色之间的深度对话，每个角色保持一致的个性和专业视角

工作方式:
- 内容创作时: 先明确受众和调性，再产出多种风格变体供选择
- 市场分析时: 以数据驱动，结构化为框架（市场规模→竞争格局→机会点→风险评估）
- 头脑风暴时: 用 SCAMPER / 六顶思考帽 / 反向思考等方法引导发散
- 角色模拟时: 为每个角色设定明确的背景、目标、知识边界和说话风格
- 多角色对话时: 用「角色名: 发言内容」格式呈现自然流畅的对话

输出格式:
- 对于 content_writing: JSON 包含多个文案变体
- 对于 market_analysis: JSON 包含结构化分析框架
- 对于 brainstorming: JSON 包含创意点子列表和评估
- 对于 persona_simulation / multi_role: JSON 包含角色设定和完整对话

通用 JSON 输出结构:
{
    "task_type": "任务类型",
    "output": {  // 具体内容根据任务类型变化 },
    "insights": ["关键洞察1", "关键洞察2"],
    "suggestions": ["后续建议1", "后续建议2"]
}"""


class CrewAgent(BaseAgent):
    """Crew 协作 Agent — 基于 Claude API"""

    def __init__(self):
        super().__init__(card=CREW_AGENT_CARD)
        from anthropic import AsyncAnthropic
        cfg = settings.client_for("crew")
        self.client = AsyncAnthropic(**cfg)
        self.model = settings.model_for("crew")

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("task_type", "content_writing")
        user_text = task.get("text") or task.get("requirements", "")

        dispatch = {
            "content_writing": self._content_writing,
            "market_analysis": self._market_analysis,
            "brainstorming": self._brainstorming,
            "persona_simulation": self._persona_simulation,
            "multi_role": self._multi_role,
        }
        handler = dispatch.get(task_type, self._content_writing)
        return await handler(user_text, task)

    async def _call(self, user_msg: str) -> tuple:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=CREW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _content_writing(self, text: str, task: Dict) -> Dict[str, Any]:
        audience = task.get("audience", "")
        tone = task.get("tone", "professional")
        length = task.get("length", "medium")
        audience_hint = f"\n目标受众: {audience}" if audience else ""
        user_msg = f"撰写以下内容的文案 (风格: {tone}, 长度: {length}):\n\n{text}{audience_hint}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("crew_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _market_analysis(self, text: str, task: Dict) -> Dict[str, Any]:
        industry = task.get("industry", "")
        industry_hint = f"\n行业: {industry}" if industry else ""
        user_msg = f"对以下需求进行市场分析:\n\n{text}{industry_hint}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("crew_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _brainstorming(self, text: str, task: Dict) -> Dict[str, Any]:
        method = task.get("method", "scamper")
        user_msg = f"对以下主题进行头脑风暴 (方法: {method}):\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("crew_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _persona_simulation(self, text: str, task: Dict) -> Dict[str, Any]:
        persona = task.get("persona", "产品经理")
        scenario = task.get("scenario", text)
        user_msg = f"以「{persona}」的角色身份，对以下场景做出回应:\n\n{scenario}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("crew_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _multi_role(self, text: str, task: Dict) -> Dict[str, Any]:
        roles = task.get("roles", ["产品经理", "技术负责人", "设计师", "运营"])
        topic = task.get("topic", text)
        roles_str = ", ".join(roles)
        user_msg = (
            f"模拟以下角色关于「{topic}」的多角色深度对话。\n\n"
            f"角色列表: {roles_str}\n\n"
            f"要求:\n"
            f"- 每个角色保持一致的个性和专业视角\n"
            f"- 对话自然流畅，有观点碰撞和互相补充\n"
            f"- 最终达成可执行的共识或行动方案\n"
            f"- 格式: 角色名: 发言内容\n"
            f"{self._format_files_hint(task)}"
        )
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("crew_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    pass
            return {"raw_output": text, "task_type": "content_writing", "output": {"content": text}}
