"""测试: SDK 数据模型"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from federation_sdk.models import (
    TaskResult, TaskStatus, SystemInfo, CostEstimate,
    Reference, ReferenceType, ImageRef, WebPageRef, ProjectRef,
)


class TestTaskResult:
    def test_create_completed(self):
        r = TaskResult(thread_id="t1", status="completed", output={"html": "<div>"})
        assert r.thread_id == "t1"
        assert r.status == "completed"
        assert r.output["html"] == "<div>"

    def test_create_failed(self):
        r = TaskResult(thread_id="t2", status="failed", error="timeout")
        assert r.error == "timeout"
        assert r.output is None


class TestReference:
    def test_image_ref(self):
        ref = ImageRef(source="/tmp/test.png", description="design")
        assert ref.type == ReferenceType.IMAGE
        assert ref.source == "/tmp/test.png"
        assert ref.encoding == "base64"

    def test_webpage_ref(self):
        ref = WebPageRef(source="https://example.com")
        assert ref.type == ReferenceType.WEB_PAGE

    def test_project_ref(self):
        ref = ProjectRef(source="/tmp/myapp")
        assert ref.type == ReferenceType.PROJECT


class TestCostEstimate:
    def test_create(self):
        ce = CostEstimate(
            task_id="est-001",
            input_tokens=1000, output_tokens=500, total_tokens=1500,
            estimated_cost=0.03, cost_range=(0.02, 0.04),
            confidence="medium",
            breakdown={"text": 1000},
        )
        assert ce.total_tokens == 1500
        assert ce.cost_range == (0.02, 0.04)


class TestSystemInfo:
    def test_create(self):
        si = SystemInfo(version="1.0", status="healthy", agents_count=3, healthy=True)
        assert si.healthy is True
        assert si.agents_count == 3


class TestTaskStatusModel:
    def test_create(self):
        ts = TaskStatus(thread_id="t1", status="running", step="code_gen", started_at="2026-01-01")
        assert ts.step == "code_gen"
