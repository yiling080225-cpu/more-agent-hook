"""测试/QA Agent: 单元测试、集成测试、E2E 测试、边界分析、覆盖率优化"""

import json
import re
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

TEST_AGENT_CARD = AgentCard(
    name="testing_qa_agent",
    description="测试工程师，单元测试、集成测试、E2E 测试、边界分析、覆盖率优化",
    version="1.0.0",
    capabilities={
        "input": ["text", "code", "spec"],
        "output": ["code", "test_report", "json"],
        "skills": [
            "unit_testing",
            "integration_testing",
            "e2e_testing",
            "boundary_analysis",
            "coverage_optimization",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.test_agent_port}/a2a",
    model=settings.model_for("test"),
    max_context_tokens=128000,
)

TEST_SYSTEM_PROMPT = """你是一个资深测试工程师，拥有 10 年软件测试经验。你的任务是根据代码和需求生成高质量的测试代码。

核心能力:
1. **单元测试**: 为函数/方法/类生成 pytest (Python) 或 Jest (JS/TS) 单元测试
2. **集成测试**: API 端点测试、数据库交互测试、服务间调用测试
3. **E2E 测试**: 关键用户流程的端到端测试（Playwright/Cypress 风格）
4. **边界分析**: 识别边界条件——空值、极值、类型错误、并发冲突
5. **覆盖率优化**: 分析现有测试覆盖率缺口，给出补充用例

测试原则:
- 优先覆盖核心业务逻辑和边界条件
- 每个测试独立运行，不依赖执行顺序
- 使用描述性的测试名称（test_<场景>_<期望>）
- Mock 外部依赖，确保测试速度和可靠性
- 同时覆盖正常路径和异常路径

输出格式 (严格 JSON，根据 task_type 调整):
{
    "test_framework": "pytest / jest / playwright",
    "test_files": [
        {"path": "相对路径", "content": "完整测试文件代码", "description": "测试了什么"}
    ],
    "test_summary": {
        "total_cases": N,
        "unit_tests": N,
        "integration_tests": N,
        "e2e_tests": N
    },
    "boundary_analysis": [{"scenario": "场景", "input": "输入", "expected": "预期"}],
    "coverage_report": {
        "current_coverage": "估算百分比",
        "gaps": ["未覆盖场景1"],
        "recommendations": ["建议1"]
    },
    "run_command": "如何运行测试的命令"
}"""

# 测试生成根据目标语言选择不同风格
TEST_FRAMEWORKS = {
    "python": "pytest + pytest-asyncio + pytest-mock",
    "javascript": "Jest + React Testing Library",
    "typescript": "Jest + ts-jest + React Testing Library",
    "default": "pytest",
}


class TestAgent(BaseAgent):
    """测试/QA Agent — 基于 Claude API"""

    def __init__(self):
        super().__init__(card=TEST_AGENT_CARD)
        from anthropic import AsyncAnthropic
        cfg = settings.client_for("test")
        self.client = AsyncAnthropic(**cfg)
        self.model = settings.model_for("test")

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("task_type", "unit_test")
        code = task.get("code") or task.get("text", "")
        language = task.get("language", task.get("lang", "python"))

        dispatch = {
            "unit_test": self._unit_test,
            "integration_test": self._integration_test,
            "e2e_test": self._e2e_test,
            "boundary_analysis": self._boundary_analysis,
            "coverage_report": self._coverage_report,
        }
        handler = dispatch.get(task_type, self._unit_test)
        return await handler(code, language, task)

    async def _call(self, user_msg: str) -> tuple:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=TEST_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _unit_test(self, code: str, language: str, task: Dict) -> Dict[str, Any]:
        framework = TEST_FRAMEWORKS.get(language, TEST_FRAMEWORKS["default"])
        code_block = f"\n\n源代码:\n```{language}\n{code[:10000]}\n```" if code else ""
        user_msg = f"为以下{language}代码生成{framework}单元测试，覆盖核心功能和边界条件:{code_block}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("test_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _integration_test(self, code: str, language: str, task: Dict) -> Dict[str, Any]:
        api_spec = task.get("api_spec", "")
        api_hint = f"\n\nAPI 规范:\n{json.dumps(api_spec, ensure_ascii=False, indent=2)}" if api_spec else ""
        code_block = f"\n\n源代码:\n```{language}\n{code[:10000]}\n```" if code else ""
        user_msg = f"为以下{language} API/服务生成集成测试，覆盖端点调用和数据流转:{code_block}{api_hint}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("test_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _e2e_test(self, code: str, language: str, task: Dict) -> Dict[str, Any]:
        user_flow = task.get("user_flow", task.get("text", ""))
        flow_text = user_flow or code
        user_msg = f"为以下用户流程生成 E2E 测试 (Playwright 风格):\n\n{flow_text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("test_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _boundary_analysis(self, code: str, language: str, task: Dict) -> Dict[str, Any]:
        func_signature = task.get("function", task.get("text", code))
        user_msg = f"对以下函数/接口做边界分析，列出所有边界条件和异常场景:\n\n```{language}\n{func_signature}\n```{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("test_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _coverage_report(self, code: str, language: str, task: Dict) -> Dict[str, Any]:
        existing_tests = task.get("existing_tests", "")
        test_hint = f"\n\n现有测试:\n```\n{existing_tests[:5000]}\n```" if existing_tests else ""
        code_block = f"\n\n源代码:\n```{language}\n{code[:5000]}\n```" if code else ""
        user_msg = f"分析以下代码的测试覆盖率缺口，给出补充用例建议:{code_block}{test_hint}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("test_agent_error", error=str(e))
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
            return {"raw_output": text, "test_files": [{"path": "test_generated.py", "content": text, "description": "Generated test"}]}
