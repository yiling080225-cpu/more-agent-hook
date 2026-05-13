from __future__ import annotations

from typing import TYPE_CHECKING

from federation_sdk.models import SystemInfo

if TYPE_CHECKING:
    from federation_sdk._http import _HttpClient


class SystemResource:
    """系统信息资源。"""

    def __init__(self, http: _HttpClient):
        self._http = http

    def info(self) -> SystemInfo:
        data = self._http.get("/system/info")
        agents = data.get("agents", {})
        return SystemInfo(
            version=data.get("config", {}).get("version", "unknown"),
            status="healthy" if data.get("agents") else "degraded",
            agents_count=agents.get("total_agents", 0),
            healthy=agents.get("healthy", 0) > 0,
        )

    async def info_async(self) -> SystemInfo:
        data = await self._http.get_async("/system/info")
        agents = data.get("agents", {})
        return SystemInfo(
            version=data.get("config", {}).get("version", "unknown"),
            status="healthy" if data.get("agents") else "degraded",
            agents_count=agents.get("total_agents", 0),
            healthy=agents.get("healthy", 0) > 0,
        )
