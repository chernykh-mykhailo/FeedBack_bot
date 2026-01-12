from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional, Any

class Settings(BaseSettings):
    BOT_TOKEN: str = Field(..., alias="BOT_TOKEN")
    ADMIN_GROUP_ID: Optional[int] = Field(0, alias="ADMIN_GROUP_ID")
    START_MESSAGE: str = "Привіт! Напиши своє питання або відгук. 😊"
    TOPIC_NAME_TEMPLATE: str = "#FIRST_NAME (#USER_ID)"
    ANONYMOUS_MODE: bool = False
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

config = Settings()

def update_config(key: str, value: Any):
    # This is a helper to update .env or local state if needed
    # For now, we'll use a simple global or DB storage for dynamic parts
    pass
