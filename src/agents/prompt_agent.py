"""提示词工程师 Agent — GPT(复杂推理) + DeepSeek(轻量测试) 按任务拆分"""

import json
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

PROMPT_AGENT_CARD = AgentCard(
    name="prompt_engineer_agent",
    description="提示词工程专家：设计、调试、优化 LLM 提示词，A/B 测试，结构化输出设计",
    version="1.0.0",
    capabilities={
        "input": ["text", "requirements"],
        "output": ["prompt_template", "test_cases", "evaluation", "json"],
        "skills": [
            "prompt_design", "prompt_debugging", "prompt_optimization",
            "few_shot_examples", "chain_of_thought", "structured_output", "prompt_testing",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.prompt_agent_port}/a2a",
    model=settings.model_for("prompt"),
    max_context_tokens=128000,
)

PROMPT_SYSTEM_PROMPT = """你是一个世界级提示词工程师。你的任务是为 LLM 设计和优化提示词。

核心能力:
1. **提示词设计**: 根据需求设计精准的 system prompt 和 user prompt
2. **提示词调试**: 分析提示词失败原因，找出歧义、遗漏、矛盾点
3. **提示词优化**: 应用 CO-STAR、Few-shot、Chain-of-Thought、结构化输出等技术
4. **测试用例**: 设计边界 case 覆盖各种输入场景
5. **版本迭代**: 给出 A/B 版本对比和优化建议

设计原则:
- 清晰 > 花哨：指令明确，不模棱两可
- 约束准确：用"必须/禁止"而非"尽量/最好不要"
- 示例先行：复杂场景给 2-3 个 few-shot
- 结构化输出：复杂任务要求 JSON/Markdown 格式输出
- 角色锚定：明确告诉模型"你是谁"和"你要做什么"

输出格式 (JSON):
{
    "prompt_version": "v1",
    "system_prompt": "系统提示词全文",
    "user_prompt_template": "用户提示词模板，用 {{变量}} 标记占位",
    "few_shot_examples": [{"input": "...", "output": "..."}],
    "test_cases": [{"input": "...", "expected_behavior": "..."}],
    "design_rationale": "设计理念说明",
    "caveats": ["注意事项1", "注意事项2"],
    "suggested_model": "推荐使用的模型"
}"""

# 任务分配: design/debug/optimize -> Opus > GPT, test -> DeepSeek (性价比)
TASK_MODEL_MAP = {
    "prompt_design": "opus",
    "prompt_debug": "opus",
    "prompt_optimize": "opus",
    "prompt_test": "deepseek",
}


class PromptAgent(BaseAgent):
    """提示词工程师 Agent — Opus + GPT + DeepSeek 三引擎"""

    def __init__(self):
        super().__init__(card=PROMPT_AGENT_CARD)
        from anthropic import AsyncAnthropic

        self.opus_client = None
        self.opus_model = None
        if settings.opus_key:
            self.opus_client = AsyncAnthropic(api_key=settings.opus_key, base_url=settings.opus_url)
            self.opus_model = settings.opus_model

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
        use = TASK_MODEL_MAP.get(task_type, "opus")
        if use == "opus" and self.opus_client:
            return self.opus_client, self.opus_model, "opus"
        if use == "opus" and self.gpt_client:
            return self.gpt_client, self.gpt_model, "gpt"
        if use == "gpt" and self.gpt_client:
            return self.gpt_client, self.gpt_model, "gpt"
        if self.ds_client:
            return self.ds_client, self.ds_model, "deepseek"
        if self.gpt_client:
            return self.gpt_client, self.gpt_model, "gpt"
        return None, None, "none"

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_text = task.get("text") or task.get("prompt", "")
        task_type = task.get("task_type", "prompt_design")
        dispatch = {
            "prompt_design": self._design_prompt,
            "prompt_debug": self._debug_prompt,
            "prompt_optimize": self._optimize_prompt,
            "prompt_test": self._test_prompt,
        }
        handler = dispatch.get(task_type, self._design_prompt)
        return await handler(user_text, task, task_type)

    async def _call(self, client, model: str, user_msg: str):
        resp = await client.messages.create(
            model=model, max_tokens=4096,
            system=PROMPT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _design_prompt(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        user_msg = f"为以下需求设计一个 LLM 提示词:\n\n{text}"
        if task.get("context"):
            user_msg += f"\n\n附加上下文:\n{json.dumps(task['context'], ensure_ascii=False, indent=2)}"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("prompt_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _debug_prompt(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        original = task.get("original_prompt", "")
        failure = task.get("failure_description", text)
        user_msg = f"以下提示词出了问题:\n\n```\n{original}\n```\n\n失败现象:\n{failure}\n\n请诊断问题并给出修复版。"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("prompt_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _optimize_prompt(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        original = task.get("original_prompt", text)
        target = task.get("optimization_target", "提升准确率和鲁棒性")
        user_msg = f"优化以下提示词:\n\n```\n{original}\n```\n\n优化目标: {target}\n\n给出优化版和对比分析。"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("prompt_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _test_prompt(self, text: str, task: Dict, task_type: str) -> Dict[str, Any]:
        client, model, provider = self._pick(task_type)
        if not client:
            return {"success": False, "error": "No available LLM client"}
        prompt = task.get("prompt_to_test", text)
        test_inputs = task.get("test_inputs", [])
        inputs_str = "\n".join(f"- {t}" for t in test_inputs) if test_inputs else text
        user_msg = f"为以下提示词设计测试用例:\n\n```\n{prompt}\n```\n\n测试场景:\n{inputs_str}"
        try:
            content, tokens = await self._call(client, model, user_msg)
            result = self._parse_json(content)
            result.update(model_used=model, provider=provider, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("prompt_agent_error", error=str(e))
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
        return {"raw_output": text, "prompt_version": "v1"}
