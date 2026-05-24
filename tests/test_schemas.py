"""测试 Pydantic 数据模型 (A2A 协议 + 工作流状态)"""

import pytest
from src.api.schemas import (
    A2ATaskRequest,
    A2ATaskResponse,
    AgentCard,
    HumanReviewRequest,
    HumanReviewResponse,
    MCPToolCall,
    MCPToolResult,
    MCPToolSchema,
    TaskStatus,
    UserInput,
    WorkflowStartRequest,
)


class TestTaskStatus:
    def test_enum_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.WAITING_HUMAN.value == "waiting_human"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_enum_membership(self):
        assert TaskStatus("completed") == TaskStatus.COMPLETED
        with pytest.raises(ValueError):
            TaskStatus("unknown")


class TestA2ATaskRequest:
    def test_minimal_request(self):
        req = A2ATaskRequest(task_id="t1", agent_name="test", task={})
        assert req.task_id == "t1"
        assert req.agent_name == "test"
        assert req.task == {}
        assert req.context == {}
        assert req.timeout == 300

    def test_full_request(self):
        req = A2ATaskRequest(
            task_id="t2",
            agent_name="agent",
            task={"text": "hello", "images": []},
            context={"style": "modern"},
            timeout=600,
        )
        assert req.task["text"] == "hello"
        assert req.context["style"] == "modern"
        assert req.timeout == 600

    def test_default_context_is_empty_dict(self):
        req = A2ATaskRequest(task_id="t1", agent_name="a", task={})
        assert req.context == {}


class TestA2ATaskResponse:
    def test_completed_response(self):
        resp = A2ATaskResponse(
            task_id="t1",
            agent_name="a1",
            status=TaskStatus.COMPLETED,
            result={"code": "print('hello')"},
        )
        assert resp.status == TaskStatus.COMPLETED
        assert resp.result["code"] == "print('hello')"
        assert resp.error is None
        assert resp.requires_human_review is False
        assert resp.tokens_used == 0

    def test_failed_response(self):
        resp = A2ATaskResponse(
            task_id="t2",
            agent_name="a2",
            status=TaskStatus.FAILED,
            error="API timeout",
        )
        assert resp.status == TaskStatus.FAILED
        assert resp.error == "API timeout"


class TestAgentCard:
    def test_basic_card(self):
        card = AgentCard(
            name="test_agent",
            description="测试 Agent",
            version="1.0.0",
            capabilities={"skills": ["code_generation"]},
            endpoint="http://localhost:8000/a2a",
        )
        assert card.name == "test_agent"
        assert "code_generation" in card.capabilities["skills"]
        assert card.mcp_servers == []

    def test_card_with_review_config(self):
        card = AgentCard(
            name="reviewer",
            description="审查",
            version="2.0.0",
            capabilities={"skills": ["review"]},
            endpoint="http://localhost/a2a",
            max_review_rounds=5,
            token_budget_per_review=10000,
        )
        assert card.max_review_rounds == 5
        assert card.token_budget_per_review == 10000

    def test_card_model_dump(self):
        card = AgentCard(
            name="agent1",
            description="desc",
            version="1.0",
            capabilities={"skills": ["s1"]},
            endpoint="http://localhost/a2a",
            model="claude-sonnet-4-6",
        )
        data = card.model_dump()
        assert data["name"] == "agent1"
        assert data["model"] == "claude-sonnet-4-6"


class TestUserInput:
    def test_text_only(self):
        u = UserInput(text="hello")
        assert u.text == "hello"
        assert u.images == []
        assert u.files == []
        assert u.context == {}

    def test_multimodal_input(self):
        u = UserInput(
            text="分析这张图",
            images=["https://example.com/img.png", "data:image/png;base64,xxx"],
            context={"task_type": "visual_analysis"},
        )
        assert len(u.images) == 2
        assert u.context["task_type"] == "visual_analysis"


class TestWorkflowStartRequest:
    def test_without_thread_id(self):
        u = UserInput(text="任务")
        req = WorkflowStartRequest(input=u)
        assert req.input.text == "任务"
        assert req.thread_id is None

    def test_with_thread_id(self):
        u = UserInput(text="继续任务")
        req = WorkflowStartRequest(input=u, thread_id="wf-123")
        assert req.thread_id == "wf-123"


class TestHumanReview:
    def test_request(self):
        req = HumanReviewRequest(
            thread_id="t1",
            checkpoint_key="after_design",
            title="设计审批",
            content={"design": "mock"},
        )
        assert req.checkpoint_key == "after_design"
        assert "approve" in req.options

    def test_response_approve(self):
        resp = HumanReviewResponse(
            thread_id="t1",
            checkpoint_key="after_design",
            decision="approve",
        )
        assert resp.decision == "approve"
        assert resp.modifications is None

    def test_response_modify(self):
        resp = HumanReviewResponse(
            thread_id="t1",
            checkpoint_key="after_design",
            decision="modify",
            modifications={"color": "blue"},
        )
        assert resp.decision == "modify"
        assert resp.modifications["color"] == "blue"


class TestMCPModels:
    def test_tool_schema(self):
        tool = MCPToolSchema(
            name="read_file",
            description="读取文件",
            parameters={"path": "str"},
        )
        assert tool.name == "read_file"
        assert tool.requires_approval is False

    def test_tool_schema_requires_approval(self):
        tool = MCPToolSchema(
            name="write_file",
            description="写入文件",
            parameters={"path": "str"},
            requires_approval=True,
        )
        assert tool.requires_approval is True

    def test_tool_call(self):
        call = MCPToolCall(
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},
        )
        assert call.tool_name == "read_file"
        assert call.arguments["path"] == "/tmp/test.txt"

    def test_tool_result_success(self):
        result = MCPToolResult(
            tool_name="read_file",
            success=True,
            result="file content here",
        )
        assert result.success is True
        assert result.result == "file content here"
        assert result.error is None

    def test_tool_result_failure(self):
        result = MCPToolResult(
            tool_name="write_file",
            success=False,
            error="permission denied",
        )
        assert result.success is False
        assert result.error == "permission denied"
