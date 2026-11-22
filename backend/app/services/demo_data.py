"""Prepared demo scenarios (synthetic, fictional). Clearly NOT live model output."""
from __future__ import annotations

import json
from functools import lru_cache

from app.core.exceptions import KothaError
from app.services.glossary_service import DATA_DIR


@lru_cache
def _load() -> dict:
    return json.loads((DATA_DIR / "demo" / "scenarios.json").read_text(encoding="utf-8"))


def notice() -> str:
    return _load()["notice"]


def list_scenarios() -> list[dict]:
    return _load()["scenarios"]


def get_scenario(scenario_id: str) -> dict:
    for s in _load()["scenarios"]:
        if s["id"] == scenario_id:
            return s
    raise KothaError(404, "UNKNOWN_SCENARIO", "Unknown demo scenario.")
