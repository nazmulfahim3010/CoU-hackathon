import asyncio

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.exceptions import KothaError
from app.schemas.clinical import BilingualField, ClinicalExtraction
from app.services import clinical_extractor
from conftest import FakeLLM, demo_confirmed, valid_extraction_json


def test_schema_accepts_valid():
    assert ClinicalExtraction.model_validate_json(valid_extraction_json()).duration.status == "reported"


def test_not_reported_must_not_carry_value():
    with pytest.raises(ValidationError):
        BilingualField(status="not_reported", en="no fever")


def test_reported_must_carry_value():
    with pytest.raises(ValidationError):
        BilingualField(status="reported")


def test_unknown_status_rejected():
    with pytest.raises(ValidationError):
        BilingualField(status="absent", en="x")


def test_missing_required_field_rejected():
    import json
    d = json.loads(valid_extraction_json())
    del d["duration"]
    with pytest.raises(ValidationError):
        ClinicalExtraction.model_validate(d)


def test_extractor_retries_then_succeeds(monkeypatch):
    llm = FakeLLM(["garbage", '{"chief_complaint": 1}', valid_extraction_json()])
    monkeypatch.setattr(clinical_extractor, "get_llm", lambda s: llm)
    out = asyncio.run(clinical_extractor.extract("জ্বর", Settings()))
    assert llm.calls == 3 and out.chief_complaint.en == "Fever"


def test_extractor_gives_up_with_controlled_error(monkeypatch):
    llm = FakeLLM(["garbage"])
    monkeypatch.setattr(clinical_extractor, "get_llm", lambda s: llm)
    with pytest.raises(KothaError) as e:
        asyncio.run(clinical_extractor.extract("জ্বর", Settings()))
    assert e.value.status_code == 502 and llm.calls == clinical_extractor.MAX_ATTEMPTS


def test_missing_info_stays_not_reported_in_demo_extraction(client):
    sid = demo_confirmed(client, "C_uncertain")
    ext = client.post("/api/clinical/extract", json={"session_id": sid}).json()["extraction"]
    assert ext["severity"]["status"] == "not_reported" and ext["severity"]["en"] is None
    assert ext["duration"]["status"] == "uncertain"
    assert ext["negative_symptoms"] == []  # unknown fever is NOT recorded as 'no fever'
    assert ext["uncertain_or_missing"]


def test_live_extraction_without_llm_is_503(client, monkeypatch):
    from conftest import FakeSTT, WEBM
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FakeSTT("জ্বর আছে"))
    sid = client.post("/api/transcription", files={"audio": ("a.webm", WEBM, "audio/webm")}).json()["session_id"]
    n = client.post("/api/normalization", json={"session_id": sid}).json()
    client.post("/api/confirmation", json={"session_id": sid, "original_text": n["original"],
                                           "confirmed_text": n["normalized"], "confirmed": True})
    r = client.post("/api/clinical/extract", json={"session_id": sid})
    assert r.status_code == 503 and r.json()["error"]["code"] == "PROVIDER_NOT_CONFIGURED"
