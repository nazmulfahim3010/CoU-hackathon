#!/usr/bin/env python3
"""Validate the Sylheti audio corpus and glossary CSV and write reports/sylheti_dataset_validation.json.

Usage (from backend/):  python scripts/validate_sylheti_dataset.py [--dataset-dir DIR] [--glossary-csv FILE] [--strict]

The report contains counts, ids and issue codes only: no audio, no transcripts, no file paths, no speaker names.
Exit code is 0 unless --strict is given and errors were found.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.services.dataset.glossary_csv import compare_with_runtime, glossary_csv_path, load_glossary_csv  # noqa: E402
from app.services.dataset.sylheti_audio_dataset import REPO_ROOT, dataset_dir, load_sylheti_audio_dataset  # noqa: E402
from app.services.glossary_service import DATA_DIR  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", type=Path, default=None)
    ap.add_argument("--glossary-csv", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "reports" / "sylheti_dataset_validation.json")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any error is found")
    args = ap.parse_args()

    ds = load_sylheti_audio_dataset(args.dataset_dir or dataset_dir())
    g = load_glossary_csv(args.glossary_csv or glossary_csv_path())
    runtime = json.loads((DATA_DIR / "dialects" / "sylheti.json").read_text(encoding="utf-8"))["entries"]
    drift = compare_with_runtime(g.entries, runtime) if g.entries else []

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "audio_dataset": {
            "summary": ds.summary(),
            "recordings": [r.to_public_dict() for r in ds.records],
            "issues": [i.to_dict() for i in ds.issues],
            "notes": [
                "Consent is recorded as a yes/no CSV flag only. Consent documentation and permitted uses (including "
                "third-party AI processing) are NOT established by this data.",
                "Single speaker; reviewer names exist but independent adjudication records do not.",
            ],
        },
        "glossary": {
            "summary": g.summary(),
            "issues": [i.to_dict() for i in g.issues],
            "runtime_drift_issues": [i.to_dict() for i in drift],
            "runtime_matches_csv": not drift,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    s, gs = ds.summary(), g.summary()
    print(f"audio: {s['matched_recordings']}/{s['transcript_records']} matched, {s['audio_files_found']} files, "
          f"containers={s['containers']}, errors={s['errors']}, warnings={s['warnings']}")
    print(f"glossary: {gs['entries_loaded']} entries, errors={gs['errors']}, warnings={gs['warnings']}, runtime_matches_csv={not drift}")
    for i in ds.issues + g.issues + drift:
        if i.severity == "error":
            print(f"  ERROR {i.code} {i.recording_id or ''}: {i.message}")
    print(f"wrote {args.out}")
    return 1 if args.strict and (ds.errors or g.errors or drift) else 0


if __name__ == "__main__":
    raise SystemExit(main())
