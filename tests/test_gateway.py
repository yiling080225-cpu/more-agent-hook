"""测试: Gateway 调度层 (Registry, A2A Client, Supervisor)"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAgentRegistry:
    """Agent 注册中心测试"""

    def test_load_cards(self):
        from src.gateway.registry import agent_registry
        agents = agent_registry.list_all()
        assert len(agents) >= 3  # 至少 3 个 core agent
        names = [a.name for a in agents]
        assert "multimodal_design_agent" in names
        assert "secure_code_agent" in names
        assert "code_review_agent" in names

    def test_get_agent(self):
        from src.gateway.registry import agent_registry
        card = agent_registry.get("multimodal_design_agent")
        assert card is not None
        assert card.name == "multimodal_design_agent"
        assert "ui_design" in str(card.capabilities.get("skills", []))

    def test_find_by_skill(self):
        from src.gateway.registry import agent_registry
        matches = agent_registry.find_by_skill("code_review")
        assert len(matches) >= 1
        assert matches[0].name == "code_review_agent"

    def test_get_agent_url(self):
        from src.gateway.registry import agent_registry
        url = agent_registry.get_agent_url("secure_code_agent")
        assert url is not None
        assert "/a2a" in url

    def test_get_nonexistent(self):
        from src.gateway.registry import agent_registry
        assert agent_registry.get("nonexistent_agent") is None

    def test_get_status_summary(self):
        from src.gateway.registry import agent_registry
        summary = agent_registry.get_status_summary()
        assert summary["total_agents"] >= 3


class TestA2AClient:
    """A2A 客户端测试"""

    def test_client_creation(self):
        from src.gateway.a2a_client import A2AClient
        client = A2AClient(timeout=10, max_retries=1)
        assert client.timeout == 10
        assert client.max_retries == 1

    def test_global_instance(self):
        from src.gateway.a2a_client import a2a_client
        assert a2a_client is not None
        assert a2a_client.timeout > 0


class TestFederationSupervisor:
    """总调度器测试"""

    def test_keyword_routing_multimodal(self):
        from src.gateway.supervisor import FederationSupervisor
        from src.api.schemas import UserInput

        sv = FederationSupervisor()
        ui = UserInput(text="分析这张设计图", images=["test.png"])
        result = sv._keyword_routing(ui, has_multimodal=True)
        assert result["agent"] == "multimodal_design_agent"

    def test_keyword_routing_code(self):
        from src.gateway.supervisor import FederationSupervisor
        from src.api.schemas import UserInput

        sv = FederationSupervisor()
        ui = UserInput(text="帮我生成一个 FastAPI 接口")
        result = sv._keyword_routing(ui, has_multimodal=False)
        assert result["agent"] == "secure_code_agent"

    def test_keyword_routing_review(self):
        from src.gateway.supervisor import FederationSupervisor
        from src.api.schemas import UserInput

        sv = FederationSupervisor()
        ui = UserInput(text="帮我审查这段代码的安全性")
        result = sv._keyword_routing(ui, has_multimodal=False)
        assert result["agent"] == "code_review_agent"

    def test_keyword_routing_workflow(self):
        from src.gateway.supervisor import FederationSupervisor
        from src.api.schemas import UserInput

        sv = FederationSupervisor()
        ui = UserInput(text="我想部署一个全栈项目")
        result = sv._keyword_routing(ui, has_multimodal=False)
        assert result["agent"] == "workflow_orchestrator"

    def test_keyword_routing_direct(self):
        from src.gateway.supervisor import FederationSupervisor
        from src.api.schemas import UserInput

        sv = FederationSupervisor()
        ui = UserInput(text="今天天气怎么样")
        result = sv._keyword_routing(ui, has_multimodal=False)
        assert result["agent"] is None

    def test_assess_review_need(self):
        from src.gateway.supervisor import FederationSupervisor
        from src.api.schemas import A2ATaskResponse, TaskStatus

        sv = FederationSupervisor()
        # 高风险 Agent 总是需要审查
        resp = A2ATaskResponse(
            task_id="t1", agent_name="secure_code_agent",
            status=TaskStatus.COMPLETED, result={"code": "x"}
        )
        assert sv._assess_review_need("secure_code_agent", resp) is True

        # 失败状态需要审查
        resp_fail = A2ATaskResponse(
            task_id="t2", agent_name="multimodal_design_agent",
            status=TaskStatus.FAILED, error="test error"
        )
        assert sv._assess_review_need("multimodal_design_agent", resp_fail) is True
