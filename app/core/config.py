from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "dev"
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_USER: str = "dev_user"
    DB_PASSWORD: str = "dev_password"
    DB_NAME: str = "dev_db"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_APPROVAL_CHANNEL: str = "#mailki-approvals"

    model_config = {"env_file": ".env"}


settings = Settings()
