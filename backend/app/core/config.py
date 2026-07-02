from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    whisper_model: str = "medium"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    gemini_api_key: str = ""
    gemini_api_key_fallback: str = ""

    temp_audio_dir: str = "./temp_audio"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    log_level: str = "INFO"
    max_upload_bytes: int = 524_288_000
    max_audio_duration_seconds: int = 2700

    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""
    web_panel_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"

    temp_audio_dir: str = "./temp_audio"
    log_level: str = "INFO"


settings = Settings()
