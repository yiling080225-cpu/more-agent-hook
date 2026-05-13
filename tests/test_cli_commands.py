"""测试: fedcli CLI 命令"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from click.testing import CliRunner
from fedcli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLIHelp:
    def test_main_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "new" in result.output
        assert "estimate" in result.output
        assert "status" in result.output

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "fedcli" in result.output or "1.0.0" in result.output


class TestEstimateCommand:
    def test_estimate_basic(self, runner):
        result = runner.invoke(cli, ["estimate", "test"])
        assert result.exit_code == 0
        assert "预估" in result.output

    def test_estimate_with_options(self, runner):
        result = runner.invoke(cli, ["estimate", "test", "--style", "glassmorphism"])
        assert result.exit_code == 0


class TestNewCommand:
    def test_new_requires_description(self, runner):
        result = runner.invoke(cli, ["new"])
        assert result.exit_code != 0

    def test_new_help_shows_options(self, runner):
        result = runner.invoke(cli, ["new", "--help"])
        assert result.exit_code == 0
        assert "style" in result.output


class TestStatusCommand:
    def test_status_help(self, runner):
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0


class TestSystemCommand:
    def test_system_help(self, runner):
        result = runner.invoke(cli, ["system", "--help"])
        assert result.exit_code == 0


class TestConversationState:
    def test_initial_state(self):
        from fedcli import ConversationState
        s = ConversationState()
        assert s.style == "modern"
        assert s.sandbox is True
        assert s.output_format == "both"

    def test_styles_dict(self):
        from fedcli import STYLES, THEMES
        assert len(STYLES) == 12
        assert len(THEMES) == 9
        assert "modern" in STYLES
        assert "ocean" in THEMES


class TestSlashCommands:
    def test_help_returns_true(self):
        from fedcli import _handle_slash_command, ConversationState
        from federation_sdk import FederationClient
        state = ConversationState()
        client = FederationClient()
        result = _handle_slash_command("/help", state, client)
        assert result is True

    def test_exit_returns_false(self):
        from fedcli import _handle_slash_command, ConversationState
        from federation_sdk import FederationClient
        state = ConversationState()
        client = FederationClient()
        result = _handle_slash_command("/exit", state, client)
        assert result is False

    def test_sandbox_on(self):
        from fedcli import _handle_slash_command, ConversationState
        from federation_sdk import FederationClient
        state = ConversationState()
        state.sandbox = False
        client = FederationClient()
        _handle_slash_command("/sandbox on", state, client)
        assert state.sandbox is True

    def test_search_off(self):
        from fedcli import _handle_slash_command, ConversationState
        from federation_sdk import FederationClient
        state = ConversationState()
        state.allow_search = True
        client = FederationClient()
        _handle_slash_command("/search off", state, client)
        assert state.allow_search is False


class TestSecurity:
    def test_mask_sensitive(self):
        from federation_sdk._security import mask_sensitive
        data = {"api_key": "sk-12345", "name": "test", "nested": {"token": "abc"}}
        masked = mask_sensitive(data)
        assert masked["api_key"] == "***"
        assert masked["name"] == "test"
        assert masked["nested"]["token"] == "***"

    def test_safe_path_ok(self):
        from federation_sdk._security import safe_path
        import tempfile
        d = tempfile.gettempdir()
        path = safe_path("test.txt", d)
        assert path.name == "test.txt"

    def test_safe_path_traversal(self):
        from federation_sdk._security import safe_path
        import tempfile
        d = tempfile.gettempdir()
        with pytest.raises(ValueError):
            safe_path("../../../etc/passwd", d)

    def test_validate_base_url_ok(self):
        from federation_sdk._security import validate_base_url
        assert validate_base_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"

    def test_validate_base_url_reject_credentials(self):
        from federation_sdk._security import validate_base_url
        with pytest.raises(ValueError):
            validate_base_url("http://user:pass@host:8000")
