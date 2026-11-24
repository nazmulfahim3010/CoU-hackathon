"""Environment-based configuration. No secrets are hardcoded; see .env.example."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application mode: demo | live
    app_mode: str = "demo"

    # Session configuration
    session_ttl_minutes: int = 30
    session_ttl_seconds: int = 1800

    # Speech-to-text. provider: none | hf_inference | openai_compatible
    speech_provider: str = "none"
    speech_model: str = "bangla-speech-processing/BanglaASR"
    speech_api_key: str = ""
    speech_base_url: str = ""  # openai_compatible: e.g. https://api.openai.com/v1

    # LLM. provider: none | anthropic | openai_compatible
    llm_provider: str = "none"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""

    # Text-to-speech. provider: none | gtts
    tts_provider: str = "gtts"
    tts_api_key: str = ""

    # Sharing a summary card with a health worker (in-memory only, consent required)
    share_ttl_minutes: int = 30
    # e.g. http://192.168.1.20:8080 so share links/QR codes work from a phone on the same Wi-Fi
    public_base_url: str = ""

    # Limits and uploads
    max_audio_seconds: int = 90
    max_upload_mb: int = 10
    max_audio_bytes: int = 10 * 1024 * 1024
    provider_timeout_seconds: float = 60.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def effective_ttl_seconds(self) -> int:
        return self.session_ttl_minutes * 60

    @property
    def effective_max_audio_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
