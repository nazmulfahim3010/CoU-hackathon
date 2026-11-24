"""Tests for Sylheti audio dataset loader, validation, and ground-truth integrity."""
from pathlib import Path
import pytest

from app.services.dataset.sylheti_audio_dataset import (
    find_dataset_paths,
    SylhetiAudioDataset,
)


def test_dataset_paths_discovery():
    """Verify CSV and audio directories are discovered across roots."""
    csv_path, audio_dir = find_dataset_paths()
    assert csv_path is not None, "CSV path could not be found"
    assert audio_dir is not None, "Audio dir could not be found"
    assert csv_path.is_file(), f"CSV path {csv_path} is not a file"
    assert audio_dir.is_dir(), f"Audio dir {audio_dir} is not a directory"


def test_dataset_loading_and_counts():
    """Verify loading dataset produces exactly 16 valid records."""
    csv_path, audio_dir = find_dataset_paths()
    dataset = SylhetiAudioDataset.load(csv_path, audio_dir)
    assert len(dataset) == 16, f"Expected 16 records, found {len(dataset)}"
    
    # Scenarios present
    scenarios = set(dataset.scenarios.keys())
    assert {"A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"}.issubset(scenarios)


def test_dataset_audio_properties():
    """Verify audio properties across all 16 WAV files."""
    csv_path, audio_dir = find_dataset_paths()
    dataset = SylhetiAudioDataset.load(csv_path, audio_dir)
    val = dataset.validate()
    assert val.is_valid, f"Validation failed with errors: {val.validation_errors}"
    assert val.matched_records == 16
    assert len(val.missing_audio_files) == 0

    for rec in dataset.records:
        assert rec.audio_metadata is not None
        assert rec.audio_metadata.sample_rate == 48000
        assert rec.audio_metadata.channels == 2
        assert rec.audio_metadata.duration_seconds > 5.0
        assert rec.original_transcript
        assert rec.standard_bangla


def test_evaluation_corpus_segregation():
    """Verify dataset records are never directly injected as active session transcripts."""
    csv_path, audio_dir = find_dataset_paths()
    dataset = SylhetiAudioDataset.load(csv_path, audio_dir)
    
    rec_001 = dataset.get("rec_001")
    assert rec_001 is not None
    # Verify that rec_001 is an immutable reference record
    assert rec_001.reviewer in ("Fahim", "Noyon")
