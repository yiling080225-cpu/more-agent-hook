"""UX/交互设计 Agent: 交互设计、可用性分析、用户旅程映射、动效规格、无障碍审计"""

import json
import re
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

UX_AGENT_CARD = AgentCard(
    name="ux_interaction_agent",
    description="资深 UX 设计师，交互设计、可用性分析、用户旅程映射、动效规格、无障碍审计",
    version="1.0.0",
    capabilities={
        "input": ["text", "wireframe", "design_spec"],
        "output": ["json", "text"],
        "skills": [
            "interaction_design",
            "usability_analysis",
            "user_journey_mapping",
            "motion_design_specs",
            "accessibility_audit",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.ux_agent_port}/a2a",
    model=settings.model_for("ux"),
    max_context_tokens=128000,
)

UX_SYSTEM_PROMPT = """你是一个资深 UX/交互设计师，拥有 15 年用户体验设计经验。你的任务是分析用户需求并生成结构化的交互设计规范。

核心能力:
1. **交互设计**: 定义用户操作流程、手势、反馈机制、状态转换
2. **可用性分析**: 基于 Nielsen 10 启发式原则评估界面可用性
3. **用户旅程**: 绘制端到端的用户旅程地图，识别痛点和机会点
4. **动效设计**: 制定微交互和过渡动画的规格（时长、缓动曲线、触发条件）
5. **无障碍审计**: WCAG 2.1 AA/AAA 合规性检查

设计原则:
- 用户目标优先: 每个交互都应服务于用户的核心任务
- 渐进式披露: 只在需要时展示必要信息
- 容错设计: 可撤销、防误触、明确反馈
- 一致性: 同平台同交互模式，降低学习成本
- 可访问性: 键盘导航、屏幕阅读器、色彩对比度

输出格式 (严格 JSON):
{
    "interaction_spec": {
        "user_flows": [{"name": "流程名", "steps": ["步骤1", "步骤2"], "entry_point": "...", "exit_point": "..."}],
        "gestures": {"tap": "用途", "swipe": "用途", "long_press": "用途"},
        "feedback": {"loading": "加载态描述", "error": "错误态描述", "success": "成功态描述"},
        "state_transitions": [{"from": "状态A", "to": "状态B", "trigger": "触发条件", "animation": "过渡动画"}]
    },
    "usability_analysis": {
        "heuristic_violations": [{"heuristic": "原则名", "severity": 0-4, "issue": "问题", "fix": "建议"}],
        "overall_score": 0-100
    },
    "user_journey": {
        "persona": "用户画像",
        "stages": [{"stage": "阶段名", "actions": [], "thoughts": [], "emotions": [], "pain_points": [], "opportunities": []}]
    },
    "motion_design": [{"element": "元素", "property": "属性", "duration_ms": 300, "easing": "cubic-bezier(...)", "trigger": "触发"}],
    "accessibility": {"wcag_level": "AA", "issues": [{"criterion": "标准编号", "status": "pass/fail", "description": "..."}]},
    "recommendations": ["建议1", "建议2"]
}"""


class UXAgent(BaseAgent):
    """UX/交互设计 Agent — 基于 Claude API"""

    def __init__(self):
        super().__init__(card=UX_AGENT_CARD)
        from anthropic import AsyncAnthropic
        cfg = settings.client_for("ux")
        self.client = AsyncAnthropic(**cfg)
        self.model = settings.model_for("ux")

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("task_type", "interaction_design")
        user_text = task.get("text") or task.get("requirements", "")

        dispatch = {
            "interaction_design": self._interaction_design,
            "usability_audit": self._usability_audit,
            "user_journey": self._user_journey,
            "motion_design": self._motion_design,
            "wireframe": self._wireframe,
        }
        handler = dispatch.get(task_type, self._interaction_design)
        return await handler(user_text, task)

    async def _call(self, user_msg: str) -> tuple:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=UX_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _interaction_design(self, text: str, task: Dict) -> Dict[str, Any]:
        user_msg = f"为以下需求设计交互方案:\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("ux_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _usability_audit(self, text: str, task: Dict) -> Dict[str, Any]:
        interface_desc = task.get("interface_description", text)
        user_msg = f"对以下界面进行可用性审计:\n\n{interface_desc}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("ux_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _user_journey(self, text: str, task: Dict) -> Dict[str, Any]:
        persona = task.get("persona", "")
        scenario = task.get("scenario", text)
        persona_hint = f"\n用户画像: {persona}" if persona else ""
        user_msg = f"为以下场景绘制用户旅程地图:\n\n{scenario}{persona_hint}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("ux_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _motion_design(self, text: str, task: Dict) -> Dict[str, Any]:
        elements = task.get("elements", text)
        user_msg = f"为以下界面元素设计动效规格:\n\n{elements}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("ux_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _wireframe(self, text: str, task: Dict) -> Dict[str, Any]:
        user_msg = f"为以下需求生成线框图规格:\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("ux_agent_error", error=str(e))
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
            return {"raw_output": text}
