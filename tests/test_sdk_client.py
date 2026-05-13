"""测试: FederationClient (本地可测部分)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from federation_sdk import FederationClient, ConnectionError
from federation_sdk.exceptions import ValidationError


class TestFederationClientInit:
    def test_default_url(self):
        c = FederationClient()
        assert "8000" in c._http._base_url

    def test_custom_url(self):
        c = FederationClient(base_url="http://127.0.0.1:9000")
        assert "9000" in c._http._base_url

    def test_url_without_protocol(self):
        c = FederationClient(base_url="127.0.0.1:8000")
        assert c._http._base_url == "http://127.0.0.1:8000"

    def test_url_with_credentials_rejected(self):
        with pytest.raises(ValidationError):
            FederationClient(base_url="http://user:pass@host:8000")


class TestEstimate:
    def test_simple_text(self):
        c = FederationClient()
        est = c.estimate("做一个电商网站")
        assert est.total_tokens > 0
        assert est.estimated_cost > 0
        assert est.cost_range[0] <= est.cost_range[1]

    def test_with_style(self):
        c = FederationClient()
        est = c.estimate("做一个电商网站", style="glassmorphism", output_format="html")
        assert est.confidence == "medium"

    def test_short_text(self):
        c = FederationClient()
        est = c.estimate("hi")
        assert est.output_tokens == 3000

    def test_long_text(self):
        c = FederationClient()
        est = c.estimate("做" * 300)
        assert est.output_tokens == 15000


class TestProperties:
    def test_resource_properties(self):
        c = FederationClient()
        assert c.supervisor is not None
        assert c.workflow is not None
        assert c.agents is not None
        assert c.system is not None

    def test_resource_type_correct(self):
        from federation_sdk.resources.supervisor import SupervisorResource
        from federation_sdk.resources.workflow import WorkflowResource
        from federation_sdk.resources.agents import AgentsResource
        from federation_sdk.resources.system import SystemResource
        c = FederationClient()
        assert isinstance(c.supervisor, SupervisorResource)
        assert isinstance(c.workflow, WorkflowResource)
        assert isinstance(c.agents, AgentsResource)
        assert isinstance(c.system, SystemResource)
