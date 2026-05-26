"""测试配置管理"""

import pytest
from src.config import Settings, settings


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

    def test_has_any_api_key_property(self):
        assert isinstance(settings.has_any_api_key, bool)

    def test_agent_urls(self):
        assert settings.multimodal_agent_url == "http://127.0.0.1:8001"
        assert settings.code_agent_url == "http://127.0.0.1:8002"
        assert settings.review_agent_url == "http://127.0.0.1:8003"
        assert settings.gateway_url == "http://127.0.0.1:8000"

    def test_sqlite_path(self):
        assert settings.sqlite_path == "data/checkpoints.db"

    def test_log_level(self):
        assert settings.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    def test_deepseek_url_default(self):
        assert settings.deepseek_url == "https://api.deepseek.com/anthropic"

    def test_client_for_returns_dict(self):
        cfg = settings.client_for("code")
        assert isinstance(cfg, dict)
        assert "api_key" in cfg
        assert "base_url" in cfg

    def test_settings_is_singleton(self):
        s2 = Settings()
        assert settings.host == s2.host
        assert settings.port == s2.port
