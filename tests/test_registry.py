"""测试 Agent 注册中心"""

import pytest
from src.api.schemas import AgentCard
from src.gateway.registry import AgentRegistry


@pytest.fixture
def registry():
    """使用 agent_cards/ 加载的注册中心"""
    return AgentRegistry()


@pytest.fixture
def test_card():
    return AgentCard(
        name="test_agent",
        description="测试 Agent",
        version="1.0.0",
        capabilities={"skills": ["skill_a", "skill_b"]},
        endpoint="http://127.0.0.1:9001/a2a",
    )


class TestAgentRegistryLoad:
    def test_loads_all_cards(self, registry):
        agents = registry.list_all()
        assert len(agents) == 3

    def test_get_by_name(self, registry):
        card = registry.get("multimodal_design_agent")
        assert card is not None
        assert card.name == "multimodal_design_agent"

    def test_get_nonexistent(self, registry):
        assert registry.get("nonexistent_agent") is None

    def test_get_agent_url(self, registry):
        url = registry.get_agent_url("secure_code_agent")
        assert url == "http://127.0.0.1:8002/a2a"


class TestAgentRegistryOperations:
    def test_register_new(self, registry, test_card):
        registry.register(test_card)
        assert registry.get("test_agent") is not None
        assert len(registry.list_all()) == 4

    def test_unregister(self, registry, test_card):
        registry.register(test_card)
        assert registry.get("test_agent") is not None
        registry.unregister("test_agent")
        assert registry.get("test_agent") is None

    def test_find_by_skill(self, registry):
        matches = registry.find_by_skill("code_review")
        names = [m.name for m in matches]
        assert "code_review_agent" in names

    def test_find_by_skill_no_match(self, registry):
        matches = registry.find_by_skill("nonexistent_skill")
        assert matches == []

    def test_list_available_initially_empty(self, registry):
        available = registry.list_available()
        assert available == []

    def test_list_all_returns_cards(self, registry):
        cards = registry.list_all()
        names = {c.name for c in cards}
        assert names == {
            "multimodal_design_agent",
            "secure_code_agent",
            "code_review_agent",
        }

    def test_status_summary(self, registry):
        summary = registry.get_status_summary()
        assert summary["total_agents"] == 3
        assert summary["available_agents"] == 0
        assert "multimodal_design_agent" in summary["agents"]
