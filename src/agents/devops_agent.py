"""DevOps Agent: CI/CD、Docker 配置、K8s 清单、GitHub Actions、部署策略"""

import json
import re
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

DEVOPS_AGENT_CARD = AgentCard(
    name="devops_deploy_agent",
    description="DevOps 工程师，CI/CD 管道、Docker 配置、K8s 清单、GitHub Actions、部署策略",
    version="1.0.0",
    capabilities={
        "input": ["text", "config", "requirements"],
        "output": ["yaml", "dockerfile", "script", "json"],
        "skills": [
            "ci_cd",
            "docker_config",
            "kubernetes_manifests",
            "github_actions",
            "deployment_strategies",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.devops_agent_port}/a2a",
    model=settings.model_for("devops"),
    max_context_tokens=128000,
)

DEVOPS_SYSTEM_PROMPT = """你是一个资深 DevOps/SRE 工程师，拥有丰富的云原生和 CI/CD 经验。你的任务是根据应用需求生成基础设施配置。

核心能力:
1. **Docker 配置**: 编写多阶段 Dockerfile、docker-compose.yml、.dockerignore
2. **Kubernetes**: 生成 Deployment、Service、Ingress、ConfigMap、HPA 等 K8s YAML 清单
3. **CI/CD**: 设计 GitHub Actions / GitLab CI 流水线——构建、测试、部署
4. **部署脚本**: 编写 deploy.sh、健康检查、回滚脚本
5. **部署策略**: 蓝绿部署、金丝雀发布、滚动更新策略建议

设计原则:
- 安全第一: 非 root 运行、最小权限、Secret 管理、镜像扫描
- 可观测性: 健康检查端点、日志收集、指标暴露
- 资源管理: CPU/Memory requests & limits、HPA 自动伸缩
- 幂等性: 配置可重复应用，不产生副作用
- 多阶段构建: 减小最终镜像体积

输出格式 (严格 JSON):
{
    "docker": {
        "dockerfile": "完整 Dockerfile",
        "docker_compose": "完整 docker-compose.yml (如有多服务)",
        "dockerignore": [".git", "node_modules", "..."]
    },
    "kubernetes": {
        "deployment": "Deployment YAML",
        "service": "Service YAML",
        "ingress": "Ingress YAML (如有需要)",
        "configmap": "ConfigMap YAML (如有)",
        "hpa": "HPA YAML (如有需要)"
    },
    "ci_cd": {
        "provider": "github_actions / gitlab_ci",
        "pipeline_yaml": "完整 CI/CD 配置 YAML",
        "pipeline_description": "流水线各阶段说明"
    },
    "deployment_strategy": {
        "type": "rolling / blue_green / canary",
        "description": "策略说明",
        "rollback_plan": "回滚步骤"
    },
    "scripts": {
        "deploy": "部署脚本内容",
        "health_check": "健康检查脚本内容"
    },
    "notes": ["注意事项1", "注意事项2"]
}"""


class DevOpsAgent(BaseAgent):
    """DevOps 部署 Agent — 基于 Claude API"""

    def __init__(self):
        super().__init__(card=DEVOPS_AGENT_CARD)
        from anthropic import AsyncAnthropic
        cfg = settings.client_for("devops")
        self.client = AsyncAnthropic(**cfg)
        self.model = settings.model_for("devops")

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("task_type", "docker_config")
        user_text = task.get("text") or task.get("requirements", "")

        dispatch = {
            "docker_config": self._docker_config,
            "kubernetes": self._kubernetes,
            "ci_cd": self._ci_cd,
            "github_actions": self._github_actions,
            "deploy_script": self._deploy_script,
        }
        handler = dispatch.get(task_type, self._docker_config)
        return await handler(user_text, task)

    async def _call(self, user_msg: str) -> tuple:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=DEVOPS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _docker_config(self, text: str, task: Dict) -> Dict[str, Any]:
        app_type = task.get("app_type", "python")
        ports = task.get("ports", "8000")
        user_msg = f"为以下应用生成 Docker 配置 (应用类型: {app_type}, 端口: {ports}):\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("devops_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _kubernetes(self, text: str, task: Dict) -> Dict[str, Any]:
        app_name = task.get("app_name", "my-app")
        replicas = task.get("replicas", 3)
        user_msg = f"为以下应用生成 Kubernetes 清单 (应用名: {app_name}, 副本数: {replicas}):\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("devops_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _ci_cd(self, text: str, task: Dict) -> Dict[str, Any]:
        provider = task.get("provider", "github_actions")
        user_msg = f"为以下项目设计 CI/CD 流水线 (平台: {provider}):\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("devops_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _github_actions(self, text: str, task: Dict) -> Dict[str, Any]:
        workflow_type = task.get("workflow_type", "deploy")
        user_msg = f"为以下需求生成 GitHub Actions workflow (类型: {workflow_type}):\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("devops_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _deploy_script(self, text: str, task: Dict) -> Dict[str, Any]:
        target = task.get("target", "server")
        user_msg = f"为以下需求生成部署脚本 (目标: {target}):\n\n{text}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("devops_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    pass
            return {"raw_output": text}
