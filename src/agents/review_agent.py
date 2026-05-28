"""审查 Agent: 对话式代码审查，最多 3 轮，含 token 预算控制"""

import json
import structlog
from typing import Any, Dict, List

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

REVIEW_AGENT_CARD = AgentCard(
    name="code_review_agent",
    description="对话式代码审查，多轮辩论，安全漏洞检测",
    version="1.0.0",
    capabilities={
        "input": ["text", "code", "diff"],
        "output": ["review_comment", "approval_status", "json"],
        "skills": [
            "code_review",
            "security_vulnerability_detection",
            "performance_analysis",
            "multi_round_debate",
            "best_practice_enforcement",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.review_agent_port}/a2a",
    model=settings.model_for("review"),
    max_context_tokens=128000,
    max_review_rounds=3,
    token_budget_per_review=50000,
)

REVIEW_SYSTEM_PROMPT = """你是一个资深代码审查专家。审查提交的代码，关注:

1. **安全性**: SQL 注入、XSS、CSRF、认证授权、密钥泄露、输入验证
2. **正确性**: 逻辑错误、边界条件、空值处理、并发安全
3. **性能**: N+1 查询、不必要循环、内存泄漏、缓存缺失
4. **最佳实践**: 类型安全、错误处理、代码可读性、SOLID 原则

审查规则:
- 每个问题标注严重级别: critical / warning / info
- critical: 安全漏洞或会导致生产故障
- warning: 可能导致 bug 或性能问题
- info: 代码风格或最佳实践建议

输出格式 (严格 JSON):
{
    "verdict": "approved" | "changes_requested",
    "issues": [
        {
            "severity": "critical" | "warning" | "info",
            "file": "文件路径",
            "line": 行号或 null,
            "description": "问题描述",
            "suggestion": "修改建议"
        }
    ],
    "summary": "审查总结",
    "score": 0-10
}

- 如果没有 critical 或 warning，verdict 必须为 "approved"
- 每轮审查 token 预算有限，优先报告严重问题"""


class ReviewAgent(BaseAgent):
    """代码审查 Agent — 对话式多轮审查"""

    def __init__(self):
        super().__init__(card=REVIEW_AGENT_CARD)
        from anthropic import AsyncAnthropic
        cfg = settings.client_for("review")
        self.client = AsyncAnthropic(**cfg)
        self.model = settings.model_for("review")
        self.max_rounds = 3
        self.token_budget = 50000
        self._round_history: Dict[str, List[Dict[str, Any]]] = {}

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行代码审查

        task 期望包含:
        - code: 要审查的代码 (str 或 {"files": [...]})
        - review_round: 当前审查轮次 (从 1 开始)
        - previous_comments: 上一轮的审查意见 (用于修复验证)
        - task_id: 用于追踪对话历史
        """
        code = task.get("code") or task.get("text", "")
        review_round = task.get("review_round", 1)
        previous_comments = task.get("previous_comments", [])
        task_id = task.get("task_id", "unknown")

        # 检查是否超过最大轮次
        if review_round > self.max_rounds:
            return {
                "success": True,
                "verdict": "approved",
                "issues": [],
                "summary": f"达到最大审查轮次 ({self.max_rounds})，自动通过",
                "score": 7,
                "auto_approved": True,
                "rounds_used": review_round,
            }

        # 检查 token 预算
        if self._estimate_tokens(code) > self.token_budget:
            return {
                "success": True,
                "verdict": "approved",
                "issues": [{
                    "severity": "warning",
                    "file": "N/A",
                    "line": None,
                    "description": f"代码超出 token 预算 ({self.token_budget})，跳过详细审查",
                    "suggestion": "请人工审查或拆分提交",
                }],
                "summary": "Token 预算超限，自动通过并添加警告",
                "score": 5,
                "tokens_exceeded": True,
            }

        return await self._review_code(code, review_round, previous_comments, task_id,
                                        files_hint=self._format_files_hint(task))

    async def _review_code(
        self,
        code: Any,
        round_num: int,
        previous_comments: List[Dict[str, Any]],
        task_id: str,
        files_hint: str = "",
    ) -> Dict[str, Any]:
        """调用 Claude 进行代码审查"""
        # 构建代码文本
        if isinstance(code, dict):
            code_text = json.dumps(code, ensure_ascii=False, indent=2)
        elif isinstance(code, list):
            parts = []
            for f in code:
                if isinstance(f, dict) and "path" in f:
                    parts.append(f"// {f['path']}\n{f.get('content', '')}")
                else:
                    parts.append(str(f))
            code_text = "\n\n".join(parts)
        else:
            code_text = str(code)

        # 构建审查消息
        user_message = f"审查以下代码 (第 {round_num} 轮):\n\n```\n{code_text[:30000]}\n```"

        if previous_comments and round_num > 1:
            prev_json = json.dumps(previous_comments, ensure_ascii=False, indent=2)
            user_message += f"\n\n上一轮审查发现了以下问题，请验证是否已修复:\n{prev_json}"

        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=REVIEW_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            content = extract_text(resp.content)
            try:
                review_result = json.loads(content)
            except json.JSONDecodeError:
                # 尝试提取 JSON
                review_result = self._extract_json(content)

            # 追踪对话历史
            if task_id not in self._round_history:
                self._round_history[task_id] = []
            self._round_history[task_id].append({
                "round": round_num,
                "review": review_result,
                "tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            })

            return {
                "success": True,
                **review_result,
                "round": round_num,
                "model_used": self.model,
                "tokens_used": resp.usage.input_tokens + resp.usage.output_tokens,
                "budget_remaining": self.token_budget - (resp.usage.input_tokens + resp.usage.output_tokens),
            }
        except Exception as e:
            logger.error("review_agent_error", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "verdict": "error",
                "issues": [],
            }

    def _estimate_tokens(self, code: Any) -> int:
        """估算代码 token 数 (粗略: 4 chars ≈ 1 token)"""
        code_str = json.dumps(code, ensure_ascii=False) if isinstance(code, (dict, list)) else str(code)
        return len(code_str) // 3

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON 块"""
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {
            "verdict": "changes_requested",
            "issues": [{"severity": "info", "file": "N/A", "line": None, "description": text[:500], "suggestion": "人工审查"}],
            "summary": "无法解析审查结果 JSON",
            "score": 5,
        }

    def get_round_history(self, task_id: str) -> List[Dict[str, Any]]:
        """获取审查历史"""
        return self._round_history.get(task_id, [])
