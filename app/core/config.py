from pydantic import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "dev"
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_USER: str = "dev_user"
    DB_PASSWORD: str = "dev_password"
    DB_NAME: str = "dev_db"

    class Config:
        env_file = ".env"


settings = Settings()
