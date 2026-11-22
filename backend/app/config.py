"""Environment-based configuration. No secrets are hardcoded; see .env.example."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    # Limits and sessions
    max_audio_bytes: int = 10 * 1024 * 1024
    session_ttl_seconds: int = 1800
    provider_timeout_seconds: float = 60.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
