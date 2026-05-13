from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable, Optional

from federation_sdk.models import TaskResult

if TYPE_CHECKING:
    from federation_sdk._http import _HttpClient


class WorkflowHandle:
    """工作流句柄，用于跟踪和等待工作流完成。"""

    def __init__(self, http: _HttpClient, thread_id: str):
        self._http = http
        self.thread_id = thread_id
        self.status = "pending"
        self.result: Optional[dict] = None

    def wait(self, timeout: int = 600) -> TaskResult:
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self._http.get(f"/workflow/{self.thread_id}/status")
            self.status = data.get("status", "running")
            if self.status in ("completed", "failed"):
                return TaskResult(
                    thread_id=self.thread_id,
                    status=self.status,
                    output=data.get("result"),
                )
            time.sleep(2)
        return TaskResult(
            thread_id=self.thread_id,
            status="timeout",
            error=f"工作流在 {timeout}s 内未完成",
        )

    async def wait_async(self, timeout: int = 600) -> TaskResult:
        import asyncio
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = await self._http.get_async(f"/workflow/{self.thread_id}/status")
            self.status = data.get("status", "running")
            if self.status in ("completed", "failed"):
                return TaskResult(
                    thread_id=self.thread_id,
                    status=self.status,
                    output=data.get("result"),
                )
            await asyncio.sleep(2)
        return TaskResult(
            thread_id=self.thread_id,
            status="timeout",
            error=f"工作流在 {timeout}s 内未完成",
        )

    def on_progress(self, callback: Callable[[str, dict], None]) -> None:
        self._progress_callback = callback


class WorkflowResource:
    """工作流资源。"""

    def __init__(self, http: _HttpClient):
        self._http = http

    def start(self, text: str, images: list[str] | None = None,
              context: dict | None = None) -> WorkflowHandle:
        payload: dict = {"input": {"text": text}}
        if images:
            payload["input"]["images"] = images
        if context:
            payload["input"]["context"] = context
        data = self._http.post("/workflow/start", json=payload)
        return WorkflowHandle(self._http, data.get("thread_id", ""))

    async def start_async(self, text: str, images: list[str] | None = None,
                          context: dict | None = None) -> WorkflowHandle:
        payload: dict = {"input": {"text": text}}
        if images:
            payload["input"]["images"] = images
        if context:
            payload["input"]["context"] = context
        data = await self._http.post_async("/workflow/start", json=payload)
        return WorkflowHandle(self._http, data.get("thread_id", ""))

    def resume(self, thread_id: str, decision: str,
               modifications: dict | None = None) -> dict:
        return self._http.post(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": decision,
                  "modifications": modifications},
        )

    async def resume_async(self, thread_id: str, decision: str,
                           modifications: dict | None = None) -> dict:
        return await self._http.post_async(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": decision,
                  "modifications": modifications},
        )

    def status(self, thread_id: str) -> dict:
        return self._http.get(f"/workflow/{thread_id}/status")

    async def status_async(self, thread_id: str) -> dict:
        return await self._http.get_async(f"/workflow/{thread_id}/status")

    def list(self) -> dict:
        return self._http.get("/workflows")

    async def list_async(self) -> dict:
        return await self._http.get_async("/workflows")
