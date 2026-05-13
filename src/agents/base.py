"""Agent 基类: 实现 A2A 标准端点 (/.well-known/agent.json + /a2a)"""

import uuid
import structlog
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

from ..api.schemas import A2ATaskRequest, A2ATaskResponse, AgentCard, TaskStatus

logger = structlog.get_logger()


class BaseAgent(ABC):
    """A2A 协议 Agent 基类"""

    def __init__(self, card: AgentCard):
        self.card = card
        self.name = card.name
        self._running_tasks: Dict[str, A2ATaskResponse] = {}

    def get_agent_card(self) -> Dict[str, Any]:
        """返回 A2A Agent Card (/.well-known/agent.json)"""
        return self.card.model_dump(exclude_none=True)

    async def handle_a2a_task(self, request: A2ATaskRequest) -> A2ATaskResponse:
        """处理 A2A 任务委托 (/a2a)"""
        task_id = request.task_id or str(uuid.uuid4())

        try:
            logger.info("agent_task_start", agent=self.name, task_id=task_id)

            result_data = await self.execute(request.task, request.context)

            response = A2ATaskResponse(
                task_id=task_id,
                agent_name=self.name,
                status=TaskStatus.COMPLETED,
                result=result_data,
                requires_human_review=self._needs_review(result_data),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.error("agent_task_error", agent=self.name, task_id=task_id, error=str(e))
            response = A2ATaskResponse(
                task_id=task_id,
                agent_name=self.name,
                status=TaskStatus.FAILED,
                error=str(e),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        self._running_tasks[task_id] = response
        return response

    @abstractmethod
    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行具体任务 — 子类实现"""
        ...

    def _needs_review(self, result: Dict[str, Any]) -> bool:
        """判断是否需要人工审查"""
        return result.get("confidence", 1.0) < 0.7

    def get_task_status(self, task_id: str) -> Optional[A2ATaskResponse]:
        """查询任务状态"""
        return self._running_tasks.get(task_id)
