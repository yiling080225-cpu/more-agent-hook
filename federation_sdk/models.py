from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ReferenceType(str, Enum):
    IMAGE = "image"
    WEB_PAGE = "web_page"
    PROJECT = "project"


class Reference(BaseModel):
    type: ReferenceType
    source: str
    description: str = ""
    encoding: str = "base64"


class ImageRef(Reference):
    type: ReferenceType = ReferenceType.IMAGE


class WebPageRef(Reference):
    type: ReferenceType = ReferenceType.WEB_PAGE


class ProjectRef(Reference):
    type: ReferenceType = ReferenceType.PROJECT


class TaskStatus(BaseModel):
    thread_id: str
    status: str
    step: str = ""
    started_at: str = ""


class TaskResult(BaseModel):
    thread_id: str
    status: str
    output: Optional[dict[str, Any]] = None
    preview_path: Optional[str] = None
    error: Optional[str] = None


class CostEstimate(BaseModel):
    task_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    cost_range: tuple[float, float]
    confidence: str
    breakdown: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SystemInfo(BaseModel):
    version: str
    status: str
    agents_count: int
    healthy: bool
