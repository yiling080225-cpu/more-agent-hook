"""配置管理: CC-Switch DB 自动读取 (单一真实源) + .env 可覆盖"""

import json
import sqlite3
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# ── 从 CC-Switch DB 自动读取 API Key + URL + Model ──
_CCSWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"


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
            if url:
                url = url.rstrip("/")
                for suffix in ("/v1/messages", "/v1/chat/completions", "/v1"):
                    if url.endswith(suffix):
                        url = url[: -len(suffix)]
                        break
            name_lower = name.lower()
            if "deepseek" in name_lower:
                keys.setdefault("deepseek_key", token)
                if url:
                    keys.setdefault("deepseek_url", url)
                if model:
                    keys.setdefault("deepseek_model", model)
            elif "gpt" in name_lower:
                keys.setdefault("gpt_key", token)
                if url:
                    keys.setdefault("gpt_url", url)
                if model:
                    keys.setdefault("gpt_model", model)
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

    # === 4 大 LLM 供应商 API Keys (CC-Switch 自动注入, .env 可覆盖) ===
    deepseek_key: str = ""
    deepseek_url: str = "https://api.deepseek.com/anthropic"
    deepseek_model: str = "deepseek-v4-pro[1m]"

    glm_key: str = ""
    glm_url: str = "https://open.bigmodel.cn/api/anthropic"
    glm_model: str = "glm-4.6V"

    gpt_key: str = ""
    gpt_url: str = "https://shiyunapi.com/v1/chat/completions"
    gpt_model: str = "gpt-5.5"

    opus_key: str = ""
    opus_url: str = "https://shiyunapi.com/v1/messages"
    opus_model: str = "claude-opus-4-8"

    clawsocket_key: str = ""
    clawsocket_url: str = ""

    gemini_key: str = ""

    # === 服务 ===
    host: str = "127.0.0.1"
    port: int = 8000
    sqlite_path: str = "data/checkpoints.db"
    log_level: str = "INFO"

    # === 12 Agent 端口 — 4 层架构 ===
    gateway_port: int = 8000

    # 设计层 (8001-8003)
    multimodal_agent_port: int = 8001
    ux_agent_port: int = 8002
    brand_agent_port: int = 8003

    # 工程层 (8004-8007)
    code_agent_port: int = 8004
    test_agent_port: int = 8005
    devops_agent_port: int = 8006
    review_agent_port: int = 8007

    # 战略层 (8008-8010)
    architect_agent_port: int = 8008
    prompt_agent_port: int = 8009
    crew_agent_port: int = 8010

    # 基础层 (8011-8012)
    knowledge_agent_port: int = 8011
    security_agent_port: int = 8012

    # ── 能力检测 ──

    @property
    def has_any_api_key(self) -> bool:
        return bool(self.deepseek_key or self.glm_key or self.clawsocket_key or self.gemini_key or self.gpt_key or self.opus_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.clawsocket_key or self.gpt_key or self.opus_key)

    @property
    def anthropic_base_url(self) -> str:
        return self.gpt_url or self.opus_url or self.clawsocket_url

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_key)

    # ── LLM 分配策略: 每个 Agent 固定分配最佳供应商 ──

    AGENT_LLM_MAP: dict[str, str] = {
        # 设计层
        "multimodal": "glm",     # GLM 视觉最强
        "ux": "gpt",             # GPT 交互设计
        "brand": "deepseek",     # DeepSeek 性价比
        # 工程层
        "code": "gpt",           # GPT 代码质量
        "test": "deepseek",      # DeepSeek 批量生成
        "devops": "deepseek",    # DeepSeek 脚本生成
        "review": "opus",        # Opus 安全审查不能用差的
        # 战略层
        "architect": "opus",     # Opus 架构决策不能错
        "prompt": "gpt",         # GPT 提示词设计
        "crew": "gpt",           # GPT 多角色协作
        # 基础层
        "knowledge": "deepseek", # DeepSeek 文档处理
        "security": "opus",      # Opus 渗透测试/合规
        "router": "deepseek",    # 路由本身轻量
    }

    def _preferred_provider(self, agent: str) -> str:
        """返回 Agent 的首选供应商名 (opus/gpt/glm/deepseek)"""
        return self.AGENT_LLM_MAP.get(agent, "deepseek")

    def _provider(self, provider: str) -> dict:
        """将供应商名转为 {api_key, base_url}"""
        if provider == "opus" and self.opus_key:
            return {"api_key": self.opus_key, "base_url": self.opus_url}
        if provider == "gpt" and self.gpt_key:
            return {"api_key": self.gpt_key, "base_url": self.gpt_url}
        if provider == "glm" and self.glm_key:
            return {"api_key": self.glm_key, "base_url": self.glm_url}
        if provider == "deepseek" and self.deepseek_key:
            return {"api_key": self.deepseek_key, "base_url": self.deepseek_url}
        return {}

    def client_for(self, agent: str) -> dict:
        """返回 {api_key, base_url} — 给 AsyncAnthropic 初始化.

        策略: 首选供应商不可用时自动降级.
        降级链: Opus→GPT→DeepSeek→GLM (按推理能力排序)
        """
        preferred = self._preferred_provider(agent)
        fallback_order = {
            "opus": ["opus", "gpt", "deepseek", "glm"],
            "gpt": ["gpt", "opus", "deepseek", "glm"],
            "glm": ["glm", "opus", "gpt", "deepseek"],
            "deepseek": ["deepseek", "opus", "gpt", "glm"],
        }
        for p in fallback_order.get(preferred, ["deepseek"]):
            cfg = self._provider(p)
            if cfg:
                return cfg
        return {"api_key": "", "base_url": ""}

    def _model_for_provider(self, provider: str) -> str:
        """返回供应商对应的模型名"""
        if provider == "opus":
            return self.opus_model
        if provider == "gpt":
            return self.gpt_model
        if provider == "glm":
            return self.glm_model
        if provider == "deepseek":
            return self.deepseek_model
        return "deepseek-chat"

    def model_for(self, agent: str) -> str:
        """返回 Agent 应使用的模型名 (与 client_for 同降级链)"""
        preferred = self._preferred_provider(agent)
        fallback_order = {
            "opus": ["opus", "gpt", "deepseek", "glm"],
            "gpt": ["gpt", "opus", "deepseek", "glm"],
            "glm": ["glm", "opus", "gpt", "deepseek"],
            "deepseek": ["deepseek", "opus", "gpt", "glm"],
        }
        for p in fallback_order.get(preferred, ["deepseek"]):
            if self._provider(p):
                return self._model_for_provider(p)
        return "deepseek-chat"

    # ── 协作管道配置 ──

    @property
    def pipeline_design(self) -> list[str]:
        """设计产出管道: 品牌→交互→视觉"""
        return ["brand_creative_agent", "ux_interaction_agent", "multimodal_design_agent"]

    @property
    def pipeline_engineering(self) -> list[str]:
        """工程产出管道: 架构→编码→审查→测试→部署"""
        return ["project_architect_agent", "secure_code_agent", "code_review_agent",
                "testing_qa_agent", "devops_deploy_agent"]

    @property
    def pipeline_strategy(self) -> list[str]:
        """战略产出管道: 提示词设计→多角色验证→审查"""
        return ["prompt_engineer_agent", "crew_collaboration_agent", "code_review_agent"]

    @property
    def pipeline_full_flow(self) -> list:
        """全流程管道: 13步5阶段，组内并行，组间顺序。
        这是 LangGraph full_flow_workflow 的降级方案 (不使用 checkpoint 和审批)。

        阶段1: 需求调研→需求文档
        阶段2: [原型设计∥可行性评估∥技术选型]→架构设计→[数据库设计∥接口文档]
        阶段3: 编码开发
        阶段4: [代码审查∥测试验证]→部署上线
        阶段5: 验收交付
        """
        return [
            # 阶段1
            ["crew_collaboration_agent"],                           # 步骤1
            ["prompt_engineer_agent"],                              # 步骤2
            # 阶段2 (并行组1 + 架构 + 并行组2)
            ["ux_interaction_agent", "project_architect_agent"],   # 步骤3-5 并行
            ["project_architect_agent"],                            # 步骤6
            ["secure_code_agent"],                                  # 步骤7-8 (DB+API 合并)
            # 阶段3
            ["secure_code_agent"],                                  # 步骤9
            # 阶段4 (并行组3 + 部署)
            ["code_review_agent", "testing_qa_agent"],             # 步骤10-11 并行
            ["devops_deploy_agent"],                                # 步骤12
            # 阶段5
            ["crew_collaboration_agent", "knowledge_rag_agent"],   # 步骤13
        ]

    # ── URL 快捷属性 ──

    @property
    def multimodal_agent_url(self) -> str:
        return f"http://{self.host}:{self.multimodal_agent_port}"

    @property
    def ux_agent_url(self) -> str:
        return f"http://{self.host}:{self.ux_agent_port}"

    @property
    def brand_agent_url(self) -> str:
        return f"http://{self.host}:{self.brand_agent_port}"

    @property
    def code_agent_url(self) -> str:
        return f"http://{self.host}:{self.code_agent_port}"

    @property
    def test_agent_url(self) -> str:
        return f"http://{self.host}:{self.test_agent_port}"

    @property
    def devops_agent_url(self) -> str:
        return f"http://{self.host}:{self.devops_agent_port}"

    @property
    def review_agent_url(self) -> str:
        return f"http://{self.host}:{self.review_agent_port}"

    @property
    def architect_agent_url(self) -> str:
        return f"http://{self.host}:{self.architect_agent_port}"

    @property
    def prompt_agent_url(self) -> str:
        return f"http://{self.host}:{self.prompt_agent_port}"

    @property
    def crew_agent_url(self) -> str:
        return f"http://{self.host}:{self.crew_agent_port}"

    @property
    def knowledge_agent_url(self) -> str:
        return f"http://{self.host}:{self.knowledge_agent_port}"

    @property
    def security_agent_url(self) -> str:
        return f"http://{self.host}:{self.security_agent_port}"

    @property
    def gateway_url(self) -> str:
        return f"http://{self.host}:{self.gateway_port}"


settings = Settings()
