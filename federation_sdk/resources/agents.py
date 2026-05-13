from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from federation_sdk._http import _HttpClient


class AgentsResource:
    """Agent 管理资源。"""

    def __init__(self, http: _HttpClient):
        self._http = http

    def list(self) -> dict:
        return self._http.get("/agents")

    async def list_async(self) -> dict:
        return await self._http.get_async("/agents")

    def card(self, name: str) -> dict:
        return self._http.get(f"/agents/{name}/card")

    async def card_async(self, name: str) -> dict:
        return await self._http.get_async(f"/agents/{name}/card")

    def health_check(self) -> dict:
        return self._http.post("/agents/health-check")

    async def health_check_async(self) -> dict:
        return await self._http.post_async("/agents/health-check")
