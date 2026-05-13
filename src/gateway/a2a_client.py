"""A2A HTTP 客户端: 向其他 Agent 发送委托请求"""

import structlog
from typing import Any, Dict, Optional

import httpx

from ..api.schemas import A2ATaskRequest, A2ATaskResponse, TaskStatus

logger = structlog.get_logger()

# 默认超时和重试配置
DEFAULT_TIMEOUT = 300
MAX_RETRIES = 2


class A2AClient:
    """A2A 协议 HTTP 客户端"""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries

    async def send_task(
        self,
        endpoint: str,
        task: Dict[str, Any],
        task_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        agent_name: str = "",
    ) -> A2ATaskResponse:
        """
        向目标 Agent 发送 A2A 任务

        Args:
            endpoint: Agent 的 /a2a 端点 URL
            task: 任务数据
            task_id: 任务 ID (不提供则自动生成)
            context: 附加上下文
            agent_name: 目标 Agent 名称

        Returns:
            A2ATaskResponse
        """
        import uuid

        request = A2ATaskRequest(
            task_id=task_id or str(uuid.uuid4()),
            agent_name=agent_name,
            task=task,
            context=context or {},
            timeout=self.timeout,
        )

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(
                        "a2a_send",
                        agent=agent_name,
                        task_id=request.task_id,
                        attempt=attempt + 1,
                    )
                    resp = await client.post(
                        endpoint,
                        json=request.model_dump(),
                        headers={"Content-Type": "application/json"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return A2ATaskResponse(**data)

            except httpx.TimeoutException:
                last_error = f"请求超时 ({self.timeout}s)"
                logger.warning("a2a_timeout", agent=agent_name, attempt=attempt + 1)
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                logger.error("a2a_http_error", agent=agent_name, error=last_error)
                break  # 非超时错误不重试
            except Exception as e:
                last_error = str(e)
                logger.error("a2a_error", agent=agent_name, error=last_error)

            if attempt < self.max_retries:
                import asyncio
                await asyncio.sleep(1 * (attempt + 1))

        # 所有重试都失败
        return A2ATaskResponse(
            task_id=request.task_id,
            agent_name=agent_name,
            status=TaskStatus.FAILED,
            error=f"A2A 通信失败 (重试 {self.max_retries} 次): {last_error}",
        )

    async def get_agent_card(self, well_known_url: str) -> Optional[Dict[str, Any]]:
        """获取 Agent 的 Agent Card"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(well_known_url)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("a2a_card_fetch_error", url=well_known_url, error=str(e))
            return None

    async def health_check(self, well_known_url: str) -> bool:
        """检查 Agent 是否在线"""
        card = await self.get_agent_card(well_known_url)
        return card is not None


# 全局单例
a2a_client = A2AClient()
