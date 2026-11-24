#!/usr/bin/env python3
"""Evaluate Kotha's real ASR and normalization on the Sylheti audio corpus.

Uses the SAME code path as the live app: process_audio (ffmpeg) -> get_stt(settings).transcribe -> normalize().
The reference transcripts are used ONLY for scoring, never as transcription output.

  ASR:            recognised text  vs  original_sylheti_transcript   (CER / WER / exact match)
  Normalization:  normalized text  vs  reference_standard_bangla     (diffs + semantic checks)

Audio is sent to the configured third-party speech provider, so this refuses to run unless you pass
--confirm-third-party-processing (confirm consent and permitted uses first). Use --skip-asr to evaluate
normalization of the reference transcripts only (no audio leaves the machine).

Run inside Docker (ffmpeg is required):
  docker run --rm --env-file backend/.env -v <repo>/data:/app/data:ro -v <repo>/reports:/app/reports \
      kotha-backend python scripts/evaluate_sylheti_dataset.py --confirm-third-party-processing

Public reports contain metrics and recording ids only. Texts go to reports/*.local.json (git-ignored).
Reports never contain audio, file paths, speaker names, API keys or provider response bodies.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.core.exceptions import KothaError  # noqa: E402
from app.core.security import validate_audio  # noqa: E402
from app.services.dataset import evaluation as ev  # noqa: E402
from app.services.dataset.sylheti_audio_dataset import REPO_ROOT, dataset_dir, load_sylheti_audio_dataset  # noqa: E402
from app.services.dialect_normalizer import normalize  # noqa: E402
from app.services.glossary_service import clean_text, load_glossary  # noqa: E402
from app.services.llm_provider import llm_configured  # noqa: E402
from app.services.speech_to_text import effective_speech_model, get_stt, process_audio, stt_configured  # noqa: E402

RETRYABLE = {"ASR_PROVIDER_UNAVAILABLE", "ASR_TIMEOUT"}


async def transcribe_one(settings, record) -> tuple[str | None, float, str | None]:
    """Exactly the app's path. Returns (text, seconds, error_code)."""
    raw = record.audio_path.read_bytes()
    t0 = time.perf_counter()
    try:
        validate_audio(raw, settings.max_audio_bytes)
        wav, _dur = process_audio(raw, settings.max_audio_bytes)
        stt = get_stt(settings)
        for attempt in (1, 2):
            try:
                result = await stt.transcribe(wav, "audio/wav")
                return clean_text(result.text), time.perf_counter() - t0, None
            except KothaError as exc:
                if attempt == 1 and exc.code in RETRYABLE:
                    await asyncio.sleep(2.0)
                    continue
                raise
    except KothaError as exc:
        return None, time.perf_counter() - t0, exc.code
    return None, time.perf_counter() - t0, "UNKNOWN"


async def run(args) -> int:
    settings = get_settings()
    ds = load_sylheti_audio_dataset(dataset_dir() if args.dataset_dir is None else args.dataset_dir)
    if not ds.records:
        print("No recordings loaded:", [i.code for i in ds.issues][:5])
        return 2
    records = [r for r in ds.records if not args.records or r.recording_id in args.records]
    if args.limit:
        records = records[: args.limit]
    glossary = load_glossary()
    use_llm = llm_configured(settings) and not args.no_llm
    skip_asr = args.skip_asr
    if not skip_asr and not stt_configured(settings):
        print("Speech provider is not configured (SPEECH_PROVIDER / SPEECH_API_KEY). Use --skip-asr or configure it.")
        return 2

    rows: list[dict[str, Any]] = []
    local: list[dict[str, Any]] = []
    transcripts: dict[str, str] = {}
    for rec in records:
        row: dict[str, Any] = {
            "recording_id": rec.recording_id, "scenario_card": rec.scenario_card,
            "anonymized_speaker_id": rec.anonymized_speaker_id, "duration_seconds": rec.audio.duration_seconds and round(rec.audio.duration_seconds, 2),
        }
        loc: dict[str, Any] = {"recording_id": rec.recording_id, "reference_original": rec.original_sylheti_transcript, "reference_standard": rec.reference_standard_bangla}

        # --- Test 5: normalize the REFERENCE Sylheti transcript, compare with the standard Bangla reference
        n_ref = await normalize(rec.original_sylheti_transcript, settings, use_llm, glossary)
        row["normalization_of_reference"] = {
            **ev.semantic_checks(rec.original_sylheti_transcript, n_ref.normalized, rec.reference_standard_bangla, glossary),
            "normalization_status": n_ref.normalization_status,
            "glossary_ids_applied": [e.glossary_id for e in n_ref.glossary_evidence if e.applied],
            "warnings": len(n_ref.warnings),
        }
        loc["normalized_from_reference"] = n_ref.normalized

        # --- Tests 3-4: real speech recognition on the real audio bytes
        if skip_asr:
            row["status"] = "skipped_asr"
        else:
            text, secs, err = await transcribe_one(settings, rec)
            row["processing_seconds"] = round(secs, 2)
            if err or text is None:
                row["status"], row["error_code"] = "failed", err
            else:
                row["status"] = "ok"
                row["asr"] = ev.asr_metrics(rec.original_sylheti_transcript, text)
                transcripts[rec.recording_id] = text
                loc["asr_transcript"] = text
                if text.strip():
                    n_asr = await normalize(text, settings, use_llm, glossary)
                    row["normalization_of_asr"] = {
                        **ev.semantic_checks(text, n_asr.normalized, rec.reference_standard_bangla, glossary),
                        "normalization_status": n_asr.normalization_status,
                    }
                    loc["normalized_from_asr"] = n_asr.normalized
            await asyncio.sleep(args.delay)
        rows.append(row)
        local.append(loc)
        print(f"{rec.recording_id} {rec.scenario_card}: "
              + (f"CER={row['asr']['cer']:.2f} WER={row['asr']['wer']:.2f}" if row.get("asr") else row["status"] + (f" {row.get('error_code','')}" if row.get("error_code") else ""))
              + f" | norm WER vs ref={row['normalization_of_reference']['wer_vs_reference']:.2f}"
              + (" REVIEW" if row["normalization_of_reference"]["requires_human_review"] else ""))

    refs = {r.recording_id: r.original_sylheti_transcript for r in ds.records}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta = {
        "generated_at": now,
        "speech_provider": settings.speech_provider, "speech_model": effective_speech_model(settings),
        "speech_credentials_configured": stt_configured(settings),
        "llm_used_for_normalization": use_llm,
        "llm_provider": settings.llm_provider if use_llm else None,
        "recordings_evaluated": len(records), "asr_run": not skip_asr,
        "third_party_audio_processing_confirmed": bool(args.confirm_third_party_processing) and not skip_asr,
    }
    asr_rows = [r for r in rows if r["status"] != "skipped_asr"]
    asr_report = {
        **meta,
        "aggregate": ev.asr_rollup(asr_rows) if asr_rows else None,
        "by_scenario": ev.by_scenario(rows) if asr_rows else None,
        "possible_label_mismatches": ev.possible_label_mismatches(transcripts, refs) if transcripts else [],
        "recordings": [{k: v for k, v in r.items() if k not in ("normalization_of_reference", "normalization_of_asr")} for r in rows],
        "limitations": [
            "Single speaker, 16 short recordings: not representative of Sylheti regional variation.",
            "Reference transcripts are team-authored; independent adjudication is not established.",
            "Metrics are descriptive, not a claim of clinical accuracy.",
        ],
    }
    norm_ref = [r["normalization_of_reference"] for r in rows]
    norm_asr = [r["normalization_of_asr"] for r in rows if "normalization_of_asr" in r]
    norm_report = {
        **meta,
        "reference_transcripts_normalized": ev.normalization_rollup(norm_ref),
        "asr_transcripts_normalized": ev.normalization_rollup(norm_asr) if norm_asr else None,
        "per_recording_reference": [{"recording_id": r["recording_id"], "scenario_card": r["scenario_card"], **r["normalization_of_reference"]} for r in rows],
        "human_review_note": "requires_human_review is an automated screen. A human must judge clinical meaning for every flagged pair.",
    }

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "sylheti_asr_evaluation.json").write_text(json.dumps(asr_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "sylheti_normalization_evaluation.json").write_text(json.dumps(norm_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "sylheti_asr_evaluation.md").write_text(render_markdown(asr_report, norm_report), encoding="utf-8")
    (out / "sylheti_evaluation.local.json").write_text(json.dumps(local, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # git-ignored: contains texts
    agg = asr_report["aggregate"]
    if agg:
        print(f"\nASR: ok {agg['successful_transcriptions']}/{agg['recordings']} | mean CER {agg['mean_cer']} | mean WER {agg['mean_wer']} | exact {agg['exact_match_rate']}")
    print("Normalization(reference):", norm_report["reference_transcripts_normalized"])
    print("wrote reports to", out)
    return 0


def render_markdown(a: dict[str, Any], n: dict[str, Any]) -> str:
    L = ["# Sylheti ASR and normalization evaluation", "",
         f"Generated {a['generated_at']}. Speech: `{a['speech_provider']}` / `{a['speech_model']}` "
         f"(credentials configured: {a['speech_credentials_configured']}). Normalization LLM used: {a['llm_used_for_normalization']}.", ""]
    agg = a["aggregate"]
    if agg:
        L += ["## ASR (scored against the original Sylheti transcript)", "",
              "| Metric | Value |", "|---|---|",
              *[f"| {k} | {v} |" for k, v in agg.items()], ""]
        L += ["### By scenario card", "", "| Card | n | ok | failed | mean CER | mean WER |", "|---|---|---|---|---|---|"]
        for card, s in (a["by_scenario"] or {}).items():
            L.append(f"| {card} | {s['recordings']} | {s['successful_transcriptions']} | {s['failed_transcriptions']} | {s['mean_cer']} | {s['mean_wer']} |")
        L.append("")
        if a["possible_label_mismatches"]:
            L += ["### Possible audio/transcript label mismatches (diagnostic; dataset not altered)", ""]
            L += [f"- `{m['recording_id']}` recognised text is closer to `{m['closer_to']}`'s reference (CER {m['own_cer']} vs {m['other_cer']})" for m in a["possible_label_mismatches"]]
            L.append("")
    L += ["## Normalization of the reference Sylheti transcripts (scored against standard Bangla)", "", "| Metric | Value |", "|---|---|",
          *[f"| {k} | {v} |" for k, v in n["reference_transcripts_normalized"].items()], ""]
    L += ["## Limitations", "", *[f"- {x}" for x in a["limitations"]], "", f"_{n['human_review_note']}_", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirm-third-party-processing", action="store_true",
                    help="I confirm consent covers sending these recordings to the configured speech provider")
    ap.add_argument("--skip-asr", action="store_true", help="evaluate normalization only; no audio is sent anywhere")
    ap.add_argument("--no-llm", action="store_true", help="force glossary-only normalization")
    ap.add_argument("--records", type=lambda s: set(s.split(",")), default=None, help="comma-separated recording ids")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between provider calls")
    ap.add_argument("--dataset-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "reports")
    args = ap.parse_args()
    if not args.skip_asr and not args.confirm_third_party_processing:
        print("Refusing to run: this sends the recordings to the configured third-party speech provider.\n"
              "Confirm consent and permitted uses, then pass --confirm-third-party-processing (or use --skip-asr).")
        return 2
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
