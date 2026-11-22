"""Re-export speech-to-text adapters for backward compatibility."""
from app.services.speech_to_text import (
    HFInferenceSTT,
    LocalTransformersSTT,
    OpenAICompatSTT,
    SpeechToTextProvider as STTProvider,
    STTResult,
    get_stt,
    process_audio,
    stt_configured,
)

__all__ = [
    "STTResult",
    "STTProvider",
    "LocalTransformersSTT",
    "HFInferenceSTT",
    "OpenAICompatSTT",
    "stt_configured",
    "get_stt",
    "process_audio",
]
