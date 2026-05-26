"""配置管理: .env 文件 + 环境变量 + 启动时友好校验"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # === API Keys ===
    deepseek_key: str = ""
    deepseek_url: str = "https://api.deepseek.com/anthropic"

    glm_key: str = ""
    glm_url: str = "https://open.bigmodel.cn/api/paas/v4"

    clawsocket_key: str = ""
    clawsocket_url: str = ""

    gemini_key: str = ""

    # === 模型分配 ===
    router_model: str = "deepseek-chat"
    multimodal_model: str = "deepseek-chat"
    code_model: str = "deepseek-chat"
    review_model: str = "deepseek-chat"

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
    def has_any_api_key(self) -> bool:
        return bool(self.deepseek_key or self.glm_key or self.clawsocket_key or self.gemini_key)

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
            if self.glm_key:
                return {"api_key": self.glm_key, "base_url": self.glm_url}
            return {"api_key": self.deepseek_key, "base_url": self.deepseek_url}
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


settings = Settings()
