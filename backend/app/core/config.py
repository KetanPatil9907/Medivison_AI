from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # App
    app_name: str = "MediVision AI"
    app_env: str = "development"
    app_debug: bool = True
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "medivision"
    postgres_user: str = "medivision"
    postgres_password: str = "medivision_dev_password"
    database_url: str = "postgresql+psycopg2://medivision:medivision_dev_password@localhost:5432/medivision"

    # Security
    secret_key: str = "change_this_to_a_long_random_hex_string"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"
    password_min_length: int = 8
    jwt_issuer: str = "medivision-ai"
    jwt_audience: str = "medivision-ai-client"

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Rate limiting
    rate_limit_general: str = "60/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_ai: str = "20/minute"
    rate_limit_upload: str = "6/minute"

    # Storage
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "medivision"
    s3_secret_key: str = "medivision_storage_secret"
    s3_bucket: str = "medivision-storage"
    s3_public_base_url: str = ""
    storage_driver: str = "s3"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # AI / LLM
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: int = 30

    # AI model paths
    vision_model_dir: str = "../ai/computer_vision"
    symptom_model_path: str = "../ai/symptom_model"
    symptom_rule_based_fallback: bool = True
    risk_model_path: str = "../ai/risk_models"
    ai_fallback_mode: bool = True

    # Default admin bootstrap (used by scripts/seed_admin.py)
    admin_email: str = "admin@medivision.local"
    admin_full_name: str = "MediVision Administrator"
    admin_initial_password: str = "Admin@12345"

    # Notifications
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "MediVision AI <no-reply@medivision.example>"
    notification_email_enabled: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()