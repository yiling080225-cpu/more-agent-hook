from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from federation_sdk._http import _HttpClient


class SupervisorResource:
    """调度器资源：路由分析和执行。"""

    def __init__(self, http: _HttpClient):
        self._http = http

    def route(self, text: str) -> dict:
        return self._http.post("/supervisor/route", json={"text": text})

    async def route_async(self, text: str) -> dict:
        return await self._http.post_async("/supervisor/route", json={"text": text})

    def execute(self, text: str, images: list[str] | None = None,
                context: dict | None = None) -> dict:
        payload: dict = {"text": text}
        if images:
            payload["images"] = images
        if context:
            payload["context"] = context
        return self._http.post("/supervisor/execute", json=payload)

    async def execute_async(self, text: str, images: list[str] | None = None,
                            context: dict | None = None) -> dict:
        payload: dict = {"text": text}
        if images:
            payload["images"] = images
        if context:
            payload["context"] = context
        return await self._http.post_async("/supervisor/execute", json=payload)
