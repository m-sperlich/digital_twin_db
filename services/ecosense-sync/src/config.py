from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Aquarius Settings
    AQUARIUS_HOSTNAME: str
    AQUARIUS_USERNAME: str
    AQUARIUS_PASSWORD: str

    # Database Settings
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    # Sync Settings
    SYNC_INTERVAL_MINUTES: int = 60
    DEFAULT_DAYS_BACK: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
