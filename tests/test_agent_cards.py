"""测试 agent_cards/ 目录中的 Agent Card JSON 文件"""

import json
from pathlib import Path

import pytest
from src.api.schemas import AgentCard

CARDS_DIR = Path(__file__).parent.parent / "agent_cards"


class TestAgentCardsDirectory:
    def test_directory_exists(self):
        assert CARDS_DIR.exists(), "agent_cards/ 目录应存在"

    def test_has_three_cards(self):
        cards = list(CARDS_DIR.glob("*.json"))
        assert len(cards) >= 3, f"期望至少 3 个 card 文件，实际 {len(cards)} 个"


class TestMultimodalAgentCard:
    @pytest.fixture(autouse=True)
    def load(self):
        path = CARDS_DIR / "multimodal_design_agent.json"
        assert path.exists()
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.card = AgentCard(**self.data)

    def test_name(self):
        assert self.card.name == "multimodal_design_agent"

    def test_version(self):
        assert self.card.version == "1.0.0"

    def test_skills(self):
        skills = self.card.capabilities["skills"]
        assert "ui_design_spec_generation" in skills
        assert "visual_element_extraction" in skills
        assert "layout_analysis" in skills

    def test_endpoint(self):
        assert "8001" in self.card.endpoint
        assert self.card.endpoint.endswith("/a2a")

    def test_model(self):
        assert self.card.model is not None
        assert len(self.card.model) > 0


class TestCodeAgentCard:
    @pytest.fixture(autouse=True)
    def load(self):
        path = CARDS_DIR / "secure_code_agent.json"
        assert path.exists()
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.card = AgentCard(**self.data)

    def test_name(self):
        assert self.card.name == "secure_code_agent"

    def test_skills(self):
        skills = self.card.capabilities["skills"]
        assert "fastapi_backend" in skills
        assert "security_best_practices" in skills

    def test_endpoint(self):
        assert "8002" in self.card.endpoint

    def test_max_context(self):
        assert self.card.max_context_tokens == 200000


class TestReviewAgentCard:
    @pytest.fixture(autouse=True)
    def load(self):
        path = CARDS_DIR / "code_review_agent.json"
        assert path.exists()
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.card = AgentCard(**self.data)

    def test_name(self):
        assert self.card.name == "code_review_agent"

    def test_skills(self):
        skills = self.card.capabilities["skills"]
        assert "code_review" in skills
        assert "security_vulnerability_detection" in skills

    def test_endpoint(self):
        assert "8003" in self.card.endpoint

    def test_review_config(self):
        assert self.card.max_review_rounds == 3
        assert self.card.token_budget_per_review == 50000
