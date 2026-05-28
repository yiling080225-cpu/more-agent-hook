"""多模态 Agent: 调用 Gemini/Anthropic API 分析文本/图像，生成 UI 设计规范"""

import base64
import json
import structlog
from typing import Any, Dict, List, Optional

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

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
    model=settings.model_for("multimodal"),
    max_context_tokens=1048576,
)


class MultimodalAgent(BaseAgent):
    """多模态理解 Agent — 优先 Gemini，无 Key 时用 Anthropic/DeepSeek"""

    def __init__(self):
        super().__init__(card=MULTIMODAL_AGENT_CARD)
        self._gemini_client = None
        self._anthropic_client = None
        self.model = settings.model_for("multimodal")

        # 初始化 Gemini 客户端 (可选)
        if settings.gemini_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=settings.gemini_key)
                logger.info("multimodal_using_gemini")
            except ImportError:
                logger.warning("google_genai_not_installed")

        # 初始化 Anthropic 客户端
        if not self._gemini_client:
            try:
                from anthropic import AsyncAnthropic
                cfg = settings.client_for("multimodal")
                self._anthropic_client = AsyncAnthropic(**cfg)
                logger.info("multimodal_using_anthropic")
            except ImportError:
                logger.warning("anthropic_not_installed")

        self._use_gemini = self._gemini_client is not None
        self._use_anthropic = self._anthropic_client is not None

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        text = task.get("text", "")
        images = task.get("images", [])
        task_type = task.get("task_type", "ui_design")

        if self._use_gemini:
            return await self._execute_gemini(text, images, task_type, context, task)
        elif self._use_anthropic:
            return await self._execute_anthropic(text, images, task_type, context, task)
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
        self, text: str, images: List[str], task_type: str, context: Dict[str, Any], task: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        from google.genai import types

        prompt_text = self._build_prompt(text, task_type, task)
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
        self, text: str, images: List[str], task_type: str, context: Dict[str, Any], task: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(text, task_type, task)

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
            raw = extract_text(resp.content)
            clean = raw.strip()

            # Clean any markdown code block wrapping
            if clean.startswith("```"):
                lines = clean.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                clean = "\n".join(lines).strip()

            # Try standard JSON parse
            try:
                result = json.loads(clean)
            except (json.JSONDecodeError, ValueError):
                # Try to repair: extract content by key (handles unescaped quotes in HTML/SVG)
                result = self._extract_structured_content(clean, text)
                if result is None:
                    # DeepSeek may output raw HTML instead of JSON {html: ...}
                    if clean.startswith("<") or "<!DOCTYPE" in clean[:50]:
                        result = {"html": clean, "description": "Generated HTML page"}
                    else:
                        logger.warning("multimodal_parse_failed", raw_preview=raw[:200])
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

    def _build_prompt(self, text: str, task_type: str, task: Dict[str, Any] = None) -> str:
        """构建 prompt，注入用户偏好 (风格/主题/输出框架)。"""
        style_hint = ""
        task = task or {}
        style = task.get("style", "")
        theme = task.get("theme", "")
        output_format = task.get("output_format", "")

        if style:
            style_hint += f"\n设计风格要求: {style}\n"

        if theme:
            if theme.startswith("#"):
                style_hint += f"自定义主色调: {theme}\n"
            else:
                style_hint += f"主色调: {theme}\n"

        if output_format and output_format != "both":
            style_hint += f"输出框架: {output_format}\n"

        files_hint = self._format_files_hint(task)

        prompts = {
            "ui_design": f"""你是一个资深 UI/UX 设计师。根据用户的描述和图片，生成一份完整的 UI 设计规范 (纯 JSON 格式，不要 markdown 代码块)。
{style_hint}
返回 JSON:
{{
    "design_system": {{
        "color_palette": ["#hex"],
        "typography": {{"heading": "font", "body": "font"}},
        "spacing": "值",
        "border_radius": "值"
    }},
    "pages": [{{"name": "页面名", "components": ["组件"], "layout": "布局"}}],
    "component_library": {{"组件名": {{"props": [], "states": [], "description": ""}}}},
    "interactions": ["交互描述"],
    "accessibility": ["无障碍要点"]
}}

用户需求: {text}""",

            "web_page": f"""你是一个资深前端设计师和全栈开发者。根据用户需求，生成一个完整的、可直接在浏览器中打开的 HTML 页面。
{style_hint}

技术要求:
- 单文件 HTML，所有 CSS 写在 <style> 标签中，JS 写在 <script> 标签中
- 使用现代 CSS (flexbox/grid, CSS 变量, 过渡动画)
- 响应式设计 (mobile-first, 断点 768px/1024px)
- 美观的视觉设计——不要默认浏览器样式
- 真实的中文内容，不要 Lorem ipsum
- 交互效果: hover 状态、过渡动画、微交互
- 无障碍: aria 标签、键盘导航、足够的色彩对比度

返回纯 JSON:
{{
    "html": "完整的 HTML 代码 (含 <!DOCTYPE html> 声明)",
    "description": "页面功能说明",
    "features": ["关键特性列表"]
}}

用户需求: {text}""",

            "svg_diagram": f"""你是一个资深图形/数据可视化设计师。根据用户描述，生成一个精美的 SVG 矢量图。
{style_hint}

要求:
- 完整独立的 SVG 元素 (含 xmlns, viewBox)
- 清晰的视觉层次和信息架构
- 合适的颜色搭配和字体大小
- 响应式 viewBox，可在不同尺寸下缩放
- 如果是流程图/架构图: 使用圆角矩形、清晰箭头、分组框
- 如果是数据图表: 坐标轴、标签、图例完整

返回纯 JSON:
{{
    "svg": "<svg>...</svg> (完整 SVG 代码)",
    "description": "图表说明",
    "viewBox": "0 0 W H"
}}

用户需求: {text}""",

            "cad_from_sketch": f"""你是一个 CAD/机械工程师。用户提供了一张草图/图片，请分析它并生成参数化的 3D 模型代码。

分析步骤:
1. 识别草图中的形状 (圆柱、立方体、孔洞、倒角等)
2. 估算尺寸比例关系
3. 生成 Python build123d 3D 模型代码

build123d 语法要点 (基于 CadQuery/OCP):
```python
from build123d import *
# 基本形状
box = Box(length, width, height)
cylinder = Cylinder(radius, height)
sphere = Sphere(radius)
cone = Cone(bottom_radius, top_radius, height)

# 布尔运算
body = box - cylinder  # 差集
body = box + cylinder  # 并集
body = box & cylinder  # 交集

# 位置变换
body = Pos(x, y, z) * body
body = Rot(X=90) * body

# 边操作: fillet, chamfer
body = fillet(body.edges(), radius)

# 草图拉伸
with BuildSketch() as sk:
    Rectangle(width, height)
body = extrude(sk, amount)

# 导出
from build123d import export_step, export_stl
export_step(body, "output.step")
export_stl(body, "output.stl")
```

返回纯 JSON:
{{
    "analysis": "对草图的描述分析 (形状/尺寸/结构)",
    "estimated_dimensions": {{"unit": "mm", "width": N, "height": N, "depth": N}},
    "build123d_code": "完整的参数化 build123d Python 代码 (含变量定义、注释和导出语句)",
    "design_notes": "关键设计决策说明"
}}

用户需求: {text}""",

            "build123d_model": f"""你是一个机械 CAD 工程师，精通 build123d (基于 CadQuery/OCP) 参数化建模。
根据用户需求，生成完整的 build123d Python 代码来创建 3D 模型。

{style_hint}

建模规范:
- 单位: 毫米 (mm)
- 原点: 零件中心或装配体基准面
- 基面: XY 平面，拉伸方向为 +Z
- 输出: 封闭的实体 (solid)，正体积
- 壁厚 (未指定时): 2.0-3.0 mm
- 倒角半径 (装饰性): 1.0-3.0 mm
- M3/M4/M5 通孔: 3.4/4.5/5.5 mm

build123d 代码结构:
```python
from build123d import *
from math import pi, sin, cos, tan, sqrt

# === 参数定义 ===
length = 100.0
width = 60.0
height = 25.0
wall_thickness = 2.5
fillet_radius = 2.0

# === 主体建模 ===
body = Box(length, width, height)

# === 特征 (孔洞、倒角等) ===
hole = Cylinder(radius=3.4, height=wall_thickness * 2)
body -= Pos(length/2 - 10, width/2 - 10, 0) * hole
body = fillet(body.edges(), radius=fillet_radius)

# === 导出 ===
export_step(body, "part_name.step")
export_stl(body, "part_name.stl")
```

返回纯 JSON:
{{
    "build123d_code": "完整的、可直接运行的 build123d Python 代码 (含参数定义、建模、导出)",
    "parameters": {{"unit": "mm"}},
    "features": ["使用的建模特征列表 (Box, Cylinder, fillet, extrude 等)"],
    "expected_outputs": ["part_name.step", "part_name.stl"],
    "design_notes": "设计决策和假设说明"
}}

用户需求: {text}""",

            "cad_model": f"""你是一个机械 CAD 工程师。根据用户需求，生成参数化的 3D 模型代码。

{style_hint}

返回纯 JSON:
{{
    "build123d_code": "完整的参数化 build123d Python 代码 (含参数定义、注释和导出语句)",
    "parameters": {{"unit": "mm"}},
    "features": ["使用的建模特征列表"],
    "design_notes": "关键设计决策说明"
}}

用户需求: {text}""",

            "visual_analysis": "分析这张图片/设计的视觉元素：1.颜色方案 2.布局结构 3.UI组件 4.视觉层次 5.改进建议。用户补充: " + text,

            "content_extraction": "提取图片中的所有文字和结构化信息，返回纯 JSON。用户补充: " + text,
        }
        return prompts.get(task_type, prompts["ui_design"]) + files_hint

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

    def _extract_structured_content(self, text: str, user_text: str) -> Optional[Dict[str, Any]]:
        """从格式不佳的 JSON 中提取结构化内容 (处理 LLM 未正确转义 HTML/SVG 引号的情况)"""
        import re

        result: Dict[str, Any] = {}

        # 提取 html 块: "html": "..." 或 "html": " 之后的 <!DOCTYPE 到结束
        html_match = re.search(r'"html"\s*:\s*"(?P<html><!DOCTYPE[\s\S]+?)(?="\s*[,}]|\Z)', text)
        if not html_match:
            html_match = re.search(r'"html"\s*:\s*"(?P<html><html[\s\S]+?</html>)', text, re.IGNORECASE)
        if not html_match:
            # raw HTML from opening < to closing </html> (not JSON-wrapped)
            html_match = re.search(r'(?P<html><!DOCTYPE[\s\S]+?</html>)', text, re.IGNORECASE)
        if html_match:
            result["html"] = html_match.group("html")
            result.setdefault("description", "")

        # 提取 svg 块
        svg_match = re.search(r'"svg"\s*:\s*"(?P<svg><svg[\s\S]+?</svg>)', text, re.IGNORECASE)
        if svg_match:
            result["svg"] = svg_match.group("svg")
            result.setdefault("description", "SVG diagram")

        # 提取 build123d_code 块
        code_match = re.search(r'"build123d_code"\s*:\s*"(?P<code>from build123d[\s\S]+?)(?="\s*[,}]|\Z)', text)
        if not code_match:
            code_match = re.search(r'"build123d_code"\s*:\s*"(?P<code>[\s\S]{200,}?)(?="\s*[,}]|\Z)', text)
        if code_match:
            result["build123d_code"] = code_match.group("code")
            result.setdefault("parameters", {"unit": "mm"})

        if result:
            logger.info("multimodal_extracted", keys=list(result.keys()))
            return result
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
