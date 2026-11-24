"""Input validation for uploaded audio (size, emptiness, container signature)."""
from app.core.exceptions import KothaError

_SIGNATURES: list[tuple[bytes, int, str]] = [
    (b"\x1a\x45\xdf\xa3", 0, "webm/matroska"),
    (b"OggS", 0, "ogg"),
    (b"RIFF", 0, "wav"),
    (b"ID3", 0, "mp3"),
    (b"\xff\xfb", 0, "mp3"),
    (b"\xff\xf3", 0, "mp3"),
    (b"\xff\xf2", 0, "mp3"),
    (b"ftyp", 4, "mp4/m4a/3gp"),
    (b"fLaC", 0, "flac"),
    (b"#!AMR", 0, "amr"),
    (b"\xff\xf1", 0, "aac"),
    (b"\xff\xf9", 0, "aac"),
]
MIN_AUDIO_BYTES = 1000  # anything smaller cannot contain meaningful speech


def validate_audio(data: bytes, max_bytes: int) -> str:
    """Return detected container name or raise KothaError."""
    if not data:
        raise KothaError(400, "EMPTY_AUDIO", "No audio was received.")
    if len(data) < MIN_AUDIO_BYTES:
        raise KothaError(400, "AUDIO_TOO_SHORT", "The recording is too short to process.")
    if len(data) > max_bytes:
        raise KothaError(413, "AUDIO_TOO_LARGE", "The recording is too large.")
    for sig, offset, name in _SIGNATURES:
        if len(data) >= offset + len(sig) and data[offset : offset + len(sig)] == sig:
            return name
    raise KothaError(415, "UNSUPPORTED_AUDIO", "The file is not a supported audio format.")
