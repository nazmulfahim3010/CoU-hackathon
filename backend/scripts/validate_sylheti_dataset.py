"""Dataset validation script for Sylheti audio corpus.

Inspects all 16 recordings and metadata log, generating reports/sylheti_dataset_validation.json.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.dataset import SylhetiAudioDataset


def run_validation():
    dataset = SylhetiAudioDataset()
    print(f"Loading Sylheti Audio Dataset from: {dataset.csv_path} and {dataset.audio_dir}")
    result = dataset.load_and_validate()

    reports_dir = Path(__file__).resolve().parent.parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "sylheti_dataset_validation.json"

    # Prepare JSON report
    report_data = {
        "dataset_name": "Sylheti Audio Recording & CSV Corpus",
        "csv_path": str(dataset.csv_path) if dataset.csv_path else None,
        "audio_dir": str(dataset.audio_dir) if dataset.audio_dir else None,
        "is_valid": result.is_valid,
        "total_csv_records": result.total_csv_records,
        "total_audio_files": result.total_audio_files,
        "matched_records": result.matched_records,
        "missing_audio_files": result.missing_audio_files,
        "missing_transcript_records": result.missing_transcript_records,
        "duplicate_ids": result.duplicate_ids,
        "duplicate_filenames": result.duplicate_filenames,
        "duration_mismatches": result.duration_mismatches,
        "validation_errors": result.validation_errors,
        "records_summary": [
            {
                "id": r.recording_id,
                "file": r.audio_filename,
                "scenario": r.scenario_card,
                "duration_csv": r.duration_seconds,
                "duration_measured": r.audio_properties.measured_duration_sec if r.audio_properties else None,
                "sample_rate": r.audio_properties.sample_rate_hz if r.audio_properties else None,
                "channels": r.audio_properties.channels if r.audio_properties else None,
                "transcript_length": len(r.original_sylheti_transcript),
                "reviewer": r.reviewer,
            }
            for r in result.records
        ],
    }

    report_file.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dataset validation report successfully written to: {report_file}")
    print(f"Total matched records: {result.matched_records}/{result.total_csv_records}")
    print(f"Validation status: {'PASSED' if result.is_valid else 'FAILED'}")


if __name__ == "__main__":
    run_validation()
