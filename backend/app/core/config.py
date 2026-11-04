from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AlwaysHealthy"
    env: str = "dev"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://alwayshealthy:alwayshealthy@localhost:5432/alwayshealthy"
    db_echo: bool = False

    # memory 用于本地开发与测试，postgres 用于演示部署
    checkpointer: str = "memory"

    jwt_secret: str = "dev-secret-change-before-demo"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 45.0

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

    @property
    def upload_max_bytes(self) -> int:
        return self.upload_max_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
