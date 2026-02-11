from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Set

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    SEARCH_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    SEARCH_URLS: List[str]


settings = Settings()
