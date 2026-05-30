"""品牌/创意 Agent: 品牌识别、色彩系统、字体层级、设计令牌、风格指南生成"""

import json
import re
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

BRAND_AGENT_CARD = AgentCard(
    name="brand_creative_agent",
    description="品牌设计师，品牌识别、色彩系统、字体层级、设计令牌、风格指南生成",
    version="1.0.0",
    capabilities={
        "input": ["text", "brand_brief"],
        "output": ["json", "design_tokens"],
        "skills": [
            "brand_identity",
            "color_system",
            "typography_scale",
            "design_tokens",
            "style_guide_generation",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.brand_agent_port}/a2a",
    model=settings.model_for("brand"),
    max_context_tokens=128000,
)

BRAND_SYSTEM_PROMPT = """你是一个资深品牌设计师，拥有丰富的品牌识别系统设计经验。你的任务是根据用户需求生成完整的品牌设计规范。

核心能力:
1. **品牌识别**: 定义品牌核心视觉元素——标志、色彩、字体、图形语言
2. **色彩系统**: 构建主色/辅色/中性色/语义色的完整色板（含 light/dark 模式）
3. **字体层级**: Heading/H1-H6/Body/Caption 的字体族、大小、字重、行高
4. **设计令牌**: 生成可直接用于 CSS 变量或 Tailwind 配置的设计令牌 JSON
5. **风格指南**: 组合以上所有元素，生成完整的品牌风格指南

设计原则:
- 一致性: 所有视觉元素协调统一，传达一致的品牌个性
- 可扩展: 色板和字体层级能覆盖从落地页到 Dashboard 的全场景
- 可访问: 色彩对比度达到 WCAG AA 标准（正文 4.5:1，大文字 3:1）
- 跨平台: 同时输出 Web/移动端的适配建议

输出格式 (严格 JSON):
{
    "brand_identity": {
        "name": "品牌名",
        "tagline": "品牌标语",
        "personality": ["关键特质1", "关键特质2", "关键特质3"],
        "visual_direction": "视觉方向描述"
    },
    "color_system": {
        "primary": {"50": "#hex", "100": "#hex", ..., "900": "#hex", "DEFAULT": "#hex"},
        "secondary": {"50": "#hex", ..., "DEFAULT": "#hex"},
        "neutral": {"50": "#hex", ..., "900": "#hex"},
        "semantic": {"success": "#hex", "warning": "#hex", "error": "#hex", "info": "#hex"},
        "dark_mode_overrides": {"primary": "#hex", "background": "#hex", "surface": "#hex"}
    },
    "typography": {
        "font_families": {"heading": "字体名", "body": "字体名", "mono": "字体名"},
        "scale": {
            "h1": {"size": "2.5rem", "weight": 700, "line_height": 1.2},
            "h2": {"size": "2rem", "weight": 700, "line_height": 1.25},
            "h3": {"size": "1.5rem", "weight": 600, "line_height": 1.3},
            "body": {"size": "1rem", "weight": 400, "line_height": 1.6},
            "caption": {"size": "0.875rem", "weight": 400, "line_height": 1.4}
        }
    },
    "design_tokens": {
        "colors": {"--color-primary": "#hex", ...},
        "spacing": {"--spacing-xs": "0.25rem", "--spacing-sm": "0.5rem", "--spacing-md": "1rem", "--spacing-lg": "1.5rem", "--spacing-xl": "2rem"},
        "border_radius": {"--radius-sm": "4px", "--radius-md": "8px", "--radius-lg": "12px"},
        "shadows": {"--shadow-sm": "...", "--shadow-md": "...", "--shadow-lg": "..."}
    },
    "style_guide": {
        "logo_usage": ["规则1", "规则2"],
        "do_dont": [{"do": "正确用法", "dont": "错误用法"}],
        "application_examples": ["场景1", "场景2"]
    }
}"""


class BrandAgent(BaseAgent):
    """品牌/创意 Agent — 基于 Claude API"""

    def __init__(self):
        super().__init__(card=BRAND_AGENT_CARD)
        from anthropic import AsyncAnthropic
        cfg = settings.client_for("brand")
        self.client = AsyncAnthropic(**cfg)
        self.model = settings.model_for("brand")

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("task_type", "brand_identity")
        user_text = task.get("text") or task.get("requirements", "")

        dispatch = {
            "brand_identity": self._brand_identity,
            "color_system": self._color_system,
            "typography": self._typography,
            "design_tokens": self._design_tokens,
            "style_guide": self._style_guide,
        }
        handler = dispatch.get(task_type, self._brand_identity)
        return await handler(user_text, task)

    async def _call(self, user_msg: str) -> tuple:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=BRAND_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _brand_identity(self, text: str, task: Dict) -> Dict[str, Any]:
        user_msg = f"为以下品牌需求设计品牌识别系统:\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("brand_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _color_system(self, text: str, task: Dict) -> Dict[str, Any]:
        base_color = task.get("primary_color", "")
        base_hint = f"\n基准色: {base_color}" if base_color else ""
        user_msg = f"为以下需求构建色彩系统:\n\n{text}{base_hint}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("brand_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _typography(self, text: str, task: Dict) -> Dict[str, Any]:
        user_msg = f"为以下需求设计字体层级系统:\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("brand_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _design_tokens(self, text: str, task: Dict) -> Dict[str, Any]:
        user_msg = f"为以下需求生成设计令牌:\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("brand_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _style_guide(self, text: str, task: Dict) -> Dict[str, Any]:
        user_msg = f"为以下需求生成完整风格指南:\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("brand_agent_error", error=str(e))
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
