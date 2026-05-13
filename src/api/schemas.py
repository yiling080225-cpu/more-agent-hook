"""Pydantic 数据模型: A2A 协议 + 工作流状态"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


# ==================== A2A 协议模型 ====================

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"


class A2ATaskRequest(BaseModel):
    """A2A 任务委托请求"""
    task_id: str = Field(description="唯一任务 ID")
    agent_name: str = Field(description="目标 Agent 名称")
    task: Dict[str, Any] = Field(description="任务内容 (text, images, files, context)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加上下文")
    timeout: int = Field(default=300, description="超时秒数")


class A2ATaskResponse(BaseModel):
    """A2A 任务响应"""
    task_id: str
    agent_name: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    requires_human_review: bool = False
    tokens_used: int = 0
    completed_at: Optional[str] = None


class AgentCard(BaseModel):
    """Agent 能力声明 (A2A Agent Card)"""
    name: str
    description: str
    version: str
    capabilities: Dict[str, Any]
    endpoint: str
    auth: Optional[Dict[str, str]] = None
    mcp_servers: List[str] = Field(default_factory=list)
    model: Optional[str] = None
    max_context_tokens: Optional[int] = None
    max_review_rounds: Optional[int] = None
    token_budget_per_review: Optional[int] = None


# ==================== 工作流模型 ====================

class UserInput(BaseModel):
    """用户输入 (多模态)"""
    text: str = Field(description="文字需求")
    images: List[str] = Field(default_factory=list, description="图片 URL 或 base64")
    videos: List[str] = Field(default_factory=list)
    audio: Optional[str] = None
    files: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class ProjectState(BaseModel):
    """工作流项目状态 (持久化)"""
    thread_id: str = Field(description="工作流线程 ID")
    requirements: Dict[str, Any] = Field(default_factory=dict)
    ui_spec: Optional[Dict[str, Any]] = None
    backend_spec: Optional[Dict[str, Any]] = None
    content: Optional[Dict[str, Any]] = None
    human_approvals: Dict[str, bool] = Field(default_factory=dict)
    code_frontend: str = ""
    code_backend: str = ""
    review_comments: List[str] = Field(default_factory=list)
    review_round: int = 0
    deployment_url: str = ""
    status: str = "pending"
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    error: Optional[str] = None


class WorkflowStartRequest(BaseModel):
    """启动工作流请求"""
    input: UserInput
    thread_id: Optional[str] = None  # 不提供则自动生成


class WorkflowEvent(BaseModel):
    """工作流事件 (SSE 推送)"""
    thread_id: str
    node: str
    status: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str


class HumanReviewRequest(BaseModel):
    """人工审批请求"""
    thread_id: str
    checkpoint_key: str
    title: str
    content: Dict[str, Any]
    options: List[str] = ["approve", "reject", "modify"]


class HumanReviewResponse(BaseModel):
    """人工审批响应"""
    thread_id: str
    checkpoint_key: str
    decision: str  # "approve" | "reject" | "modify"
    modifications: Optional[Dict[str, Any]] = None


# ==================== MCP 模型 ====================

class MCPToolSchema(BaseModel):
    """MCP 工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    requires_approval: bool = False


class MCPToolCall(BaseModel):
    """MCP 工具调用请求"""
    tool_name: str
    arguments: Dict[str, Any]


class MCPToolResult(BaseModel):
    """MCP 工具调用结果"""
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
