"""代码 Agent: 调用 Claude API 生成前端/后端代码"""

import structlog
from typing import Any, Dict

from anthropic import AsyncAnthropic

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent

logger = structlog.get_logger()

CODE_AGENT_CARD = AgentCard(
    name="secure_code_agent",
    description="复杂代码生成、类型安全的后端/前端开发",
    version="1.0.0",
    capabilities={
        "input": ["text", "code", "json"],
        "output": ["code", "json"],
        "skills": [
            "fastapi_backend",
            "nextjs_frontend",
            "postgresql_schema",
            "api_design",
            "type_safe_code",
            "security_best_practices",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.code_agent_port}/a2a",
    model=settings.code_model,
    max_context_tokens=200000,
)


SYSTEM_PROMPTS = {
    "frontend": """你是一个资深前端工程师。根据 UI 设计规范生成生产级代码。

技术栈: Next.js 14 + TypeScript + Tailwind CSS

规则:
- 使用 App Router (app/ 目录)
- 组件使用 'use client' 指令当需要交互
- TypeScript 严格模式，完整的 Props 类型定义
- Tailwind CSS 类名，响应式设计 (mobile-first)
- 无障碍: aria-label, role, keyboard navigation
- 错误边界 + loading 状态
- 只输出代码，不要解释

输出格式: JSON
{
    "files": [
        {"path": "相对路径", "content": "文件内容"}
    ],
    "dependencies": {"package": "version"},
    "setup_instructions": "简要说明"
}""",

    "backend": """你是一个资深后端工程师。根据 PRD 和数据模型生成生产级 API。

技术栈: FastAPI + Python 3.12 + SQLAlchemy 2.0 + PostgreSQL

规则:
- Pydantic v2 模型定义请求/响应
- 异步数据库操作 (asyncpg)
- 完整的错误处理 (HTTPException)
- 输入验证 + 类型安全
- 安全: SQL 注入防护, CORS, rate limiting 留接口
- 幂等性设计 (支付/写入操作)
- 只输出代码，不要解释

输出格式: JSON
{
    "files": [
        {"path": "相对路径", "content": "文件内容"}
    ],
    "api_endpoints": ["GET /...", "POST /..."],
    "dependencies": {"package": "version"},
    "setup_instructions": "简要说明"
}""",
}


SVG_PROMPT = """你是一个资深图形/数据可视化设计师。根据需求生成精美的 SVG 矢量图。

要求:
- 完整独立的 SVG 元素，含 xmlns 和 viewBox
- 清晰的视觉层次和信息架构
- 合适的颜色搭配
- 响应式 viewBox，可缩放
- 流程图/架构图: 圆角矩形、清晰箭头、分组框
- 数据图表: 坐标轴、标签、图例完整

只输出 SVG 代码，不要 JSON 包装，不要 markdown 代码块。"""


OPENSCAD_PROMPT = """你是一个 CAD/3D 建模工程师。根据需求生成 OpenSCAD 参数化代码。

OpenSCAD 语法:
- cube([x, y, z], center=true/false)
- cylinder(h, r, r2, center=true/false, $fn=100)
- difference() { body; cutout; }
- union() { part1; part2; }
- intersection() { a; b; }
- translate([x, y, z]) child()
- rotate([x, y, z]) child()
- linear_extrude(height) 2d_shape
- circle(r, $fn=100)
- square([x, y], center=true)

要求:
- 精确的参数化尺寸
- 模块化设计: 每个零件封装为 module
- 清晰的注释说明
- 变量定义在顶部
- 使用 $fn 控制曲面精度

只输出 OpenSCAD 代码，不要 JSON 包装，不要 markdown 代码块。"""


WEB_HTML_PROMPT = """你是一个资深前端设计师。根据需求生成完整的 HTML 页面。

要求:
- 单文件，所有 CSS 内嵌在 <style>，JS 在 <script>
- 现代 CSS (flexbox/grid, CSS 变量, 过渡动画)
- 响应式设计 mobile-first
- 美观的视觉设计
- 真实中文内容
- 交互效果

只输出完整 HTML 代码，不要 JSON 包装。"""


class CodeAgent(BaseAgent):
    """代码生成 Agent — 基于 Claude API"""

    def __init__(self):
        super().__init__(card=CODE_AGENT_CARD)
        kwargs = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        self.client = AsyncAnthropic(**kwargs)
        self.model = settings.code_model

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("type", "backend")
        spec = task.get("spec", task)
        language = task.get("language", "python")

        if task_type == "frontend":
            return await self._generate_frontend(spec, context)
        elif task_type == "backend":
            return await self._generate_backend(spec, context)
        elif task_type == "svg":
            return await self._generate_svg(spec, context)
        elif task_type == "openscad":
            return await self._generate_openscad(spec, context)
        elif task_type == "web_html":
            return await self._generate_web_html(spec, context)
        else:
            return await self._generate_generic(spec, language, context)

    async def _generate_frontend(self, spec: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成前端代码"""
        import json
        spec_str = json.dumps(spec, ensure_ascii=False, indent=2) if isinstance(spec, dict) else str(spec)

        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=SYSTEM_PROMPTS["frontend"],
                messages=[{"role": "user", "content": f"根据以下 UI 设计规范生成前端代码:\n\n{spec_str}"}],
            )
            # 尝试解析 JSON 响应
            content = resp.content[0].text
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                result = {
                    "files": [{"path": "app/page.tsx", "content": content}],
                    "dependencies": {},
                    "setup_instructions": "代码生成完成，JSON 解析失败，返回原始内容",
                }

            return {
                "success": True,
                "code": result,
                "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
                "model_used": self.model,
            }
        except Exception as e:
            logger.error("code_agent_frontend_error", error=str(e))
            return {"success": False, "error": str(e), "code": None}

    async def _generate_backend(self, spec: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成后端代码"""
        import json
        spec_str = json.dumps(spec, ensure_ascii=False, indent=2) if isinstance(spec, dict) else str(spec)

        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=SYSTEM_PROMPTS["backend"],
                messages=[{"role": "user", "content": f"根据以下规范生成后端 API 代码:\n\n{spec_str}"}],
            )
            content = resp.content[0].text
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                result = {
                    "files": [{"path": "main.py", "content": content}],
                    "api_endpoints": [],
                    "dependencies": {},
                    "setup_instructions": "代码生成完成",
                }

            return {
                "success": True,
                "code": result,
                "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
                "model_used": self.model,
            }
        except Exception as e:
            logger.error("code_agent_backend_error", error=str(e))
            return {"success": False, "error": str(e), "code": None}

    async def _generate_generic(
        self, spec: Any, language: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """通用代码生成"""
        spec_str = str(spec)
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=f"你是一个资深 {language} 工程师。生成干净、类型安全、有错误处理的代码。只输出代码。",
                messages=[{"role": "user", "content": spec_str}],
            )
            return {
                "success": True,
                "code": resp.content[0].text,
                "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
                "model_used": self.model,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _generate_svg(self, spec: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成 SVG 矢量图"""
        import json
        spec_str = json.dumps(spec, ensure_ascii=False, indent=2) if isinstance(spec, dict) else str(spec)
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SVG_PROMPT,
                messages=[{"role": "user", "content": f"请生成以下 SVG:\n\n{spec_str}"}],
            )
            svg_code = resp.content[0].text.strip()
            # 清理 markdown 代码块包装
            if svg_code.startswith("```"):
                svg_code = svg_code.split("```")[1]
                if svg_code.startswith("svg"):
                    svg_code = svg_code[3:]
            return {
                "success": True,
                "code": svg_code.strip(),
                "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
                "model_used": self.model,
            }
        except Exception as e:
            logger.error("code_agent_svg_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _generate_openscad(self, spec: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成 OpenSCAD 3D 模型"""
        import json
        spec_str = json.dumps(spec, ensure_ascii=False, indent=2) if isinstance(spec, dict) else str(spec)
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=OPENSCAD_PROMPT,
                messages=[{"role": "user", "content": f"请生成以下 3D 模型的 OpenSCAD 代码:\n\n{spec_str}"}],
            )
            code = resp.content[0].text.strip()
            if code.startswith("```"):
                code = code.split("```")[1]
                if code.startswith("openscad") or code.startswith("scad"):
                    code = code[code.index("\n"):]
            return {
                "success": True,
                "code": code.strip(),
                "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
                "model_used": self.model,
            }
        except Exception as e:
            logger.error("code_agent_openscad_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _generate_web_html(self, spec: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成完整 HTML 页面"""
        import json
        spec_str = json.dumps(spec, ensure_ascii=False, indent=2) if isinstance(spec, dict) else str(spec)
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=WEB_HTML_PROMPT,
                messages=[{"role": "user", "content": f"请生成以下 HTML 页面:\n\n{spec_str}"}],
            )
            html = resp.content[0].text.strip()
            if html.startswith("```"):
                html = html.split("```")[1]
                if html.startswith("html"):
                    html = html[4:]
            return {
                "success": True,
                "code": html.strip(),
                "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
                "model_used": self.model,
            }
        except Exception as e:
            logger.error("code_agent_html_error", error=str(e))
            return {"success": False, "error": str(e)}
