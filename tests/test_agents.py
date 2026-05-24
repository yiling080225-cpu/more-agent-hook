"""测试 Agent 基类和各专项 Agent"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.api.schemas import (
    A2ATaskRequest,
    A2ATaskResponse,
    AgentCard,
    TaskStatus,
)
from src.agents.base import BaseAgent


class MockAgent(BaseAgent):
    """用于测试的 Mock Agent"""
    def __init__(self, card=None):
        if card is None:
            card = AgentCard(
                name="mock_agent",
                description="Mock agent for testing",
                version="1.0.0",
                capabilities={"skills": ["test"]},
                endpoint="http://127.0.0.1:9000/a2a",
            )
        super().__init__(card=card)

    async def execute(self, task, context):
        return {"result": "mock_executed", "task": list(task.keys())}


class FailingAgent(BaseAgent):
    """会失败的 Mock Agent"""
    def __init__(self):
        card = AgentCard(
            name="failing_agent",
            description="Always fails",
            version="1.0.0",
            capabilities={"skills": ["failure"]},
            endpoint="http://127.0.0.1:9001/a2a",
        )
        super().__init__(card=card)

    async def execute(self, task, context):
        raise RuntimeError("Simulated failure")


class LowConfidenceAgent(BaseAgent):
    """低置信度 Agent"""
    def __init__(self):
        card = AgentCard(
            name="low_confidence_agent",
            description="Low confidence",
            version="1.0.0",
            capabilities={"skills": ["uncertain"]},
            endpoint="http://127.0.0.1:9002/a2a",
        )
        super().__init__(card=card)

    async def execute(self, task, context):
        return {"result": "uncertain_result", "confidence": 0.3}


class TestBaseAgent:
    def test_get_agent_card(self):
        agent = MockAgent()
        card = agent.get_agent_card()
        assert card["name"] == "mock_agent"
        assert card["version"] == "1.0.0"

    def test_agent_name(self):
        agent = MockAgent()
        assert agent.name == "mock_agent"

    @pytest.mark.asyncio
    async def test_handle_task_success(self):
        agent = MockAgent()
        request = A2ATaskRequest(
            task_id="task-1",
            agent_name="mock_agent",
            task={"text": "hello", "type": "test"},
        )
        response = await agent.handle_a2a_task(request)
        assert response.status == TaskStatus.COMPLETED
        assert response.agent_name == "mock_agent"
        assert response.result["result"] == "mock_executed"

    @pytest.mark.asyncio
    async def test_handle_task_creates_task_id(self):
        agent = MockAgent()
        request = A2ATaskRequest(
            task_id="",
            agent_name="mock_agent",
            task={"text": "test"},
        )
        response = await agent.handle_a2a_task(request)
        assert response.task_id != ""
        assert len(response.task_id) == 36  # UUID

    @pytest.mark.asyncio
    async def test_handle_task_failure(self):
        agent = FailingAgent()
        request = A2ATaskRequest(
            task_id="task-fail",
            agent_name="failing_agent",
            task={},
        )
        response = await agent.handle_a2a_task(request)
        assert response.status == TaskStatus.FAILED
        assert "Simulated failure" in response.error

    @pytest.mark.asyncio
    async def test_handle_task_requires_review_low_confidence(self):
        agent = LowConfidenceAgent()
        request = A2ATaskRequest(
            task_id="task-review",
            agent_name="low_confidence_agent",
            task={},
        )
        response = await agent.handle_a2a_task(request)
        assert response.requires_human_review is True

    def test_needs_review_high_confidence(self):
        agent = MockAgent()
        assert agent._needs_review({"confidence": 0.9}) is False

    def test_needs_review_low_confidence(self):
        agent = MockAgent()
        assert agent._needs_review({"confidence": 0.5}) is True

    def test_needs_review_default_confidence(self):
        agent = MockAgent()
        # Default confidence of 1.0 (from dict with no "confidence" key)
        assert agent._needs_review({"other": "data"}) is False

    def test_task_status_tracking(self):
        agent = MockAgent()
        # Initially no tasks
        assert agent.get_task_status("nonexistent") is None


class TestAgentCardDefinitions:
    """验证源码中定义的 Agent Card 常量"""
    def test_multimodal_card(self):
        from src.agents.multimodal_agent import MULTIMODAL_AGENT_CARD
        assert MULTIMODAL_AGENT_CARD.name == "multimodal_design_agent"
        assert "ui_design_spec_generation" in MULTIMODAL_AGENT_CARD.capabilities["skills"]
        assert MULTIMODAL_AGENT_CARD.max_context_tokens == 1048576

    def test_code_card(self):
        from src.agents.code_agent import CODE_AGENT_CARD
        assert CODE_AGENT_CARD.name == "secure_code_agent"
        assert "fastapi_backend" in CODE_AGENT_CARD.capabilities["skills"]
        assert CODE_AGENT_CARD.max_context_tokens == 200000

    def test_review_card(self):
        from src.agents.review_agent import REVIEW_AGENT_CARD
        assert REVIEW_AGENT_CARD.name == "code_review_agent"
        assert REVIEW_AGENT_CARD.max_review_rounds == 3
        assert REVIEW_AGENT_CARD.token_budget_per_review == 50000


class TestMultimodalAgentFallback:
    """测试多模态 Agent 的降级逻辑"""
    def test_fallback_ui_spec(self):
        from src.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent()
        spec = agent._fallback_ui_spec("普通网页")
        assert "design_system" in spec
        assert len(spec["design_system"]["color_palette"]) == 4
        assert len(spec["pages"]) == 3

    def test_fallback_ui_spec_ecommerce(self):
        from src.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent()
        spec = agent._fallback_ui_spec("电商商品管理后台")
        assert "design_system" in spec
        assert len(spec["design_system"]["color_palette"]) == 5

    def test_build_prompt_ui_design(self):
        from src.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent()
        prompt = agent._build_prompt("创建一个登录页面", "ui_design")
        assert "UI/UX 设计师" in prompt
        assert "登录页面" in prompt
        assert "design_system" in prompt

    def test_build_prompt_with_style(self):
        from src.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent()
        prompt = agent._build_prompt("页面设计", "ui_design", {"style": "极简黑白 大量留白"})
        assert "极简黑白 大量留白" in prompt

    def test_build_prompt_with_theme(self):
        from src.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent()
        prompt = agent._build_prompt("页面设计", "ui_design", {"theme": "#FF5733"})
        assert "#FF5733" in prompt


class TestReviewAgentLogic:
    """测试代码审查 Agent 逻辑"""
    def test_estimate_tokens(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        tokens = agent._estimate_tokens("hello world" * 100)
        assert tokens > 0

    def test_extract_json(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        result = agent._extract_json('{"verdict": "approved", "issues": []}')
        assert result["verdict"] == "approved"

    def test_extract_json_wrapped(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        text = 'some text before\n{"verdict": "changes_requested", "issues": [{"severity": "critical"}]}\nafter'
        result = agent._extract_json(text)
        assert result["verdict"] == "changes_requested"

    @pytest.mark.asyncio
    async def test_execute_exceeds_max_rounds(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        result = await agent.execute(
            {"code": "print('hello')", "review_round": 5, "task_id": "t1"}, {}
        )
        assert result["auto_approved"] is True

    @pytest.mark.asyncio
    async def test_execute_exceeds_token_budget(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        huge_code = "x" * (agent.token_budget * 5 + 100)
        result = await agent.execute(
            {"code": huge_code, "review_round": 1, "task_id": "t2"}, {}
        )
        assert result.get("tokens_exceeded") is True

    def test_round_history(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        # Initially empty
        assert agent.get_round_history("unknown") == []


class TestCodeAgentPrompts:
    def test_frontend_prompt_exists(self):
        from src.agents.code_agent import SYSTEM_PROMPTS
        assert "frontend" in SYSTEM_PROMPTS
        assert "Next.js" in SYSTEM_PROMPTS["frontend"]

    def test_backend_prompt_exists(self):
        from src.agents.code_agent import SYSTEM_PROMPTS
        assert "backend" in SYSTEM_PROMPTS
        assert "FastAPI" in SYSTEM_PROMPTS["backend"]

    def test_svg_prompt_exists(self):
        from src.agents.code_agent import SVG_PROMPT
        assert "SVG" in SVG_PROMPT

    def test_html_prompt_exists(self):
        from src.agents.code_agent import WEB_HTML_PROMPT
        assert "HTML" in WEB_HTML_PROMPT

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要网络/API Key，跳过集成测试")
    async def test_execute_backend_integration(self):
        from src.agents.code_agent import CodeAgent
        agent = CodeAgent()
        result = await agent.execute(
            {"type": "backend", "spec": {"endpoints": ["GET /health"]}},
            {},
        )
        assert result["success"] is True
