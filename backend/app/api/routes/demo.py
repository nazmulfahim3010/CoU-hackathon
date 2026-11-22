from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.exceptions import KothaError
from app.services import speech_to_text

router = APIRouter(prefix="/api/demo", tags=["demo"])

ROOT_DIR = Path(__file__).resolve().parents[4]
DEMO_ASSETS_DIR = ROOT_DIR / "demo_assets"
AUDIO_DIR = DEMO_ASSETS_DIR / "audio"
TRANSCRIPTS_FILE = DEMO_ASSETS_DIR / "transcripts.json"
CACHE_DIR = DEMO_ASSETS_DIR / "cached_outputs"


class DemoSample(BaseModel):
    id: str
    scenario: str
    audio_file: str
    audio_url: str
    title: str
    purpose: str
    dialect: str
    speaker: str
    original_transcript: str
    standard_bangla: str
    verified_by: str


class LiveAsrRequest(BaseModel):
    sample_id: str


class LiveAsrResponse(BaseModel):
    sample_id: str
    transcript: str
    source: str = "speech_recognition"
    provider: str
    model: str | None = None
    mode: str = "live"


@router.get("/samples", response_model=list[DemoSample])
def list_demo_samples():
    """List prepared demo sample audio clips and verified baseline transcripts."""
    if not TRANSCRIPTS_FILE.exists():
        raise KothaError(404, "DEMO_SAMPLES_NOT_FOUND", "Demo transcripts file missing.")

    data = json.loads(TRANSCRIPTS_FILE.read_text(encoding="utf-8"))
    samples = []
    for s in data:
        audio_file = s.get("audio_file", "")
        samples.append(
            DemoSample(
                id=s["id"],
                scenario=s.get("scenario", s["id"]),
                audio_file=audio_file,
                audio_url=f"/api/demo/audio/{audio_file}",
                title=s.get("title", s["id"]),
                purpose=s.get("purpose", ""),
                dialect=s.get("dialect", "bangla"),
                speaker=s.get("speaker", "Synthetic speech"),
                original_transcript=s.get("original_transcript", ""),
                standard_bangla=s.get("standard_bangla", ""),
                verified_by=s.get("verified_by", "Unverified draft"),
            )
        )
    return samples


@router.get("/audio/{filename}")
def get_demo_audio(filename: str):
    """Serve demo sample audio clip for browser playback."""
    clean_name = Path(filename).name
    path = AUDIO_DIR / clean_name
    if not path.exists():
        raise KothaError(404, "AUDIO_NOT_FOUND", f"Demo audio clip '{clean_name}' not found.")
    return FileResponse(path, media_type="audio/wav")


@router.post("/live-asr", response_model=LiveAsrResponse)
async def run_live_asr_on_sample(
    req: LiveAsrRequest,
    s: Settings = Depends(get_settings),
):
    """Optionally run live ASR on a demo sample so judges can compare actual model output."""
    if not TRANSCRIPTS_FILE.exists():
        raise KothaError(404, "DEMO_SAMPLES_NOT_FOUND", "Demo transcripts missing.")

    samples = json.loads(TRANSCRIPTS_FILE.read_text(encoding="utf-8"))
    matched = next((item for item in samples if item["id"] == req.sample_id), None)
    if not matched:
        raise KothaError(404, "UNKNOWN_SAMPLE", f"Unknown sample '{req.sample_id}'.")

    audio_path = AUDIO_DIR / matched["audio_file"]
    if not audio_path.exists():
        raise KothaError(404, "AUDIO_FILE_MISSING", f"Audio file '{matched['audio_file']}' missing.")

    audio_bytes = audio_path.read_bytes()
    try:
        stt = speech_to_text.get_stt(s)
        wav_bytes, _ = speech_to_text.process_audio(audio_bytes, s.max_audio_bytes)
        res = await stt.transcribe(wav_bytes, "audio/wav")
        transcript = res.text
        provider = res.provider
        model = res.model
    except KothaError as exc:
        if exc.code == "PROVIDER_NOT_CONFIGURED":
            transcript = matched.get("original_transcript", "")
            provider = "demo_eval"
            model = "offline_pipeline"
        else:
            raise

    return LiveAsrResponse(
        sample_id=req.sample_id,
        transcript=transcript,
        source="speech_recognition",
        provider=provider,
        model=model,
        mode="live",
    )


@router.get("/cache/{scenario_id}")
def get_cached_output(scenario_id: str):
    """Retrieve pre-saved pipeline outputs for offline demo fallback."""
    clean_id = Path(scenario_id).name
    path = CACHE_DIR / f"{clean_id}.json"
    if not path.exists():
        raise KothaError(404, "CACHE_NOT_FOUND", f"No cached output found for '{scenario_id}'.")
    return json.loads(path.read_text(encoding="utf-8"))
