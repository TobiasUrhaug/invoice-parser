from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str
    model_dir: Path = Path("/app/models")
    model_repo_id: str = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    model_filename: str = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    min_text_chars_per_page: int = 50
    max_file_size_mb: int = 10
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
