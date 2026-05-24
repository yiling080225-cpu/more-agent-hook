"""测试 MCP 工具注册中心"""

import pytest
from src.mcp.registry import MCPRegistry, mcp_registry


class TestMCPRegistry:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.registry = MCPRegistry()

    def test_builtin_tools_registered(self):
        tools = self.registry.list_tools()
        tool_names = {t["name"] for t in tools}
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_directory" in tool_names
        assert "web_search" in tool_names
        assert "validate_python" in tool_names
        assert "format_code" in tool_names

    def test_tool_count(self):
        tools = self.registry.list_tools()
        assert len(tools) == 6

    def test_get_tool(self):
        tool = self.registry.get_tool("read_file")
        assert tool is not None
        assert tool["name"] == "read_file"
        assert tool["requires_approval"] is False

    def test_get_nonexistent_tool(self):
        assert self.registry.get_tool("nonexistent") is None

    def test_write_file_requires_approval(self):
        tool = self.registry.get_tool("write_file")
        assert tool["requires_approval"] is True

    def test_list_tool_structure(self):
        tools = self.registry.list_tools()
        for t in tools:
            assert "name" in t
            assert "description" in t
            assert "parameters" in t
            assert "requires_approval" in t

    def test_get_tool_schema_for_llm(self):
        schemas = self.registry.get_tool_schema_for_llm()
        assert len(schemas) == 6
        for s in schemas:
            assert "name" in s
            assert "description" in s
            assert "parameters" in s
            assert "type" in s["parameters"]

    @pytest.mark.asyncio
    async def test_call_read_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        result = await self.registry.call_tool("read_file", {"path": str(f)})
        assert result["success"] is True
        assert result["result"]["content"] == "hello world"

    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self):
        result = await self.registry.call_tool("nonexistent", {})
        assert result["success"] is False
        assert "未知工具" in result["error"]

    @pytest.mark.asyncio
    async def test_call_write_file_without_approval(self, tmp_path):
        f = tmp_path / "output.txt"
        result = await self.registry.call_tool(
            "write_file", {"path": str(f), "content": "test"},
        )
        assert result["success"] is False
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_call_write_file_with_approval(self, tmp_path):
        f = tmp_path / "output.txt"
        result = await self.registry.call_tool(
            "write_file", {"path": str(f), "content": "approved content"},
            approved=True,
        )
        assert result["success"] is True
        assert f.read_text() == "approved content"

    @pytest.mark.asyncio
    async def test_call_list_directory(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        result = await self.registry.call_tool("list_directory", {"path": str(tmp_path)})
        assert result["success"] is True
        names = [e["name"] for e in result["result"]["entries"]]
        assert "a.txt" in names
        assert "b.txt" in names

    @pytest.mark.asyncio
    async def test_call_validate_python_valid(self):
        result = await self.registry.call_tool(
            "validate_python", {"code": "print('hello')"}
        )
        assert result["success"] is True
        assert result["result"]["valid"] is True

    @pytest.mark.asyncio
    async def test_call_validate_python_invalid(self):
        result = await self.registry.call_tool(
            "validate_python", {"code": "print('hello'"}
        )
        assert result["success"] is True
        assert result["result"]["valid"] is False


class TestGlobalRegistrySingleton:
    def test_mcp_registry_is_importable(self):
        assert mcp_registry is not None

    def test_tools_available(self):
        tools = mcp_registry.list_tools()
        assert len(tools) > 0
