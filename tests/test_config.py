"""测试配置管理 (环境变量 + cc-switch 自动读取)"""

import pytest
from src.config import Settings, settings, _load_claude_settings


class TestAutoLoadClaudeSettings:
    def test_returns_dict(self):
        result = _load_claude_settings()
        assert isinstance(result, dict)

    def test_has_expected_keys(self):
        result = _load_claude_settings()
        # Keys may be present or absent depending on cc-switch state
        valid_keys = {"anthropic_api_key", "anthropic_base_url", "claude_default_model"}
        for k in result:
            assert k in valid_keys


class TestSettings:
    def test_host_port(self):
        assert settings.host == "127.0.0.1"
        assert settings.port == 8000

    def test_agent_ports(self):
        assert settings.gateway_port == 8000
        assert settings.multimodal_agent_port == 8001
        assert settings.code_agent_port == 8002
        assert settings.review_agent_port == 8003

    def test_model_names(self):
        assert isinstance(settings.multimodal_model, str)
        assert isinstance(settings.code_model, str)
        assert isinstance(settings.review_model, str)
        assert isinstance(settings.router_model, str)

    def test_has_anthropic_property(self):
        assert isinstance(settings.has_anthropic, bool)

    def test_has_gemini_property(self):
        assert isinstance(settings.has_gemini, bool)

    def test_agent_urls(self):
        assert settings.multimodal_agent_url == "http://127.0.0.1:8001"
        assert settings.code_agent_url == "http://127.0.0.1:8002"
        assert settings.review_agent_url == "http://127.0.0.1:8003"
        assert settings.gateway_url == "http://127.0.0.1:8000"

    def test_sqlite_path(self):
        assert settings.sqlite_path == "data/checkpoints.db"

    def test_log_level(self):
        assert settings.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    def test_base_url_non_empty(self):
        assert len(settings.anthropic_base_url) > 0
        assert settings.anthropic_base_url.startswith("https://")
