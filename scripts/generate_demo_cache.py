"""Generates cached demo pipeline outputs for all prepared scenarios.

Saves each scenario's pipeline state to demo_assets/cached_outputs/{scenario_id}.json
with timestamps, models, and provider metadata for offline/fallback execution.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from app.schemas.clinical import ClinicalExtraction
from app.services import demo_data, red_flag_engine
from app.services.glossary_service import load_glossary


def generate_cache():
    cache_dir = root_dir / "demo_assets" / "cached_outputs"
    cache_dir.mkdir(parents=True, exist_ok=True)

    scenarios = demo_data.list_scenarios()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    glossary = load_glossary()

    for sc in scenarios:
        sid = sc["id"]
        original = sc["original"]
        normalized = sc["normalized"]
        extraction_data = sc["extraction"]

        # Run deterministic glossary match
        glossary_matches = [
            m.model_dump() for m in glossary.match(original)
        ]

        # Run deterministic safety evaluation
        safety_eval = red_flag_engine.evaluate(
            session_id=f"demo_cache_{sid}",
            confirmed_text=normalized,
            original_transcript=original,
        ).model_dump()

        cache_payload = {
            "scenario_id": sid,
            "title": sc["title"],
            "purpose": sc["purpose"],
            "dialect_label": sc["dialect_label"],
            "timestamp": now_iso,
            "provider": "cached_demo_output",
            "model": "pre-saved-demo-fallback",
            "transcript": {
                "text": original,
                "source": "demo_sample",
            },
            "normalization": {
                "original": original,
                "normalized": normalized,
                "source": "demo_prepared",
                "glossary_matches": glossary_matches,
                "uncertain_spans": [],
                "warnings": [
                    "Demo mode: this normalization was pre-verified for this sample."
                ],
                "provider": "cached_demo_output",
            },
            "extraction": extraction_data,
            "safety": safety_eval,
        }

        out_file = cache_dir / f"{sid}.json"
        out_file.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Generated demo cache for {sid} -> {out_file}")


if __name__ == "__main__":
    generate_cache()
