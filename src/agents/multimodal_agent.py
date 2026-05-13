"""多模态 Agent: 调用 Gemini/Anthropic API 分析文本/图像，生成 UI 设计规范"""

import base64
import json
import structlog
from typing import Any, Dict, List, Optional

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent

logger = structlog.get_logger()

MULTIMODAL_AGENT_CARD = AgentCard(
    name="multimodal_design_agent",
    description="处理图像、文本的多模态理解与 UI 设计规范生成",
    version="1.0.0",
    capabilities={
        "input": ["text", "image", "audio"],
        "output": ["text", "json"],
        "skills": [
            "ui_design_spec_generation",
            "visual_element_extraction",
            "handwritten_sketch_interpretation",
            "color_palette_extraction",
            "layout_analysis",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.multimodal_agent_port}/a2a",
    model=settings.multimodal_model,
    max_context_tokens=1048576,
)


class MultimodalAgent(BaseAgent):
    """多模态理解 Agent — 优先 Gemini，无 Key 时用 Anthropic/DeepSeek"""

    def __init__(self):
        super().__init__(card=MULTIMODAL_AGENT_CARD)
        self._gemini_client = None
        self._anthropic_client = None
        self.model = settings.multimodal_model

        # 初始化 Gemini 客户端
        if settings.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=settings.gemini_api_key)
                logger.info("multimodal_using_gemini")
            except ImportError:
                logger.warning("google_genai_not_installed")

        # 初始化 Anthropic 客户端 (含 DeepSeek 兼容端点)
        if settings.anthropic_api_key and not self._gemini_client:
            try:
                from anthropic import AsyncAnthropic
                kwargs = {"api_key": settings.anthropic_api_key}
                if settings.anthropic_base_url:
                    kwargs["base_url"] = settings.anthropic_base_url
                self._anthropic_client = AsyncAnthropic(**kwargs)
                logger.info("multimodal_using_anthropic_fallback")
            except ImportError:
                logger.warning("anthropic_not_installed")

        self._use_gemini = self._gemini_client is not None
        self._use_anthropic = self._anthropic_client is not None

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        text = task.get("text", "")
        images = task.get("images", [])
        task_type = task.get("task_type", "ui_design")

        if self._use_gemini:
            return await self._execute_gemini(text, images, task_type, context)
        elif self._use_anthropic:
            return await self._execute_anthropic(text, images, task_type, context)
        else:
            logger.warning("no_api_key_available", task_type=task_type)
            return {
                "success": True,
                "ui_spec": self._fallback_ui_spec(text),
                "confidence": 0.3,
                "model_used": "fallback",
                "note": "未配置任何 API Key，使用模板",
            }

    # ==================== Gemini 路径 ====================

    async def _execute_gemini(
        self, text: str, images: List[str], task_type: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        from google.genai import types

        prompt_text = self._build_prompt(text, task_type)
        contents = [prompt_text]
        for img in images:
            img_data = self._load_image(img)
            if img_data:
                contents.append(img_data)

        try:
            resp = self._gemini_client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7 if task_type == "ui_design" else 0.3,
                    max_output_tokens=4096,
                    response_mime_type="application/json" if task_type in ("ui_design", "content_extraction") else None,
                ),
            )
            result = json.loads(resp.text) if task_type in ("ui_design", "content_extraction") else {"analysis": resp.text}
            return {"success": True, **result, "confidence": 0.85, "model_used": self.model}
        except Exception as e:
            logger.error("gemini_error", error=str(e))
            return self._fallback_result(text)

    # ==================== Anthropic/DeepSeek 路径 ====================

    async def _execute_anthropic(
        self, text: str, images: List[str], task_type: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(text, task_type)

        # 构建消息内容 (支持图片)
        content = []
        for img in images[:5]:  # 最多 5 张图片
            img_data = self._load_image_base64(img)
            if img_data:
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": img_data},
                })
        content.append({"type": "text", "text": prompt})

        try:
            resp = await self._anthropic_client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": content}],
            )
            raw = resp.content[0].text
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = self._fallback_ui_spec(text)

            return {
                "success": True,
                **result,
                "confidence": 0.80,
                "model_used": self.model,
                "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
            }
        except Exception as e:
            logger.error("anthropic_multimodal_error", error=str(e))
            return self._fallback_result(text)

    # ==================== 辅助方法 ====================

    def _build_prompt(self, text: str, task_type: str) -> str:
        prompts = {
            "ui_design": """你是一个资深 UI/UX 设计师。根据用户的描述和图片，生成一份完整的 UI 设计规范 (纯 JSON 格式，不要 markdown 代码块)。

返回 JSON:
{
    "design_system": {
        "color_palette": ["#hex"],
        "typography": {"heading": "font", "body": "font"},
        "spacing": "值",
        "border_radius": "值"
    },
    "pages": [{"name": "页面名", "components": ["组件"], "layout": "布局"}],
    "component_library": {"组件名": {"props": [], "states": [], "description": ""}},
    "interactions": ["交互描述"],
    "accessibility": ["无障碍要点"]
}

用户需求: """ + text,

            "visual_analysis": "分析这张图片/设计的视觉元素：1.颜色方案 2.布局结构 3.UI组件 4.视觉层次 5.改进建议。用户补充: " + text,

            "content_extraction": "提取图片中的所有文字和结构化信息，返回纯 JSON。用户补充: " + text,
        }
        return prompts.get(task_type, prompts["ui_design"])

    def _load_image(self, img: str):
        """加载图片为 Gemini 格式"""
        if img.startswith("data:"):
            try:
                header, b64 = img.split(",", 1)
                mime = header.split(";")[0].replace("data:", "")
                return {"inline_data": {"mime_type": mime, "data": b64}}
            except Exception:
                return None
        elif img.startswith("http"):
            return {"image": {"source": {"image_uri": img}}}
        else:
            try:
                with open(img, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                return {"inline_data": {"mime_type": "image/png", "data": b64}}
            except Exception:
                return None

    def _load_image_base64(self, img: str) -> Optional[str]:
        """加载图片为纯 base64 字符串"""
        if img.startswith("data:"):
            try:
                return img.split(",", 1)[1]
            except Exception:
                return None
        elif img.startswith("http"):
            # HTTP 图片暂不支持，返回 None
            return None
        else:
            try:
                with open(img, "rb") as f:
                    return base64.b64encode(f.read()).decode()
            except Exception:
                return None

    def _fallback_result(self, text: str) -> Dict[str, Any]:
        return {
            "success": True,
            "ui_spec": self._fallback_ui_spec(text),
            "confidence": 0.4,
            "model_used": "fallback",
            "note": "API 调用失败，使用降级模板",
        }

    def _fallback_ui_spec(self, text: str) -> Dict[str, Any]:
        is_ecommerce = any(w in text.lower() for w in ["电商", "商店", "shop", "ecommerce", "购买", "商品"])
        return {
            "design_system": {
                "color_palette": ["#1a73e8", "#34a853", "#fbbc04", "#ea4335"] if not is_ecommerce
                else ["#2d3436", "#0984e3", "#00b894", "#fdcb6e", "#e17055"],
                "typography": {"heading": "Inter", "body": "Inter"},
                "spacing": "4px grid, 16px base",
                "border_radius": "8px",
            },
            "pages": [
                {"name": "首页", "components": ["导航栏", "Hero区域", "功能卡片", "页脚"], "layout": "单列垂直"},
                {"name": "商品列表" if is_ecommerce else "列表页", "components": ["搜索栏", "筛选器", "卡片网格"], "layout": "侧边栏+网格"},
                {"name": "详情页", "components": ["图片轮播", "信息面板", "操作按钮"], "layout": "两栏"},
            ],
            "component_library": {
                "Button": {"props": ["variant", "size", "disabled"], "states": ["default", "hover", "active", "disabled"], "description": "通用按钮"},
                "Card": {"props": ["title", "image", "description", "onClick"], "states": ["default", "hover"], "description": "内容卡片"},
                "Navbar": {"props": ["logo", "links", "actions"], "states": ["default", "scrolled", "mobile"], "description": "导航栏"},
            },
            "interactions": ["页面过渡动画", "卡片悬浮效果", "表单实时验证"],
            "accessibility": ["ARIA labels", "键盘导航", "色彩对比度 WCAG AA"],
            "_note": "使用降级模板 (API 不可用)",
        }
