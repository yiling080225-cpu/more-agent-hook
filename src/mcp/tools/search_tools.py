"""MCP 搜索工具: Web 搜索 (Brave API)、文本搜索"""

import httpx
from typing import Any, Dict, Optional


async def web_search(
    query: str,
    num_results: int = 5,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Web 搜索 (需要 Brave Search API Key)"""
    if not api_key:
        return {
            "success": False,
            "error": "需要 BRAVE_API_KEY，请在 .env 中配置",
        }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": min(num_results, 10)},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for r in data.get("web", {}).get("results", [])[:num_results]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                })

            return {"success": True, "results": results, "query": query}
    except httpx.HTTPError as e:
        return {"success": False, "error": f"搜索请求失败: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def text_search(content: str, pattern: str) -> Dict[str, Any]:
    """在文本中搜索模式 (支持简单关键词)"""
    lines = content.split("\n")
    matches = []
    for i, line in enumerate(lines, 1):
        if pattern.lower() in line.lower():
            matches.append({"line": i, "content": line.strip()[:200]})
    return {
        "success": True,
        "pattern": pattern,
        "total_matches": len(matches),
        "matches": matches[:50],  # 最多返回 50 条
    }
