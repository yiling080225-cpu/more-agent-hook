"""MCP 文件工具: 读写文件、列出目录"""

import os
import json
from pathlib import Path
from typing import Any, Dict


async def read_file(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取文件内容"""
    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"文件不存在: {path}"}
        if p.stat().st_size > 10 * 1024 * 1024:  # 10MB 限制
            return {"success": False, "error": "文件超过 10MB 限制"}
        content = p.read_text(encoding=encoding)
        return {"success": True, "content": content, "size": len(content), "path": str(p.absolute())}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def write_file(path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """写入文件"""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return {"success": True, "path": str(p.absolute()), "size": len(content)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_directory(path: str = ".") -> Dict[str, Any]:
    """列出目录内容"""
    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"目录不存在: {path}"}
        if not p.is_dir():
            return {"success": False, "error": f"不是目录: {path}"}
        entries = []
        for entry in sorted(p.iterdir()):
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
        return {"success": True, "path": str(p.absolute()), "entries": entries}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def read_json(path: str) -> Dict[str, Any]:
    """读取 JSON 文件"""
    result = await read_file(path)
    if not result["success"]:
        return result
    try:
        data = json.loads(result["content"])
        return {"success": True, "data": data, "path": path}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析错误: {e}"}
