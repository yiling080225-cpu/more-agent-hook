from __future__ import annotations

import uuid
from typing import Any, Optional

from federation_sdk._http import _HttpClient
from federation_sdk.models import (
    CostEstimate,
    Reference,
    SystemInfo,
    TaskResult,
    TaskStatus,
)
from federation_sdk.references import estimate_reference_tokens
from federation_sdk.resources.supervisor import SupervisorResource
from federation_sdk.resources.workflow import WorkflowResource
from federation_sdk.resources.agents import AgentsResource
from federation_sdk.resources.system import SystemResource


class FederationClient:
    """SDK 单一入口。同步异步共用实例。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: int = 300):
        self._http = _HttpClient(base_url, timeout)

    @property
    def supervisor(self) -> SupervisorResource:
        return SupervisorResource(self._http)

    @property
    def workflow(self) -> WorkflowResource:
        return WorkflowResource(self._http)

    @property
    def agents(self) -> AgentsResource:
        return AgentsResource(self._http)

    @property
    def system(self) -> SystemResource:
        return SystemResource(self._http)

    # === 简便层 ===

    def execute(self, text: str, *,
                images: Optional[list[str]] = None,
                references: Optional[list[Reference]] = None,
                files: Optional[list[str]] = None,
                context: Optional[dict[str, Any]] = None,
                style: str = "modern",
                theme: Optional[str] = None,
                output_format: str = "both",
                allow_search: Optional[bool] = None,
                sandbox: bool = True,
                wait: bool = True,
                timeout: int = 600) -> TaskResult:
        ctx: dict[str, Any] = {**(context or {}), "style": style, "output_format": output_format,
                                "sandbox": sandbox}
        if theme:
            ctx["theme"] = theme
        if allow_search is not None:
            ctx["allow_search"] = allow_search
        if references:
            ctx["references"] = [
                {"type": r.type.value, "source": r.source, "description": r.description}
                for r in references
            ]

        payload: dict[str, Any] = {"text": text, "context": ctx}
        if images:
            payload["images"] = images
        if files:
            payload["files"] = files

        data = self._http.post("/supervisor/execute", json=payload, timeout=timeout)
        thread_id = data.get("thread_id", "")
        status = data.get("status", "completed")

        if status == "waiting_human":
            return TaskResult(
                thread_id=thread_id,
                status="waiting_human",
                output=data.get("result"),
            )
        return TaskResult(
            thread_id=thread_id,
            status=status,
            output=data.get("result"),
            error=data.get("error"),
        )

    async def execute_async(self, text: str, *,
                            images: Optional[list[str]] = None,
                            references: Optional[list[Reference]] = None,
                            files: Optional[list[str]] = None,
                            context: Optional[dict[str, Any]] = None,
                            style: str = "modern",
                            theme: Optional[str] = None,
                            output_format: str = "both",
                            allow_search: Optional[bool] = None,
                            sandbox: bool = True,
                            wait: bool = True,
                            timeout: int = 600) -> TaskResult:
        ctx: dict[str, Any] = {**(context or {}), "style": style, "output_format": output_format,
                                "sandbox": sandbox}
        if theme:
            ctx["theme"] = theme
        if allow_search is not None:
            ctx["allow_search"] = allow_search
        if references:
            ctx["references"] = [
                {"type": r.type.value, "source": r.source, "description": r.description}
                for r in references
            ]

        payload: dict[str, Any] = {"text": text, "context": ctx}
        if images:
            payload["images"] = images
        if files:
            payload["files"] = files

        data = await self._http.post_async("/supervisor/execute", json=payload, timeout=timeout)
        thread_id = data.get("thread_id", "")
        status = data.get("status", "completed")

        if status == "waiting_human":
            return TaskResult(
                thread_id=thread_id,
                status="waiting_human",
                output=data.get("result"),
            )
        return TaskResult(
            thread_id=thread_id,
            status=status,
            output=data.get("result"),
            error=data.get("error"),
        )

    def estimate(self, text: str, *,
                 images: Optional[list[str]] = None,
                 references: Optional[list[Reference]] = None,
                 style: str = "modern",
                 output_format: str = "both",
                 allow_search: Optional[bool] = None) -> CostEstimate:
        task_id = f"est-{uuid.uuid4().hex[:8]}"
        input_tokens = max(len(text) // 2, 100)
        if allow_search:
            input_tokens += 3000

        breakdown: dict[str, Any] = {"需求文本": input_tokens}
        warnings: list[str] = []

        if references:
            ref_tokens, ref_warnings = estimate_reference_tokens(references)
            input_tokens += ref_tokens
            breakdown["参考素材"] = ref_tokens
            warnings.extend(ref_warnings)

        if images:
            img_tokens = len(images) * 5000
            input_tokens += img_tokens
            breakdown["图片"] = img_tokens

        if len(text) < 50:
            output_tokens = 3000
        elif len(text) < 200:
            output_tokens = 8000
        else:
            output_tokens = 15000

        total = input_tokens + output_tokens
        cost = (input_tokens / 1000) * 0.015 + (output_tokens / 1000) * 0.030
        cost_low = round(cost * 0.8, 4)
        cost_high = round(cost * 1.2, 4)
        cost_mid = round(cost, 4)

        return CostEstimate(
            task_id=task_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost=cost_mid,
            cost_range=(cost_low, cost_high),
            confidence="medium",
            breakdown=breakdown,
            warnings=warnings,
        )

    async def estimate_async(self, text: str, *,
                             images: Optional[list[str]] = None,
                             references: Optional[list[Reference]] = None,
                             style: str = "modern",
                             output_format: str = "both",
                             allow_search: Optional[bool] = None) -> CostEstimate:
        return self.estimate(text, images=images, references=references,
                             style=style, output_format=output_format,
                             allow_search=allow_search)

    def status(self, thread_id: str) -> TaskStatus:
        data = self._http.get(f"/workflow/{thread_id}/status")
        return TaskStatus(
            thread_id=thread_id,
            status=data.get("status", "unknown"),
            step=data.get("step", ""),
            started_at=data.get("started_at", ""),
        )

    async def status_async(self, thread_id: str) -> TaskStatus:
        data = await self._http.get_async(f"/workflow/{thread_id}/status")
        return TaskStatus(
            thread_id=thread_id,
            status=data.get("status", "unknown"),
            step=data.get("step", ""),
            started_at=data.get("started_at", ""),
        )

    def approve(self, thread_id: str, *, note: str = "") -> TaskResult:
        data = self._http.post(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": "approve",
                  "modifications": {"note": note}},
        )
        return TaskResult(
            thread_id=thread_id,
            status=data.get("status", "completed"),
            output=data.get("result"),
        )

    async def approve_async(self, thread_id: str, *, note: str = "") -> TaskResult:
        data = await self._http.post_async(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": "approve",
                  "modifications": {"note": note}},
        )
        return TaskResult(
            thread_id=thread_id,
            status=data.get("status", "completed"),
            output=data.get("result"),
        )

    def reject(self, thread_id: str, *, reason: str = "") -> TaskResult:
        data = self._http.post(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": "reject",
                  "modifications": {"reason": reason}},
        )
        return TaskResult(
            thread_id=thread_id,
            status=data.get("status", "completed"),
            output=data.get("result"),
        )

    async def reject_async(self, thread_id: str, *, reason: str = "") -> TaskResult:
        data = await self._http.post_async(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": "reject",
                  "modifications": {"reason": reason}},
        )
        return TaskResult(
            thread_id=thread_id,
            status=data.get("status", "completed"),
            output=data.get("result"),
        )

    def health(self) -> SystemInfo:
        data = self._http.get("/health")
        return SystemInfo(
            version=data.get("version", "unknown"),
            status=data.get("status", "unknown"),
            agents_count=data.get("agents_registered", 0),
            healthy=data.get("status") == "healthy",
        )

    async def health_async(self) -> SystemInfo:
        data = await self._http.get_async("/health")
        return SystemInfo(
            version=data.get("version", "unknown"),
            status=data.get("status", "unknown"),
            agents_count=data.get("agents_registered", 0),
            healthy=data.get("status") == "healthy",
        )
