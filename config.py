from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    BOT_TOKEN: str = Field(..., alias="BOT_TOKEN")
    ADMIN_GROUP_ID: Optional[int] = Field(None, alias="ADMIN_GROUP_ID")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

config = Settings()
