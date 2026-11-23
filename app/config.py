from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IncuBrix"
    environment: str = "development"
    simulation_mode: bool = True
    connector_mode: str = "simulation"  # simulation | mock | local | live
    database_url: str = "sqlite+pysqlite:///./incubrix.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend_url: str = "redis://localhost:6379/1"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "incubrix"
    minio_secure: bool = False
    correlation_header: str = "X-Correlation-Id"
    log_level: str = "INFO"
    job_backend: str = "inline"  # inline | celery
    output_backend: str = "local"  # local | s3
    output_dir: str = "outputs"
    ai_provider: str = "mock"  # mock | gemini | openai
    ai_model: str = "mock-model"
    ai_api_key: str = ""
    disabled_connectors: list[str] = []
    recert_interval_days: int = 30
    recert_margin_days: int = 5
    demo_access_token: str | None = None
    rate_limit_per_minute: int = 120
    callback_secret: str = "incubrix-" + "callback-secret"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
