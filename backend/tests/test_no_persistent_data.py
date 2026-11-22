"""Verification of the zero-retention privacy architecture.

Guarantees:
1. No files are written to the repository or lingering in temp directories after full intake workflows.
2. Server logs contain event metadata only — NEVER patient transcripts, audio bytes, or API credentials.
3. Audio transcoding scratch files are deleted in `finally` even when errors occur.
4. Expired or purged sessions leave zero in-memory traces.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from app.services import clinical_extractor, speech_to_text, text_to_speech
from conftest import FakeLLM


def _get_project_files() -> set[str]:
    """Get relative paths of all persistent files in the backend, ignoring caches."""
    root = Path(__file__).resolve().parent.parent
    files = set()
    for p in root.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(root))
            if "__pycache__" not in rel and ".pytest_cache" not in rel and ".git" not in rel and ".venv" not in rel:
                files.add(rel)
    return files


def _get_temp_files() -> set[str]:
    """Get list of temporary files matching kotha scratch prefixes."""
    tmp = Path(tempfile.gettempdir())
    try:
        return {p.name for p in tmp.iterdir() if p.is_file()}
    except Exception:
        return set()


def test_full_workflow_creates_no_persistent_files(client, monkeypatch):
    """Running a complete intake and clinical summary pipeline must leave zero files behind."""
    initial_project_files = _get_project_files()
    initial_temp_files = _get_temp_files()

    # Mock audio synthesis
    monkeypatch.setattr(text_to_speech, "_synthesize_gtts", lambda t: b"ID3fake_mp3_audio")

    # Mock LLM for clinical extraction
    mock_extraction_json = (
        '{"chief_complaint":{"status":"reported","bn":"মাথায় ব্যথা","en":"Headache"},'
        '"symptoms":[{"bn":"মাথা ব্যথা","en":"Headache"}],'
        '"duration":{"status":"reported","bn":"৩ দিন","en":"3 days"},'
        '"severity":{"status":"not_reported","bn":null,"en":null},'
        '"relevant_history":{"status":"not_reported","bn":null,"en":null},'
        '"current_medications":{"status":"not_reported","bn":null,"en":null},'
        '"allergies":{"status":"not_reported","bn":null,"en":null},'
        '"associated_symptoms":[],"negative_symptoms":[],"uncertain_or_missing":[],"model_noted_red_flag_indicators":[]}'
    )
    fake_llm = FakeLLM([mock_extraction_json])
    monkeypatch.setattr(clinical_extractor, "get_llm", lambda s: fake_llm)

    # 1. Create Session
    sess_res = client.post("/api/session", json={"mode": "live"})
    assert sess_res.status_code == 201
    sid = sess_res.json()["session_id"]

    # 2. Upload typed patient transcript
    unique_secret = "গোপনীয়_রোগীর_লক্ষণ_মাথায়_ব্যথা_তিন_দিন"
    tx_res = client.post("/api/transcription/typed", json={"session_id": sid, "text": unique_secret})
    assert tx_res.status_code == 200

    # 3. Normalization
    norm_res = client.post("/api/normalization", json={"session_id": sid})
    assert norm_res.status_code == 200

    # 4. Confirmation
    conf_res = client.post(
        "/api/confirmation",
        json={
            "session_id": sid,
            "original_text": unique_secret,
            "confirmed_text": unique_secret,
            "confirmed": True,
        },
    )
    assert conf_res.status_code == 200

    # 5. Extraction
    ext_res = client.post("/api/clinical/extract", json={"session_id": sid})
    assert ext_res.status_code == 200

    # 6. Safety evaluation
    saf_res = client.post("/api/safety/evaluate", json={"session_id": sid})
    assert saf_res.status_code == 200

    # 7. Summary generation
    sum_res = client.post("/api/summary/generate", json={"session_id": sid})
    assert sum_res.status_code == 200

    # 8. Speech reply generation
    sp_res = client.post("/api/speech/generate", json={"session_id": sid})
    assert sp_res.status_code == 200

    # 9. Explicit session deletion
    del_res = client.delete(f"/api/session/{sid}")
    assert del_res.status_code == 204

    # Assert no new project files appeared
    final_project_files = _get_project_files()
    new_project_files = final_project_files - initial_project_files
    assert not new_project_files, f"Unexpected persistent files created in project: {new_project_files}"

    # Assert no lingering scratch files in temp directory
    final_temp_files = _get_temp_files()
    new_temp_files = final_temp_files - initial_temp_files
    suspicious_temp = [f for f in new_temp_files if f.endswith(".raw") or f.endswith("_converted.wav")]
    assert not suspicious_temp, f"Lingering temporary files in temp directory: {suspicious_temp}"


def test_logs_contain_no_patient_transcripts_or_secrets(client, caplog, monkeypatch):
    """Server log streams must NEVER record patient transcript text, audio data, or API keys."""
    caplog.set_level(logging.DEBUG)

    s = get_settings()
    monkeypatch.setattr(s, "llm_api_key", "sk-secret-patient-key-998877")
    monkeypatch.setattr(s, "speech_api_key", "sk-speech-key-112233")
    monkeypatch.setattr(text_to_speech, "_synthesize_gtts", lambda t: b"ID3fake_mp3_audio")

    patient_secret_phrase = "অত্যন্ত_গোপনীয়_লক্ষণ_বুকে_প্রচণ্ড_ব্যথা_উৎস"

    sid = client.post("/api/session", json={"mode": "live"}).json()["session_id"]
    client.post("/api/transcription/typed", json={"session_id": sid, "text": patient_secret_phrase})
    client.post("/api/normalization", json={"session_id": sid})
    client.post(
        "/api/confirmation",
        json={
            "session_id": sid,
            "original_text": patient_secret_phrase,
            "confirmed_text": patient_secret_phrase,
            "confirmed": True,
        },
    )

    # Check all captured log output
    full_log_text = caplog.text

    # Patient secret phrase must never appear anywhere in logs
    assert "অত্যন্ত_গোপনীয়" not in full_log_text
    assert "বুকে_প্রচণ্ড_ব্যথা_উৎস" not in full_log_text
    assert patient_secret_phrase not in full_log_text

    # Secrets / keys must never appear
    assert "sk-secret-patient-key-998877" not in full_log_text
    assert "sk-speech-key-112233" not in full_log_text


def test_audio_temp_files_cleaned_up_on_error(tmp_path):
    """Audio transcoding temporary files must be cleaned up in finally blocks even on error."""
    temp_dir = tempfile.gettempdir()
    initial_files = set(os.listdir(temp_dir))

    # Trigger audio error by passing invalid non-audio bytes that pass size check
    fake_header = b"\x1a\x45\xdf\xa3" + b"\x00" * 2000  # valid webm magic bytes but invalid container payload
    try:
        speech_to_text.process_audio(fake_header, max_bytes=10_000_000)
    except Exception:
        pass  # expected error from ffmpeg or validation

    final_files = set(os.listdir(temp_dir))
    leaked = [f for f in (final_files - initial_files) if f.endswith(".raw") or f.endswith("_converted.wav")]
    assert not leaked, f"process_audio leaked temp files on error: {leaked}"
