"""配置管理: 环境变量 + 模型设置 + Agent 端点 + 自动读取 cc-switch/Claude Code 配置"""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


def _load_claude_settings() -> dict:
    """从 Claude Code / cc-switch 配置中自动读取 API Keys"""
    result = {}

    # 1. 从 Claude Code settings.json 读取
    claude_settings = Path.home() / ".claude" / "settings.json"
    if claude_settings.exists():
        try:
            data = json.loads(claude_settings.read_text(encoding="utf-8"))
            env_vars = data.get("env", {})
            if env_vars.get("ANTHROPIC_AUTH_TOKEN"):
                result["anthropic_api_key"] = env_vars["ANTHROPIC_AUTH_TOKEN"]
            if env_vars.get("ANTHROPIC_BASE_URL"):
                result["anthropic_base_url"] = env_vars["ANTHROPIC_BASE_URL"]
            # 检测实际模型
            model = env_vars.get("ANTHROPIC_MODEL", "")
            if model:
                result["claude_default_model"] = model
        except Exception:
            pass

    # 2. 从 cc-switch 数据库读取 (作为备选)
    ccswitch_db = Path.home() / ".cc-switch" / "cc-switch.db"
    if ccswitch_db.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(ccswitch_db))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT settings_config FROM providers WHERE app_type='claude' AND is_current=1"
            ).fetchone()
            if row:
                config = json.loads(row["settings_config"])
                env_vars = config.get("env", {})
                if not result.get("anthropic_api_key") and env_vars.get("ANTHROPIC_AUTH_TOKEN"):
                    result["anthropic_api_key"] = env_vars["ANTHROPIC_AUTH_TOKEN"]
                if not result.get("anthropic_base_url") and env_vars.get("ANTHROPIC_BASE_URL"):
                    result["anthropic_base_url"] = env_vars["ANTHROPIC_BASE_URL"]
                if not result.get("claude_default_model") and env_vars.get("ANTHROPIC_MODEL"):
                    result["claude_default_model"] = env_vars["ANTHROPIC_MODEL"]
            conn.close()
        except Exception:
            pass

    return result


_auto_config = _load_claude_settings()
_has_anthropic = bool(_auto_config.get("anthropic_api_key"))


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # AI API Keys (自动从 cc-switch 读取，.env 中的值优先覆盖)
    gemini_api_key: str = ""
    anthropic_api_key: str = _auto_config.get("anthropic_api_key", "")
    anthropic_base_url: str = _auto_config.get("anthropic_base_url", "https://api.anthropic.com")

    # 模型选择 (根据实际用的模型自动调整)
    multimodal_model: str = "gemini-2.5-flash"
    code_model: str = _auto_config.get("claude_default_model", "claude-sonnet-4-6")
    review_model: str = _auto_config.get("claude_default_model", "claude-haiku-4-5")
    router_model: str = _auto_config.get("claude_default_model", "claude-sonnet-4-6") if _has_anthropic else "gemini-2.5-flash"

    # 服务
    host: str = "127.0.0.1"
    port: int = 8000

    # 存储
    sqlite_path: str = "data/checkpoints.db"

    # 日志
    log_level: str = "INFO"

    # Agent 端点 (本地多端口模式)
    gateway_port: int = 8000
    multimodal_agent_port: int = 8001
    code_agent_port: int = 8002
    review_agent_port: int = 8003

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def multimodal_agent_url(self) -> str:
        return f"http://{self.host}:{self.multimodal_agent_port}"

    @property
    def code_agent_url(self) -> str:
        return f"http://{self.host}:{self.code_agent_port}"

    @property
    def review_agent_url(self) -> str:
        return f"http://{self.host}:{self.review_agent_port}"

    @property
    def gateway_url(self) -> str:
        return f"http://{self.host}:{self.gateway_port}"


settings = Settings()
