from pydantic import BaseSettings


class Settings(BaseSettings):
    ENV: str = "development"
    GOOGLE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    INDEXNOW_KEY: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
