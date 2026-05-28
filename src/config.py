"""配置管理: CC-Switch DB 自动读取 (单一真实源) + .env 可覆盖"""

import json
import sqlite3
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# ── 从 CC-Switch DB 自动读取 API Key + URL + Model ──
_CCSWITCH_DB = Path(os.path.expandvars(r"%USERPROFILE%\.cc-switch\cc-switch.db"))


def _load_ccswitch_keys() -> dict[str, str]:
    """从 CC-Switch SQLite 读取所有 Anthropic-format provider 的 key/url/model."""
    keys: dict[str, str] = {}
    if not _CCSWITCH_DB.exists():
        return keys
    try:
        db = sqlite3.connect(str(_CCSWITCH_DB))
        rows = db.execute(
            "SELECT name, settings_config FROM providers WHERE app_type='claude'"
        ).fetchall()
        db.close()
        for name, cfg_json in rows:
            try:
                cfg = json.loads(cfg_json)
                env = cfg.get("env", {})
                token = env.get("ANTHROPIC_AUTH_TOKEN", "")
                url = env.get("ANTHROPIC_BASE_URL", "")
                model = env.get("ANTHROPIC_MODEL", "")
            except (json.JSONDecodeError, TypeError):
                continue
            if not token:
                continue
            name_lower = name.lower()
            if "deepseek" in name_lower:
                keys.setdefault("deepseek_key", token)
                if url:
                    keys.setdefault("deepseek_url", url)
                if model:
                    keys.setdefault("deepseek_model", model)
            elif "opus" in name_lower:
                keys.setdefault("opus_key", token)
                if url:
                    keys.setdefault("opus_url", url)
                if model:
                    keys.setdefault("opus_model", model)
            elif "zhipu" in name_lower or "glm" in name_lower:
                keys.setdefault("glm_key", token)
                if url:
                    keys.setdefault("glm_url", url)
                if model:
                    keys.setdefault("glm_model", model)
    except Exception:
        pass
    return keys


_CC_KEYS = _load_ccswitch_keys()
for _k, _v in _CC_KEYS.items():
    os.environ.setdefault(_k.upper(), _v)


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # === API Keys (CC-Switch 自动注入, .env 可覆盖) ===
    deepseek_key: str = ""
    deepseek_url: str = "https://api.deepseek.com/anthropic"
    deepseek_model: str = "deepseek-chat"

    glm_key: str = ""
    glm_url: str = "https://open.bigmodel.cn/api/anthropic"
    glm_model: str = "glm-4.6V"

    opus_key: str = ""
    opus_url: str = "https://shiyunapi.com"
    opus_model: str = "claude-opus-4-7"

    clawsocket_key: str = ""
    clawsocket_url: str = ""

    gemini_key: str = ""

    # === 服务 ===
    host: str = "127.0.0.1"
    port: int = 8000
    sqlite_path: str = "data/checkpoints.db"
    log_level: str = "INFO"

    # === Agent 端口 ===
    gateway_port: int = 8000
    multimodal_agent_port: int = 8001
    code_agent_port: int = 8002
    review_agent_port: int = 8003

    # ── 能力检测 ──

    @property
    def has_any_api_key(self) -> bool:
        return bool(self.deepseek_key or self.glm_key or self.clawsocket_key or self.gemini_key or self.opus_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.clawsocket_key or self.opus_key)

    @property
    def anthropic_base_url(self) -> str:
        return self.opus_url or self.clawsocket_url

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_key)

    # ── 智能路由: 根据可用供应商自动选择 endpoint + model ──

    def client_for(self, agent: str) -> dict:
        """返回 {api_key, base_url} — 给 AsyncAnthropic 初始化"""
        if agent == "multimodal":
            if self.glm_key:
                return {"api_key": self.glm_key, "base_url": self.glm_url}
            if self.opus_key:
                return {"api_key": self.opus_key, "base_url": self.opus_url}
            return {"api_key": self.deepseek_key, "base_url": self.deepseek_url}
        if agent == "code" or agent == "router":
            # DeepSeek 优先 (便宜、1M 上下文、分类/编码足够强)
            if self.deepseek_key:
                return {"api_key": self.deepseek_key, "base_url": self.deepseek_url}
            if self.opus_key:
                return {"api_key": self.opus_key, "base_url": self.opus_url}
            return {"api_key": "", "base_url": ""}
        # review: Opus > DeepSeek (审查是高风险的, 值得用最强推理)
        if self.opus_key:
            return {"api_key": self.opus_key, "base_url": self.opus_url}
        if self.deepseek_key:
            return {"api_key": self.deepseek_key, "base_url": self.deepseek_url}
        if self.glm_key:
            return {"api_key": self.glm_key, "base_url": self.glm_url}
        return {"api_key": "", "base_url": ""}

    def model_for(self, agent: str) -> str:
        """返回对应 Agent 应使用的模型名 (来自 CC-Switch ANTHROPIC_MODEL)"""
        if agent == "multimodal":
            if self.glm_key:
                return self.glm_model
            if self.opus_key:
                return self.opus_model
            return self.deepseek_model
        if agent == "code" or agent == "router":
            if self.deepseek_key:
                return self.deepseek_model
            if self.opus_key:
                return self.opus_model
            return "deepseek-chat"
        # review: Opus > DeepSeek > GLM
        if self.opus_key:
            return self.opus_model
        if self.deepseek_key:
            return self.deepseek_model
        if self.glm_key:
            return self.glm_model
        return "deepseek-chat"

    # ── URL 快捷属性 ──

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
