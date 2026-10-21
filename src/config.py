from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    admin_chat_id: int
    manager_username: str = "stc_manager"
    database_url: str

    liqpay_public_key: str
    liqpay_private_key: str
    liqpay_sandbox: bool = True
    webhook_base_url: str

    public_offer_url: str = "https://cutt.ly/Wtwtl8P7"
    refund_policy_url: str = "https://cutt.ly/KR7c35q"

    google_sheet_id: str
    google_credentials_path: str = "google_credentials.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
