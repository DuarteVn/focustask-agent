from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Whisper
    whisper_model: str = "medium"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # Gemini
    gemini_api_key: str = ""
    gemini_api_key_fallback: str = ""

    # App
    temp_audio_dir: str = "./temp_audio"
    log_level: str = "INFO"
    max_upload_bytes: int = 524288000
    max_audio_duration_seconds: int = 2700

    # Database
    database_url: str = ""

    # Telegram
    telegram_bot_token: str = ""
    web_panel_base_url: str = "http://localhost:8000"


settings = Settings()
