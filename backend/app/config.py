from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    sqlite_path: str = "margin_iq.db"
    anthropic_api_key: str = ""
    environment: str = "development"
    default_reconciliation_tolerance_pct: float = 2.0
    seed_demo: bool = False
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
