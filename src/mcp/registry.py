"""MCP 工具注册中心: 工具发现、调用、权限校验"""

import structlog
from typing import Any, Dict, List, Optional

from .tools import file_tools, search_tools, code_tools

logger = structlog.get_logger()


class MCPRegistry:
    """MCP 工具注册与调用中心"""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_builtins()

    def _register_builtins(self):
        """注册内置 MCP 工具"""
        # 文件工具
        self.register(
            name="read_file",
            description="读取文件内容",
            handler=file_tools.read_file,
            parameters={"path": "str", "encoding": "str?"},
            requires_approval=False,
        )
        self.register(
            name="write_file",
            description="写入文件",
            handler=file_tools.write_file,
            parameters={"path": "str", "content": "str", "encoding": "str?"},
            requires_approval=True,
        )
        self.register(
            name="list_directory",
            description="列出目录内容",
            handler=file_tools.list_directory,
            parameters={"path": "str"},
            requires_approval=False,
        )

        # 搜索工具
        self.register(
            name="web_search",
            description="Web 搜索",
            handler=search_tools.web_search,
            parameters={"query": "str", "num_results": "int?"},
            requires_approval=False,
        )

        # 代码工具
        self.register(
            name="validate_python",
            description="验证 Python 代码语法",
            handler=code_tools.validate_python,
            parameters={"code": "str"},
            requires_approval=False,
        )
        self.register(
            name="format_code",
            description="格式化代码",
            handler=code_tools.format_code,
            parameters={"code": "str", "language": "str"},
            requires_approval=False,
        )

        logger.info("mcp_tools_registered", count=len(self._tools))

    def register(
        self,
        name: str,
        description: str,
        handler,
        parameters: Dict[str, str],
        requires_approval: bool = False,
    ):
        self._tools[name] = {
            "name": name,
            "description": description,
            "handler": handler,
            "parameters": parameters,
            "requires_approval": requires_approval,
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有已注册工具"""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
                "requires_approval": t["requires_approval"],
            }
            for t in self._tools.values()
        ]

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个工具定义"""
        return self._tools.get(name)

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        approved: bool = False,
    ) -> Dict[str, Any]:
        """
        调用 MCP 工具

        Args:
            tool_name: 工具名称
            arguments: 调用参数
            approved: 是否已通过人工审批 (对 requires_approval=True 的工具)

        Returns:
            {"success": bool, "result": Any, "error": str?}
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"未知工具: {tool_name}"}

        if tool["requires_approval"] and not approved:
            return {
                "success": False,
                "error": f"工具 '{tool_name}' 需要人工审批",
                "requires_approval": True,
            }

        try:
            logger.info("mcp_tool_call", tool=tool_name, args=arguments)
            result = await tool["handler"](**arguments)
            return {"success": True, "result": result, "tool": tool_name}
        except Exception as e:
            logger.error("mcp_tool_error", tool=tool_name, error=str(e))
            return {"success": False, "error": str(e), "tool": tool_name}

    def get_tool_schema_for_llm(self) -> List[Dict[str, Any]]:
        """生成 LLM Function Calling Schema"""
        schemas = []
        for t in self._tools.values():
            properties = {}
            required = []
            for pname, ptype in t["parameters"].items():
                is_optional = ptype.endswith("?")
                clean_type = ptype.rstrip("?")
                type_map = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}
                properties[pname] = {"type": type_map.get(clean_type, "string")}
                if not is_optional:
                    required.append(pname)

            schemas.append({
                "name": t["name"],
                "description": t["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return schemas


# 全局单例
mcp_registry = MCPRegistry()
