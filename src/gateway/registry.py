"""Agent Card 注册中心: 加载、发现、健康检查"""

import json
import structlog
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from ..api.schemas import AgentCard

logger = structlog.get_logger()


class AgentRegistry:
    """Agent 注册与发现中心"""

    def __init__(self, cards_dir: str = "agent_cards"):
        self._agents: Dict[str, AgentCard] = {}
        self._status: Dict[str, bool] = {}
        self._cards_dir = Path(cards_dir)
        self._load_cards()

    def _load_cards(self):
        """从 agent_cards/ 目录加载所有 Agent Card"""
        if not self._cards_dir.exists():
            logger.warning("agent_cards_dir_not_found", path=str(self._cards_dir))
            return

        for card_file in self._cards_dir.glob("*.json"):
            try:
                data = json.loads(card_file.read_text(encoding="utf-8"))
                card = AgentCard(**data)
                self._agents[card.name] = card
                self._status[card.name] = False  # 初始状态: 未检测
                logger.info("agent_card_loaded", name=card.name)
            except Exception as e:
                logger.error("agent_card_load_error", file=card_file.name, error=str(e))

        logger.info("agent_registry_ready", total=len(self._agents))

    def register(self, card: AgentCard) -> None:
        """动态注册 Agent"""
        self._agents[card.name] = card
        self._status[card.name] = False
        logger.info("agent_registered", name=card.name)

    def unregister(self, name: str) -> None:
        """注销 Agent"""
        self._agents.pop(name, None)
        self._status.pop(name, None)

    def get(self, name: str) -> Optional[AgentCard]:
        """获取 Agent Card"""
        return self._agents.get(name)

    def list_all(self) -> List[AgentCard]:
        """列出所有已注册 Agent"""
        return list(self._agents.values())

    def list_available(self) -> List[AgentCard]:
        """列出所有健康 Agent"""
        return [c for name, c in self._agents.items() if self._status.get(name, False)]

    def get_agent_url(self, name: str) -> Optional[str]:
        """获取 Agent 端点 URL"""
        agent = self._agents.get(name)
        return agent.endpoint if agent else None

    def find_by_skill(self, skill: str) -> List[AgentCard]:
        """按技能查找 Agent"""
        matches = []
        for agent in self._agents.values():
            if skill in agent.capabilities.get("skills", []):
                matches.append(agent)
        return matches

    async def health_check(self) -> Dict[str, bool]:
        """对所有 Agent 进行健康检查"""
        async with httpx.AsyncClient(timeout=5) as client:
            for name, card in self._agents.items():
                try:
                    well_known_url = card.endpoint.replace("/a2a", "/.well-known/agent.json")
                    resp = await client.get(well_known_url)
                    self._status[name] = resp.status_code == 200
                except Exception:
                    self._status[name] = False

        available = sum(1 for v in self._status.values() if v)
        logger.info("health_check_complete", total=len(self._agents), available=available)
        return dict(self._status)

    def get_status_summary(self) -> Dict[str, Any]:
        """获取注册中心状态摘要"""
        return {
            "total_agents": len(self._agents),
            "available_agents": sum(1 for v in self._status.values() if v),
            "agents": {
                name: {
                    "available": self._status.get(name, False),
                    "endpoint": card.endpoint,
                    "skills": card.capabilities.get("skills", []),
                }
                for name, card in self._agents.items()
            },
        }


# 全局单例
agent_registry = AgentRegistry()
