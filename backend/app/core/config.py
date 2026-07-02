from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    whisper_model: str = "medium"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"

    temp_audio_dir: str = "./temp_audio"
    log_level: str = "INFO"


settings = Settings()
