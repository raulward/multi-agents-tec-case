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
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION: str = "financial_docs"
    DATA_DIR: str = "./data/processed"
    MODEL_NAME: str = "gpt-4o-mini"


settings = Settings()
