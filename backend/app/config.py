from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "FRAME Boost API"
    SECRET_KEY: str = "dev_secret_change_me"
    ADMIN_EMAIL: str = "admin@frameboost.local"
    ADMIN_PASSWORD: str = "admin123"
    DATABASE_URL: str = "sqlite:///./frameboost.sqlite3"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    PUBLIC_APP_URL: str = "http://127.0.0.1:8000"

    class Config:
        env_file = ".env"


settings = Settings()
