from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "margin_iq"
    anthropic_api_key: str = ""
    environment: str = "development"
    default_reconciliation_tolerance_pct: float = 2.0

    class Config:
        env_file = ".env"


settings = Settings()
