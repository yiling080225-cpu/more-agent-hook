"""配置管理: 从环境变量 (.env) 读取供应商 + Agent 模型分配"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # === 供应商 1: DeepSeek (Anthropic 兼容) ===
    deepseek_key: str = ""
    deepseek_url: str = "https://api.deepseek.com/anthropic"

    # === 供应商 2: 智谱 GLM (Anthropic 兼容, 视觉能力强) ===
    glm_key: str = ""
    glm_url: str = ""

    # === 供应商 3: clawsocket 聚合 (Anthropic 兼容, 含 Claude + GPT) ===
    clawsocket_key: str = ""
    clawsocket_url: str = ""

    # === Gemini (独立, 需翻墙) ===
    gemini_key: str = ""

    # === 模型分配 ===
    router_model: str = "claude-sonnet-4-6"
    multimodal_model: str = "claude-sonnet-4-6"
    code_model: str = "claude-sonnet-4-6"
    review_model: str = "claude-haiku-4-5"

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

    @property
    def has_anthropic(self) -> bool:
        return bool(self.clawsocket_key)

    @property
    def anthropic_base_url(self) -> str:
        return self.clawsocket_url

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_key)

    def client_for(self, agent: str) -> dict:
        """返回 {api_key, base_url} 给对应 Agent"""
        if agent == "multimodal":
            return {"api_key": self.glm_key, "base_url": self.glm_url}
        return {"api_key": self.deepseek_key, "base_url": self.deepseek_url}

    # === URL 快捷属性 ===
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


def _load_claude_settings() -> dict:
    """从环境变量加载 Claude 设置 (兼容旧接口)"""
    return {
        "anthropic_api_key": settings.clawsocket_key,
        "anthropic_base_url": settings.clawsocket_url,
        "claude_default_model": settings.code_model,
    }


settings = Settings()
