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
    SLACK_APPROVER_USER_ID: str = "U0904E3AAR5"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    POLL_INTERVAL_MINUTES: int = 5

    model_config = {"env_file": ".env"}


settings = Settings()
