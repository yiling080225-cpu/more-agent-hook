"""联邦总调度器: 智能路由 + 任务委托 + 12 Agent 协作管道 + Human-in-the-loop"""

import os
import structlog
from pathlib import Path
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
from ..utils._content import extract_text
from ..monitoring.token_tracker import token_tracker

logger = structlog.get_logger()

ROUTING_PROMPT = """你是一个 12 Agent 联邦的任务路由器。根据用户输入和偏好设置，选择最合适的 Agent。

可用 Agent (4 层架构):

[设计层]
- multimodal_design_agent: 图像/视频/音频多模态理解，UI设计规范，网页生成，SVG图表，CAD/3D建模
- ux_interaction_agent: 交互设计，用户体验，动效设计，可用性分析，线框图生成
- brand_creative_agent: 品牌视觉系统，色彩搭配，字体规范，设计Token，风格指南

[工程层]
- secure_code_agent: 前端/后端代码生成，API设计，数据库Schema，类型安全开发
- testing_qa_agent: 测试用例生成，自动化测试(pytest/jest)，边界条件检测，覆盖率分析
- devops_deploy_agent: CI/CD配置，Docker/K8s编排，GitHub Actions，部署脚本
- code_review_agent: 代码审查，安全漏洞检测，多轮辩论式审查

[战略层]
- project_architect_agent: 架构规划，技术栈选型，模块划分，系统设计
- prompt_engineer_agent: 提示词设计/调试/优化，A/B测试，结构化输出设计
- crew_collaboration_agent: 多角色对话协作，内容文案，市场分析，创意头脑风暴

[基础层]
- knowledge_rag_agent: 文档解析，向量检索，RAG问答，上下文增强
- security_audit_agent: 渗透测试，合规检查，OWASP扫描，漏洞评估，代码加固

选择规则:
1. 图片/视频/音频/UI设计/网页/SVG/CAD/3D -> multimodal_design_agent
2. 交互设计/UX/动效/可用性/线框图/用户体验 -> ux_interaction_agent
3. 品牌设计/色彩系统/字体/视觉识别/设计规范 -> brand_creative_agent
4. 代码生成/API开发/数据库/功能实现/写代码 -> secure_code_agent
5. 测试/单元测试/集成测试/E2E/覆盖率/测试用例 -> testing_qa_agent
6. 部署/CI/CD/Docker/K8s/Kubernetes/GitHub Actions -> devops_deploy_agent
7. 代码审查/代码评审/Code Review/查漏洞 -> code_review_agent
8. 架构规划/技术选型/系统设计/模块划分 -> project_architect_agent
9. 提示词/Prompt设计/调试/优化 -> prompt_engineer_agent
10. 多角色协作/内容文案/市场分析/头脑风暴 -> crew_collaboration_agent
11. 文档理解/知识检索/RAG/查资料 -> knowledge_rag_agent
12. 安全审计/渗透测试/OWASP/合规检查/漏洞评估 -> security_audit_agent
13. 全栈项目/从零构建/完整系统 -> workflow_orchestrator (触发多阶段管道)
14. 简单问答: 直接回答，不委托Agent

若用户上传了文件，将以 [文件内容摘要]...[/文件内容摘要] 形式给出前 1500 字 — 优先采信文件内容。

返回 JSON:
{
    "agent": "agent_name 或 null",
    "reason": "选择理由",
    "is_pipeline": true/false,
    "pipeline": "engineering"/"design"/"strategy" 或 null,
    "extracted_requirements": "摘要",
    "task_type": "..."
}"""


class FederationSupervisor:
    """联邦总调度器 — 12 Agent + 3 条协作管道"""

    def __init__(self):
        self.router_client = None
        self.router_anthropic = None
        self.router_model = settings.model_for("router")

        if settings.gemini_key and HAS_GENAI:
            try:
                self.router_client = genai.Client(api_key=settings.gemini_key)
                logger.info("supervisor_router_using_gemini")
            except Exception:
                pass

        if not self.router_client:
            try:
                from anthropic import AsyncAnthropic
                cfg = settings.client_for("router")
                self.router_anthropic = AsyncAnthropic(**cfg)
                logger.info("supervisor_router_using_anthropic")
            except Exception:
                pass

        self._active_workflows: Dict[str, Dict[str, Any]] = {}

    async def route_and_execute(self, user_input: UserInput) -> Dict[str, Any]:
        """分析用户输入，路由到最合适的 Agent 并执行 (支持管道编排)"""
        import uuid
        thread_id = user_input.context.get("thread_id") or str(uuid.uuid4())

        files_markdown = ""
        if user_input.files:
            from ..utils.file_extraction import extract_files_to_markdown
            files_markdown = extract_files_to_markdown(user_input.files)

        routing = await self._route_task(user_input, files_markdown=files_markdown)

        # 管道模式优先: agent 为 None 但 is_pipeline=True 时触发多 Agent 协作
        if routing.get("is_pipeline"):
            return await self._execute_pipeline(
                routing, user_input, files_markdown, thread_id
            )

        if routing["agent"] is None:
            return {
                "thread_id": thread_id,
                "routing": routing,
                "result": {
                    "status": "completed",
                    "thread_id": thread_id,
                    "message": routing.get("direct_response", "任务已理解，无需委托 Agent"),
                },
                "requires_human_review": False,
            }

        # 单 Agent 模式
        return await self._execute_single(
            routing["agent"], routing, user_input, files_markdown, thread_id
        )

    async def _execute_single(
        self, agent_name: str, routing: dict, user_input: UserInput,
        files_markdown: str, thread_id: str
    ) -> Dict[str, Any]:
        """单 Agent 执行"""
        agent_url = agent_registry.get_agent_url(agent_name)
        if not agent_url:
            return {
                "thread_id": thread_id,
                "routing": routing,
                "result": {"status": "failed", "thread_id": thread_id,
                           "error": f"Agent '{agent_name}' 未注册或不可用"},
                "errors": [f"Agent '{agent_name}' 未注册"],
                "requires_human_review": False,
            }

        task = self._build_task(user_input, files_markdown, routing, thread_id)
        response = await a2a_client.send_task(
            endpoint=agent_url, task=task, agent_name=agent_name, context=user_input.context,
        )

        # 记录 Agent LLM token 消耗
        self._track_agent_tokens(agent_name, response)

        # 检查并透传 Agent 侧错误
        errors = []
        response_dict = response.model_dump()
        if response.status == TaskStatus.FAILED:
            agent_error = response.error or response_dict.get("error", "")
            if not agent_error:
                inner = response_dict.get("result", {})
                if isinstance(inner, dict):
                    agent_error = inner.get("error", "")
            if agent_error:
                errors.append(f"[{agent_name}] {agent_error}")
                logger.warning("agent_execution_failed", agent=agent_name, error=str(agent_error)[:200])

        preview_path = self._save_direct_output(
            routing.get("task_type", ""), response_dict, thread_id
        )
        needs_review = self._assess_review_need(agent_name, response)

        result = {
            "thread_id": thread_id,
            "routing": routing,
            "result": response_dict,
            "requires_human_review": needs_review,
            "preview_path": preview_path,
        }
        if errors:
            result["errors"] = errors
        return result

    async def _execute_pipeline(
        self, routing: dict, user_input: UserInput, files_markdown: str, thread_id: str
    ) -> Dict[str, Any]:
        """管道模式: 支持顺序执行和并行组。

        Flat list: ["agent_a", "agent_b"] → A→B 顺序
        Nested list: [["agent_a", "agent_b"], "agent_c"] → [A∥B]→C 组内并步组间顺序
        """
        import asyncio as _asyncio

        pipe_name = routing.get("pipeline", "engineering")
        pipe_map = {
            "design": settings.pipeline_design,
            "engineering": settings.pipeline_engineering,
            "strategy": settings.pipeline_strategy,
            "full_flow": settings.pipeline_full_flow,
        }
        agents = pipe_map.get(pipe_name, settings.pipeline_engineering)

        results = []
        stage_num = 0
        all_previous_outputs = []

        async def _execute_single_agent(agent_name: str, task: dict) -> dict:
            """执行单个 Agent (供并行组使用)"""
            agent_url = agent_registry.get_agent_url(agent_name)
            if not agent_url:
                return {"agent": agent_name, "status": "skipped", "error": "未注册"}
            response = await a2a_client.send_task(
                endpoint=agent_url, task=task, agent_name=agent_name,
                context=user_input.context,
            )
            return {
                "agent": agent_name,
                "result": response.model_dump(),
                "status": response.status.value,
            }

        for item in agents:
            stage_num += 1

            # 检测是否为并行组 (嵌套列表)
            if isinstance(item, list):
                # ── 并行组: 组内所有 Agent 并发执行 ──
                group_agents = item
                tasks_for_group = []
                for agent_name in group_agents:
                    task = self._build_task(user_input, files_markdown, routing, thread_id)
                    if all_previous_outputs:
                        task["text"] = (
                            f"前面阶段的产出汇总:\n"
                            f"{chr(10).join(all_previous_outputs[-3:])[:4000]}\n\n"
                            f"基于以上产出继续处理，原始需求:\n{user_input.text}"
                        )
                    task["pipeline_stage"] = f"{stage_num}/{len(agents)}"
                    task["pipeline_agent"] = agent_name
                    tasks_for_group.append((agent_name, task))

                # asyncio.gather 并行执行
                group_results = await _asyncio.gather(
                    *[_execute_single_agent(name, t) for name, t in tasks_for_group],
                    return_exceptions=True,
                )

                for r in group_results:
                    if isinstance(r, Exception):
                        results.append({"agent": "unknown", "stage": stage_num,
                                       "status": "failed", "error": str(r)})
                    else:
                        r["stage"] = stage_num
                        results.append(r)
                        all_previous_outputs.append(str(r.get("result", ""))[:1500])
                        logger.info("pipeline_parallel_done", agent=r.get("agent"),
                                    stage=stage_num, pipeline=pipe_name, thread_id=thread_id)
            else:
                # ── 顺序执行 ──
                agent_name = item
                task = self._build_task(user_input, files_markdown, routing, thread_id)
                if all_previous_outputs:
                    task["text"] = (
                        f"前面阶段的产出汇总:\n"
                        f"{chr(10).join(all_previous_outputs[-3:])[:4000]}\n\n"
                        f"基于以上产出继续处理，原始需求:\n{user_input.text}"
                    )
                task["pipeline_stage"] = f"{stage_num}/{len(agents)}"
                task["pipeline_agent"] = agent_name

                r = await _execute_single_agent(agent_name, task)
                r["stage"] = stage_num
                results.append(r)
                all_previous_outputs.append(str(r.get("result", ""))[:1500])
                logger.info("pipeline_stage_complete", agent=agent_name, stage=stage_num,
                            pipeline=pipe_name, thread_id=thread_id)

        # 管道最终产出写入 preview/
        last = results[-1] if results else {}
        preview_path = self._save_direct_output(
            routing.get("task_type", ""), last.get("result", {}), thread_id
        )

        return {
            "thread_id": thread_id,
            "routing": routing,
            "pipeline": pipe_name,
            "pipeline_results": results,
            "result": last.get("result", {}),
            "requires_human_review": True,
            "preview_path": preview_path,
        }

    def _build_task(
        self, user_input: UserInput, files_markdown: str, routing: dict, thread_id: str
    ) -> Dict[str, Any]:
        return {
            "text": user_input.text,
            "images": user_input.images,
            "videos": user_input.videos,
            "audio": user_input.audio,
            "files": user_input.files,
            "files_markdown": files_markdown,
            "task_type": routing.get("task_type", ""),
            "extracted_requirements": routing.get("extracted_requirements", ""),
            "thread_id": thread_id,
            **{k: v for k, v in user_input.context.items()
               if k not in ("sandbox", "allow_search")},
        }

    async def _route_task(self, user_input: UserInput, files_markdown: str = "") -> Dict[str, Any]:
        """路由任务：LLM 优先，确定性产出类型可走快速通道，关键词仅作最终降级。"""
        has_multimodal = bool(
            user_input.images or user_input.videos or user_input.audio or user_input.files
        )
        extra_parts = []
        if has_multimodal:
            extra_parts.append("[用户上传了图片/视频/音频/文件]")
        ctx = user_input.context or {}
        if ctx.get("style"):
            extra_parts.append(f"[偏好风格: {ctx['style']}]")
        if ctx.get("theme"):
            extra_parts.append(f"[偏好主题: {ctx['theme']}]")
        if ctx.get("output_format"):
            extra_parts.append(f"[输出框架: {ctx['output_format']}]")
        if files_markdown:
            snippet = files_markdown[:1500].strip()
            extra_parts.append(f"[文件内容摘要]\n{snippet}\n[/文件内容摘要]")
        extra = " " + " ".join(extra_parts) if extra_parts else ""

        # 策略 0: 确定性产出类型 / 管道触发 — 快速通道，无需 LLM
        kw = self._keyword_routing(user_input, has_multimodal, files_markdown=files_markdown)
        fast_path_types = (
            "web_page", "svg_diagram", "cad_model", "cad_from_sketch", "build123d_model",
        )
        if kw.get("task_type") in fast_path_types or kw.get("is_pipeline"):
            logger.info("route_fast_path", task_type=kw.get("task_type"), agent=kw.get("agent"))
            return kw

        # 策略 1: LLM 路由 (主路径) — Gemini / Anthropic Router
        llm_routing = None
        if self.router_client and HAS_GENAI:
            llm_routing = await self._route_via_gemini(user_input, extra, has_multimodal)
        elif self.router_anthropic:
            llm_routing = await self._route_via_anthropic(user_input, extra, has_multimodal)

        # 策略 2: LLM 路由成功 → 直接返回，附带 LLM 路由的 task_type 覆盖关键词结果
        if llm_routing and llm_routing.get("agent"):
            llm_routing["task_type"] = llm_routing.get("task_type") or kw.get("task_type", "")
            logger.info("route_llm_primary", agent=llm_routing.get("agent"),
                        reason=llm_routing.get("reason"))
            return llm_routing

        # 策略 3: LLM 路由失败或返回 agent=null → 关键词降级
        logger.info("route_keyword_fallback", agent=kw.get("agent"), reason=kw.get("reason"))
        return kw

    async def _route_via_gemini(self, user_input: UserInput, extra: str, has_multimodal: bool) -> Dict[str, Any]:
        try:
            resp = self.router_client.models.generate_content(
                model=self.router_model,
                contents=f"{ROUTING_PROMPT}\n\n用户输入: {user_input.text}{extra}",
                config=types.GenerateContentConfig(
                    temperature=0.1, max_output_tokens=512,
                    response_mime_type="application/json",
                ),
            )
            # 记录 Router LLM token 消耗
            if hasattr(resp, "usage_metadata") and resp.usage_metadata:
                router_tokens = getattr(resp.usage_metadata, "total_token_count", 0)
                if router_tokens:
                    token_tracker.record(router_tokens, provider="gemini", agent="router",
                                         model=self.router_model, task_type="routing")
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
                model=self.router_model, max_tokens=512,
                messages=[{"role": "user",
                           "content": f"{ROUTING_PROMPT}\n\n用户输入: {user_input.text}{extra}"}],
            )
            # 记录 Router LLM token 消耗
            if hasattr(resp, "usage") and resp.usage:
                router_tokens = resp.usage.input_tokens + resp.usage.output_tokens
                token_tracker.record(router_tokens, provider=settings._preferred_provider("router"),
                                     agent="router", model=self.router_model, task_type="routing")
            import json, re
            text = extract_text(resp.content)
            try:
                routing = json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r'\{[\s\S]*\}', text)
                routing = json.loads(match.group()) if match else {"agent": None}
            if has_multimodal and routing.get("agent") is None:
                routing["agent"] = "multimodal_design_agent"
            return routing
        except Exception as e:
            logger.warning("anthropic_routing_failed", error=str(e))
            return self._keyword_routing(user_input, has_multimodal)

    def _keyword_routing(self, user_input: UserInput, has_multimodal: bool, files_markdown: str = "") -> Dict[str, Any]:
        """降级路由: 12 Agent 关键词匹配 + 管道触发检测"""
        text = user_input.text
        text_lower = text.lower()
        file_snippet = (files_markdown[:2000] if files_markdown else "")
        file_snippet_lower = file_snippet.lower()
        combined = text + "\n" + file_snippet
        combined_lower = text_lower + "\n" + file_snippet_lower

        # ── 产出类型关键词 ──
        web_keywords = ["网页", "页面", "网站", "html", "前端页面", "生成页面", "做个页面", "写个页面",
                        "landing", "首页", "着陆页", "webpage", "web page", "homepage", "官网", "主页"]
        diagram_keywords = ["画图", "画个图", "流程图", "svg", "图表", "架构图", "示意图", "思维导图",
                            "draw", "diagram", "flowchart", "chart", "图形", "可视化", "脑图"]
        cad_keywords = ["cad", "3d", "三维", "模型", "建模", "零件", "齿轮", "机械", "打印",
                        "openscad", "stl", "step", "草图", "草稿", "工程图",
                        "支架", "外壳", "壳体", "底座", "法兰",
                        "手机架", "手机壳", "轴", "弹簧", "凸轮", "连杆"]
        build123d_keywords = ["build123d", "step文件", "step 文件", "stp", "制造",
                             "cnc", "数控", "装配", "装配体", "螺栓", "轴承", "齿轮箱"]

        # ── 12 Agent 关键词 (按优先级) ──
        ux_keywords = ["交互设计", "ux", "可用性", "usability", "动效", "motion", "动画效果",
                       "线框图", "wireframe", "用户旅程", "user journey", "信息架构", "体验优化",
                       "交互原型", "用户体验", "user experience", "交互细节"]
        brand_keywords = ["品牌设计", "brand", "视觉系统", "设计系统", "design system", "色彩方案",
                         "配色", "字体搭配", "视觉规范", "vi设计", "品牌规范", "设计token",
                         "design token", "风格指南", "style guide", "品牌色", "品牌识别"]
        test_keywords = ["测试", "test", "单元测试", "unit test", "集成测试", "integration test",
                        "e2e", "端到端", "覆盖率", "coverage", "pytest", "jest", "测试用例",
                        "自动化测试", "回归测试", "regression test", "性能测试", "边界测试"]
        devops_keywords = ["部署", "deploy", "docker", "k8s", "kubernetes", "ci/cd", "ci cd",
                          "pipeline", "github action", "容器化", "负载均衡", "扩容",
                          "运维", "devops", "terraform", "ansible", "dockerfile", "docker-compose"]
        review_keywords = ["审查", "review", "代码审查", "code review", "pr review",
                          "代码质量", "代码规范", "lint", "重构建议"]
        architect_keywords = ["架构", "技术选型", "系统设计", "模块划分", "框架设计", "项目规划",
                             "architecture", "tech stack", "system design", "方案设计",
                             "架构设计", "框架规划", "项目框架", "技术方案", "技术架构",
                             "软件架构", "整体设计", "选型", "微服务", "单体架构"]
        prompt_keywords = ["提示词", "prompt", "prompt engineering", "system prompt", "优化提示",
                          "调试提示", "设计提示", "提示词工程", "提示词设计", "提示词优化",
                          "提示词测试", "few-shot", "结构化输出", "prompt template", "提示词模板"]
        crew_keywords = ["多角色", "文案", "copywriting", "市场分析", "头脑风暴", "brainstorm",
                        "创意", "内容创作", "广告语", "slogan", "软文", "营销文案",
                        "角色扮演", "角色模拟", "persona", "协作讨论"]
        knowledge_keywords = ["文档", "知识库", "检索", "retrieval", "rag", "查资料", "查文档",
                             "全文搜索", "语义搜索", "pdf", "读文件", "文献"]
        security_keywords = ["安全审计", "渗透测试", "owasp", "安全扫描", "漏洞评估",
                            "vulnerability", "penetration test", "合规检查", "代码加固",
                            "安全加固", "安全评估", "安全检测", "安全漏洞", "xss", "sql注入",
                            "csrf", "认证绕过", "权限提升"]
        code_keywords = ["代码", "开发", "实现", "API", "接口", "写个", "生成", "build", "create",
                        "implement", "函数", "class", "组件", "component", "数据库表",
                        "schema", "后端", "backend", "前端", "frontend", "react", "vue",
                        "fastapi", "express", "next.js", "django", "flask"]
        workflow_keywords = ["全栈", "从零", "完整项目", "full stack", "完整系统", "端到端项目"]

        # ── 管道触发检测 (最高优先级) ──
        # 全流程触发 (13步端到端)
        if any(kw in combined_lower for kw in [
            "全流程", "一条龙", "端到端", "从需求到交付", "完整交付",
            "全链路", "13步", "13 步", "全套开发", "从头到尾",
            "从零到一", "从0到1", "start to finish", "end to end",
        ]):
            return {"agent": None, "reason": "触发13步全流程管道 (LangGraph工作流)",
                    "is_pipeline": True, "pipeline": "full_flow",
                    "task_type": "full_flow_project"}
        # 全栈项目 -> 工程管道
        if any(kw in combined_lower for kw in [
            "完整网站", "全栈应用", "完整系统", "电商系统", "管理后台",
            "saas", "web app", "从零构建", "完整项目", "出全套", "做全套",
        ]):
            return {"agent": None, "reason": "触发工程协作管道",
                    "is_pipeline": True, "pipeline": "engineering",
                    "task_type": "full_stack_project"}
        # 品牌全案 -> 设计管道
        if any(kw in combined_lower for kw in [
            "品牌全案", "全套设计", "视觉系统", "品牌重塑", "rebranding",
            "全套品牌", "品牌升级", "vi系统",
        ]):
            return {"agent": None, "reason": "触发设计协作管道",
                    "is_pipeline": True, "pipeline": "design",
                    "task_type": "brand_design_system"}
        # 战略方案 -> 战略管道
        if any(kw in combined_lower for kw in [
            "产品战略", "技术方案", "完整方案", "技术规划书", "项目蓝图",
        ]):
            return {"agent": None, "reason": "触发战略协作管道",
                    "is_pipeline": True, "pipeline": "strategy",
                    "task_type": "strategy_proposal"}

        # ── 确定性产出类型 (绕过 LLM) ──
        if has_multimodal and any(kw in combined for kw in cad_keywords):
            return {"agent": "multimodal_design_agent", "reason": "CAD 建模需求 (含图片/文件参考)",
                    "is_pipeline": False, "task_type": "cad_from_sketch"}
        if any(kw in combined for kw in web_keywords):
            return {"agent": "multimodal_design_agent", "reason": "网页生成需求",
                    "is_pipeline": False, "task_type": "web_page"}
        elif any(kw in combined for kw in diagram_keywords):
            return {"agent": "multimodal_design_agent", "reason": "图表/SVG 生成需求",
                    "is_pipeline": False, "task_type": "svg_diagram"}
        elif any(kw in combined_lower for kw in build123d_keywords):
            return {"agent": "multimodal_design_agent", "reason": "build123d 精确建模需求",
                    "is_pipeline": False, "task_type": "build123d_model"}
        elif any(kw in combined for kw in cad_keywords):
            return {"agent": "multimodal_design_agent", "reason": "CAD 建模需求",
                    "is_pipeline": False, "task_type": "cad_model"}

        # ── 12 Agent 关键词路由 (按优先级) ──
        if has_multimodal:
            return {"agent": "multimodal_design_agent", "reason": "包含多模态输入",
                    "is_pipeline": False, "task_type": "多模态分析"}
        elif any(kw in combined_lower for kw in security_keywords):
            return {"agent": "security_audit_agent", "reason": "安全审计需求",
                    "is_pipeline": False, "task_type": "security_audit"}
        elif any(kw in combined_lower for kw in brand_keywords):
            return {"agent": "brand_creative_agent", "reason": "品牌设计需求",
                    "is_pipeline": False, "task_type": "brand_identity"}
        elif any(kw in combined_lower for kw in ux_keywords):
            return {"agent": "ux_interaction_agent", "reason": "交互/UX 设计需求",
                    "is_pipeline": False, "task_type": "interaction_design"}
        elif any(kw in combined_lower for kw in devops_keywords):
            return {"agent": "devops_deploy_agent", "reason": "DevOps/部署需求",
                    "is_pipeline": False, "task_type": "devops"}
        elif any(kw in combined_lower for kw in test_keywords):
            return {"agent": "testing_qa_agent", "reason": "测试/QA 需求",
                    "is_pipeline": False, "task_type": "testing"}
        elif any(kw in combined_lower for kw in review_keywords):
            return {"agent": "code_review_agent", "reason": "代码审查需求",
                    "is_pipeline": False, "task_type": "代码审查"}
        elif any(kw in combined_lower for kw in prompt_keywords):
            return {"agent": "prompt_engineer_agent", "reason": "提示词工程需求",
                    "is_pipeline": False, "task_type": "prompt_design"}
        elif any(kw in combined_lower for kw in architect_keywords):
            return {"agent": "project_architect_agent", "reason": "架构规划需求",
                    "is_pipeline": False, "task_type": "architecture_plan"}
        elif any(kw in combined_lower for kw in crew_keywords):
            return {"agent": "crew_collaboration_agent", "reason": "多角色协作需求",
                    "is_pipeline": False, "task_type": "content_creation"}
        elif any(kw in combined_lower for kw in knowledge_keywords):
            return {"agent": "knowledge_rag_agent", "reason": "知识检索需求",
                    "is_pipeline": False, "task_type": "rag_query"}
        elif any(kw in combined for kw in workflow_keywords):
            return {"agent": "workflow_orchestrator", "reason": "多阶段工作流",
                    "is_pipeline": True, "pipeline": "engineering", "task_type": "多阶段工作流"}
        elif any(kw in combined_lower for kw in code_keywords):
            return {"agent": "secure_code_agent", "reason": "代码生成需求",
                    "is_pipeline": False, "task_type": "代码生成"}
        else:
            return {"agent": None, "reason": "直接回答", "is_pipeline": False, "task_type": "直接回答"}

    def _save_direct_output(self, task_type: str, result: Dict[str, Any], thread_id: str) -> Optional[str]:
        """将直接产出 (网页/SVG/CAD) 写入 preview/，返回预览路径。"""
        preview_dir = Path("preview")
        preview_dir.mkdir(exist_ok=True)

        content = result.get("result", result)
        if isinstance(content, dict):
            inner = content.get("result", content)
            if isinstance(inner, dict):
                content = inner

        file_map = {
            "web_page": ("html", content.get("html") if isinstance(content, dict) else None),
            "svg_diagram": ("svg", content.get("svg") if isinstance(content, dict) else None),
            "cad_model": ("py", content.get("build123d_code") or content.get("openscad_code")
                         if isinstance(content, dict) else None),
            "cad_from_sketch": ("py", content.get("build123d_code") or content.get("openscad_code")
                               if isinstance(content, dict) else None),
            "build123d_model": ("py", content.get("build123d_code") if isinstance(content, dict) else None),
        }

        if task_type not in file_map:
            return None

        ext, data = file_map[task_type]
        if not data or not isinstance(data, str) or len(data) < 50:
            return None

        filename = f"{task_type}_{thread_id[:8]}.{ext}"
        filepath = preview_dir / filename
        filepath.write_text(data, encoding="utf-8")
        logger.info("direct_output_saved", task_type=task_type, path=str(filepath))
        return str(filepath.resolve())

    def _assess_review_need(self, agent_name: str, response: A2ATaskResponse) -> bool:
        """评估是否需要人工审查"""
        high_risk = [
            "secure_code_agent", "code_review_agent",
            "security_audit_agent",  # 安全审计始终审查
            "prompt_engineer_agent", "project_architect_agent",
        ]
        if agent_name in high_risk:
            return True
        if response.status == TaskStatus.FAILED:
            return True
        if response.requires_human_review:
            return True
        return False

    def _track_agent_tokens(self, agent_name: str, response: A2ATaskResponse) -> None:
        """从 Agent 响应中提取并记录 token 消耗"""
        try:
            result = response.result or {}
            if not isinstance(result, dict):
                return
            tokens = result.get("tokens_used", 0)
            if not tokens:
                # 可能嵌套在 result.result 中
                inner = result.get("result", {})
                if isinstance(inner, dict):
                    tokens = inner.get("tokens_used", 0)
            if tokens:
                model = result.get("model_used", "")
                # 从 AGENT_LLM_MAP 反查 provider
                agent_short = agent_name.replace("_agent", "").replace("secure_code", "code") \
                    .replace("code_review", "review").replace("multimodal_design", "multimodal") \
                    .replace("testing_qa", "test").replace("devops_deploy", "devops") \
                    .replace("project_architect", "architect").replace("prompt_engineer", "prompt") \
                    .replace("crew_collaboration", "crew").replace("knowledge_rag", "knowledge") \
                    .replace("security_audit", "security").replace("ux_interaction", "ux") \
                    .replace("brand_creative", "brand")
                provider = settings._preferred_provider(agent_short)
                token_tracker.record(tokens, provider=provider, agent=agent_name,
                                     model=model, task_type="agent_execute",
                                     success=response.status != TaskStatus.FAILED)
        except Exception as e:
            logger.warning("token_tracking_error", error=str(e))

    def track_workflow(self, thread_id: str, state: Dict[str, Any]):
        self._active_workflows[thread_id] = state

    def get_workflow_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self._active_workflows.get(thread_id)


supervisor = FederationSupervisor()
