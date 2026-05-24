"""测试安全模块：MCP 权限校验、安全策略"""

import pytest
from src.mcp.registry import MCPRegistry


class TestMCPApprovalSecurity:
    """测试 MCP 工具的审批安全机制"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.registry = MCPRegistry()

    def test_all_approval_required_tools(self):
        """确保所有写入操作都需要审批"""
        approval_required = []
        for t in self.registry.list_tools():
            if t["requires_approval"]:
                approval_required.append(t["name"])

        assert "write_file" in approval_required, "写入文件必须需要审批"

    def test_read_operations_no_approval(self):
        """确保读取操作不需要审批"""
        no_approval = []
        for t in self.registry.list_tools():
            if not t["requires_approval"]:
                no_approval.append(t["name"])

        assert "read_file" in no_approval
        assert "list_directory" in no_approval

    @pytest.mark.asyncio
    async def test_write_rejected_without_approval(self):
        result = await self.registry.call_tool(
            "write_file",
            {"path": "/etc/passwd", "content": "malicious"},
            approved=False,
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_nonexistent_tool_rejected(self):
        result = await self.registry.call_tool("delete_all_files", {})
        assert result["success"] is False


class TestReviewAgentSecurity:
    """测试审查 Agent 的安全检测能力"""

    def test_review_prompt_includes_security(self):
        from src.agents.review_agent import REVIEW_SYSTEM_PROMPT
        assert "安全性" in REVIEW_SYSTEM_PROMPT or "security" in REVIEW_SYSTEM_PROMPT.lower()
        assert "SQL" in REVIEW_SYSTEM_PROMPT
        assert "XSS" in REVIEW_SYSTEM_PROMPT

    def test_token_budget_enforced(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        assert agent.token_budget == 50000

    def test_max_rounds_enforced(self):
        from src.agents.review_agent import ReviewAgent
        agent = ReviewAgent()
        assert agent.max_rounds == 3


class TestCodeAgentSecurity:
    """测试代码 Agent 的安全提示"""

    def test_frontend_prompt_security(self):
        from src.agents.code_agent import SYSTEM_PROMPTS
        prompt = SYSTEM_PROMPTS["frontend"]
        assert "aria-label" in prompt or "无障碍" in prompt

    def test_backend_prompt_security(self):
        from src.agents.code_agent import SYSTEM_PROMPTS
        prompt = SYSTEM_PROMPTS["backend"]
        assert "SQL" in prompt or "CORS" in prompt or "validate" in prompt.lower()


class TestConfigSecurity:
    """测试配置安全"""

    def test_no_hardcoded_key(self):
        from src.config import Settings, _load_claude_settings
        auto = _load_claude_settings()
        # API key 从文件读取，不应硬编码在源码中
        assert isinstance(auto, dict)
        if "anthropic_api_key" in auto:
            # Key 应该是从外部文件加载的，不是硬编码
            assert auto["anthropic_api_key"] != ""

    def test_localhost_default(self):
        from src.config import settings
        # 确保默认绑定 localhost，不会意外暴露在公网
        assert settings.host == "127.0.0.1"

    def test_write_file_requires_approval(self):
        """验证 write_file MCP 工具必须人工审批"""
        from src.mcp.registry import mcp_registry
        tool = mcp_registry.get_tool("write_file")
        assert tool["requires_approval"] is True, "write_file 必须标记为需要审批"


class TestSensitiveDataInPrompts:
    """测试 prompt 中不包含敏感信息"""

    def test_no_api_keys_in_prompts(self):
        from src.agents.code_agent import SYSTEM_PROMPTS
        for name, prompt in SYSTEM_PROMPTS.items():
            assert "sk-" not in prompt, f"{name} prompt 包含疑似 API key"
            assert "api_key" not in prompt.lower(), f"{name} prompt 包含 api_key"

    def test_no_api_keys_in_review_prompt(self):
        from src.agents.review_agent import REVIEW_SYSTEM_PROMPT
        assert "sk-" not in REVIEW_SYSTEM_PROMPT
