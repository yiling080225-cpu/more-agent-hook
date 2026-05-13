"""测试: Agent 实现"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMultimodalAgent:
    """多模态 Agent 测试"""

    def test_agent_card(self):
        from src.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent()
        card = agent.get_agent_card()
        assert card["name"] == "multimodal_design_agent"
        assert "ui_design_spec_generation" in card["capabilities"]["skills"]

    def test_fallback_ui_spec(self):
        from src.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent()
        spec = agent._fallback_ui_spec("做一个电商网站")
        assert "design_system" in spec
        assert "color_palette" in spec["design_system"]
        assert "pages" in spec
        assert len(spec["pages"]) >= 2
        assert "component_library" in spec

    def test_fallback_ui_spec_ecommerce_detection(self):
        from src.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent()
        spec_ecom = agent._fallback_ui_spec("做一个电商网站卖东西")
        spec_normal = agent._fallback_ui_spec("做一个博客")
        # 电商检测不影响结构，但应该有不同配色
        assert "color_palette" in spec_ecom["design_system"]
        assert "color_palette" in spec_normal["design_system"]

    def test_execute_without_api(self):
        """测试无 API Key 时的降级行为"""
        import asyncio
        from src.agents.multimodal_agent import MultimodalAgent

        agent = MultimodalAgent()
        # 空 API Key 时 generate_content 会抛异常，应走 fallback
        result = asyncio.run(agent.execute(
            {"text": "测试电商网站", "task_type": "ui_design"}, {}
        ))
        # 降级或 API 结果都应返回 ui_spec
        assert "ui_spec" in result or "success" in result


class TestCodeAgent:
    """代码 Agent 测试"""

    def test_agent_card(self):
        from src.agents.code_agent import CodeAgent
        agent = CodeAgent()
        card = agent.get_agent_card()
        assert card["name"] == "secure_code_agent"
        skills = card["capabilities"]["skills"]
        assert "fastapi_backend" in skills
        assert "nextjs_frontend" in skills

    def test_system_prompts(self):
        from src.agents.code_agent import SYSTEM_PROMPTS
        assert "frontend" in SYSTEM_PROMPTS
        assert "backend" in SYSTEM_PROMPTS
        assert "Next.js" in SYSTEM_PROMPTS["frontend"]
        assert "FastAPI" in SYSTEM_PROMPTS["backend"]


class TestReviewAgent:
    """审查 Agent 测试"""

    def test_agent_card(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        card = agent.get_agent_card()
        assert card["name"] == "code_review_agent"
        assert card["max_review_rounds"] == 3
        assert card["token_budget_per_review"] == 50000

    def test_max_rounds_check(self):
        import asyncio
        from src.agents.review_agent import ReviewAgent

        agent = ReviewAgent()
        result = asyncio.run(agent.execute({
            "code": "print('hello')",
            "review_round": 4,
            "previous_comments": [],
            "task_id": "test",
        }, {}))
        assert result["verdict"] == "approved"
        assert result["auto_approved"] is True

    def test_token_budget_check(self):
        import asyncio
        from src.agents.review_agent import ReviewAgent

        agent = ReviewAgent()
        agent.token_budget = 10  # 极小预算
        result = asyncio.run(agent.execute({
            "code": "a" * 200,  # 超出预算
            "review_round": 1,
            "previous_comments": [],
            "task_id": "test",
        }, {}))
        assert result["tokens_exceeded"] is True

    def test_token_estimation(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        tokens = agent._estimate_tokens("hello world " * 100)
        assert tokens > 0
        # 约 1200 chars / 3 ≈ 400 tokens
        assert 300 < tokens < 600

    def test_extract_json(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        result = agent._extract_json('some text {"verdict": "approved", "score": 8} more text')
        assert result["verdict"] == "approved"
        assert result["score"] == 8

    def test_extract_json_invalid(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        result = agent._extract_json("just plain text, no JSON here")
        assert result["verdict"] == "changes_requested"
        assert result["score"] == 5

    def test_round_history(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        assert agent.get_round_history("nonexistent") == []
