from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-secret-change-before-demo"


class Settings(BaseSettings):
    app_name: str = "AlwaysHealthy"
    env: str = "dev"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://alwayshealthy:alwayshealthy@localhost:5432/alwayshealthy"
    db_echo: bool = False

    # memory 用于本地开发与测试，postgres 用于演示部署
    checkpointer: str = "memory"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    # 留空则不开放管理员自助注册。演示时给一个值并写进 deployment/.env，
    # 生产部署务必换成不易猜的值：拿到它就能建出 admin 账号
    admin_registration_code: str = ""

    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 45.0
    # 一次工作流的总预算。前端另有 180 秒兜底，这条必须更短：先由后端自己收口，
    # 才能把 run 标成 failed；反过来是前端先断连、后端还在算，状态停在 running
    workflow_timeout_seconds: float = 150.0
    # 按运行类型分档：评估/调整计划是 collect→assess→plan→report 长链，多轮 LLM 调用，
    # 给足预算；咨询/打卡/查报告是单节点短链，几十秒就该结束，压短些能更早止损。
    # workflow_timeout_seconds 仍作为兜底默认，两档都未命中时用它。
    workflow_timeout_long: float = 150.0
    workflow_timeout_short: float = 60.0

    # keyword 走本地关键词检索，bge 走 BGE-M3 + Chroma
    embedding_backend: str = "keyword"
    bge_model_path: str = "BAAI/bge-m3"
    chroma_dir: str = "storage/chroma"
    knowledge_dir: str = "knowledge"

    storage_dir: str = "storage"
    upload_max_mb: int = 10
    emergency_phone: str = "120"
    graph_concurrency: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _reject_dev_secret_in_prod(self) -> "Settings":
        # 默认密钥是公开的，prod 下留着等于谁都能签出合法令牌
        if self.env == "prod" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("env=prod 时必须显式设置 JWT_SECRET")
        return self

    @property
    def upload_max_bytes(self) -> int:
        return self.upload_max_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
