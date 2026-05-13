"""MCP 代码工具: 代码格式化、AST 分析、依赖检查"""

import ast
import subprocess
import sys
from typing import Any, Dict


async def validate_python(code: str) -> Dict[str, Any]:
    """验证 Python 代码语法"""
    try:
        ast.parse(code)
        return {"success": True, "valid": True, "message": "Python 语法正确"}
    except SyntaxError as e:
        return {
            "success": True,
            "valid": False,
            "error_line": e.lineno,
            "error_offset": e.offset,
            "message": str(e),
        }


async def format_code(code: str, language: str = "python") -> Dict[str, Any]:
    """格式化代码 (需要安装对应格式化工具)"""
    formatters = {
        "python": (["ruff", "format", "-"], ".py"),
        "javascript": (["npx", "prettier", "--stdin-filepath", "file.js"], ".js"),
    }

    if language not in formatters:
        return {"success": False, "error": f"不支持的语言: {language}"}

    cmd, _ = formatters[language]

    try:
        proc = subprocess.run(
            cmd,
            input=code,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return {"success": True, "formatted": proc.stdout}
        else:
            return {"success": False, "error": proc.stderr}
    except FileNotFoundError:
        return {"success": False, "error": f"未安装 {language} 的格式化工具"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "格式化超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def install_dependencies(requirements: str) -> Dict[str, Any]:
    """安装 Python 依赖"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", requirements],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout[-500:],
            "stderr": proc.stderr[-500:],
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "安装超时 (120s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}
