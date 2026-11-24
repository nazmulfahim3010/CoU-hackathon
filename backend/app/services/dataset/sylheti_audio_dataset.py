"""Sylheti Audio Dataset Loader and Audio Quality Inspector.

Loads and validates the Sylheti speech evaluation corpus (16 recordings + metadata log).
Segregated strictly from live patient requests.
"""
from __future__ import annotations

import csv
import os
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AudioMetadata:
    encoding: str
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    frame_count: int
    measured_duration_sec: float
    file_size_bytes: int

    @property
    def sample_rate(self) -> int:
        return self.sample_rate_hz

    @property
    def duration_seconds(self) -> float:
        return self.measured_duration_sec


@dataclass
class SylhetiRecordingRecord:
    recording_id: str
    audio_filename: str
    audio_path: str
    dialect: str
    scenario_card: str
    anonymized_speaker_id: str
    duration_seconds: float
    original_sylheti_transcript: str
    reference_standard_bangla: str
    english_translation: str
    reviewer: str
    consent_status: str
    audio_properties: AudioMetadata | None = None

    @property
    def id(self) -> str:
        return self.recording_id

    @property
    def original_transcript(self) -> str:
        return self.original_sylheti_transcript

    @property
    def standard_bangla(self) -> str:
        return self.reference_standard_bangla

    @property
    def audio_metadata(self) -> AudioMetadata | None:
        return self.audio_properties

    def to_public_dict(self) -> dict[str, Any]:
        """Safe presentation representation without revealing raw server paths."""
        return {
            "recording_id": self.recording_id,
            "dialect": self.dialect,
            "scenario_card": self.scenario_card,
            "duration_seconds": self.duration_seconds,
            "original_sylheti_transcript": self.original_sylheti_transcript,
            "reference_standard_bangla": self.reference_standard_bangla,
            "english_translation": self.english_translation,
            "reviewer": self.reviewer,
            "consent_status": self.consent_status,
            "measured_duration_sec": self.audio_properties.measured_duration_sec if self.audio_properties else None,
            "sample_rate_hz": self.audio_properties.sample_rate_hz if self.audio_properties else None,
            "channels": self.audio_properties.channels if self.audio_properties else None,
        }


@dataclass
class DatasetValidationResult:
    is_valid: bool
    total_csv_records: int
    total_audio_files: int
    matched_records: int
    missing_audio_files: list[str]
    missing_transcript_records: list[str]
    duplicate_ids: list[str]
    duplicate_filenames: list[str]
    duration_mismatches: list[dict[str, Any]]
    validation_errors: list[str]
    records: list[SylhetiRecordingRecord]


def _inspect_audio_file(file_path: Path) -> AudioMetadata:
    """Inspect actual WAV file header properties."""
    with wave.open(str(file_path), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        duration = nframes / float(framerate) if framerate > 0 else 0.0

        return AudioMetadata(
            encoding="pcm_s16le" if sampwidth == 2 else f"pcm_{sampwidth * 8}bit",
            sample_rate_hz=framerate,
            channels=nchannels,
            sample_width_bytes=sampwidth,
            frame_count=nframes,
            measured_duration_sec=round(duration, 3),
            file_size_bytes=file_path.stat().st_size,
        )


def find_dataset_paths() -> tuple[Path | None, Path | None]:
    """Search for dataset directory in canonical project locations."""
    # Priority candidate pairs
    candidates = [
        (
            Path("dataset/Audio_Record_and_Csv/sylheti_recordings_log_completeV2.csv"),
            Path("dataset/Audio_Record_and_Csv/human_varified_audio.m4a"),
        ),
        (
            Path("data/audio/sylheti/sylheti_recordings_log_completeV2.csv"),
            Path("data/audio/sylheti/human_varified_audio.m4a"),
        ),
        (
            Path("data/audio/sylheti/sylheti_recordings_log_completeV2.csv"),
            Path("data/audio/sylheti/recordings"),
        ),
    ]

    # Search upward starting from current working directory and this file's directory
    roots = [
        Path.cwd(),
        Path.cwd().parent,
        Path(__file__).resolve().parents[3],
        Path(__file__).resolve().parents[4],
    ]

    for root in roots:
        for csv_rel, audio_rel in candidates:
            csv_path = root / csv_rel
            audio_path = root / audio_rel
            if csv_path.exists() and audio_path.exists():
                return csv_path.resolve(), audio_path.resolve()

    return None, None


class SylhetiAudioDataset:
    """Reusable loader and validator for the Sylheti Audio evaluation corpus."""

    def __init__(self, csv_path: str | Path | None = None, audio_dir: str | Path | None = None):
        if csv_path is None or audio_dir is None:
            found_csv, found_audio = find_dataset_paths()
            self.csv_path = Path(csv_path) if csv_path else found_csv
            self.audio_dir = Path(audio_dir) if audio_dir else found_audio
        else:
            self.csv_path = Path(csv_path)
            self.audio_dir = Path(audio_dir)

    def is_installed(self) -> bool:
        return bool(self.csv_path and self.csv_path.exists() and self.audio_dir and self.audio_dir.exists())

    @classmethod
    def load(cls, csv_path: str | Path | None = None, audio_dir: str | Path | None = None) -> "SylhetiAudioDataset":
        inst = cls(csv_path, audio_dir)
        inst._val = inst.load_and_validate()
        return inst

    def validate(self) -> DatasetValidationResult:
        if not hasattr(self, "_val") or self._val is None:
            self._val = self.load_and_validate()
        return self._val

    @property
    def records(self) -> list[SylhetiRecordingRecord]:
        return self.validate().records

    @property
    def scenarios(self) -> dict[str, list[SylhetiRecordingRecord]]:
        sc: dict[str, list[SylhetiRecordingRecord]] = {}
        for r in self.records:
            sc.setdefault(r.scenario_card, []).append(r)
        return sc

    def get(self, rec_id: str) -> SylhetiRecordingRecord | None:
        for r in self.records:
            if r.recording_id == rec_id:
                return r
        return None

    def __len__(self) -> int:
        return len(self.records)

    def load_and_validate(self) -> DatasetValidationResult:
        if not self.is_installed():
            return DatasetValidationResult(
                is_valid=False,
                total_csv_records=0,
                total_audio_files=0,
                matched_records=0,
                missing_audio_files=[],
                missing_transcript_records=[],
                duplicate_ids=[],
                duplicate_filenames=[],
                duration_mismatches=[],
                validation_errors=["Sylheti audio dataset is not installed in standard project paths."],
                records=[],
            )

        assert self.csv_path is not None
        assert self.audio_dir is not None

        # 1. Read raw CSV content with Unicode support
        try:
            raw_text = self.csv_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            raw_text = self.csv_path.read_text(encoding="utf-8", errors="replace")

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not lines:
            return DatasetValidationResult(
                is_valid=False,
                total_csv_records=0,
                total_audio_files=0,
                matched_records=0,
                missing_audio_files=[],
                missing_transcript_records=[],
                duplicate_ids=[],
                duplicate_filenames=[],
                duration_mismatches=[],
                validation_errors=["CSV file is empty."],
                records=[],
            )

        # 2. Handle introductory line (e.g. 'sylheti_recordings_log_complete')
        header_index = 0
        if not lines[0].startswith("id,"):
            for i, line in enumerate(lines):
                if line.startswith("id,"):
                    header_index = i
                    break

        csv_reader = csv.DictReader(lines[header_index:])
        rows = list(csv_reader)

        # 3. Discover audio files on disk
        disk_audio_files = {
            f.name: f for f in self.audio_dir.iterdir() if f.is_file() and not f.name.startswith((".", "__MACOSX"))
        }

        # 4. Process and validate records
        records: list[SylhetiRecordingRecord] = []
        seen_ids: set[str] = set()
        seen_filenames: set[str] = set()
        duplicate_ids: list[str] = []
        duplicate_filenames: list[str] = []
        missing_audio_files: list[str] = []
        missing_transcripts: list[str] = []
        duration_mismatches: list[dict[str, Any]]
        duration_mismatches = []
        validation_errors: list[str] = []

        for row in rows:
            rec_id = row.get("id", "").strip()
            audio_file = row.get("audio_file", "").strip()
            orig_transcript = row.get("original_transcript", "").strip()
            std_bangla = row.get("standard_bangla", "").strip()
            duration_str = row.get("duration_sec", "0").strip()

            # ID validation
            if not rec_id:
                validation_errors.append("Row found with missing 'id'.")
                continue
            if rec_id in seen_ids:
                duplicate_ids.append(rec_id)
            seen_ids.add(rec_id)

            # Filename validation
            if not audio_file:
                validation_errors.append(f"Record {rec_id} has empty 'audio_file'.")
                continue
            if audio_file in seen_filenames:
                duplicate_filenames.append(audio_file)
            seen_filenames.add(audio_file)

            # Transcript validation
            if not orig_transcript:
                missing_transcripts.append(rec_id)

            # Duration parse
            try:
                csv_duration = float(duration_str)
            except ValueError:
                csv_duration = 0.0

            # Match with audio file
            audio_props: AudioMetadata | None = None
            if audio_file not in disk_audio_files:
                missing_audio_files.append(audio_file)
                audio_full_path = str(self.audio_dir / audio_file)
            else:
                target_file = disk_audio_files[audio_file]
                audio_full_path = str(target_file)
                try:
                    audio_props = _inspect_audio_file(target_file)
                    # Check duration deviation (> 1.0s)
                    if abs(audio_props.measured_duration_sec - csv_duration) > 1.0:
                        duration_mismatches.append(
                            {
                                "id": rec_id,
                                "file": audio_file,
                                "csv_duration": csv_duration,
                                "measured_duration": audio_props.measured_duration_sec,
                                "difference": round(abs(audio_props.measured_duration_sec - csv_duration), 2),
                            }
                        )
                except Exception as e:
                    validation_errors.append(f"Could not inspect WAV header for {audio_file}: {e}")

            record = SylhetiRecordingRecord(
                recording_id=rec_id,
                audio_filename=audio_file,
                audio_path=audio_full_path,
                dialect=row.get("dialect", "sylheti").strip(),
                scenario_card=row.get("scenario_card", "").strip(),
                anonymized_speaker_id="speaker_tonmoy_01" if row.get("speaker") else "unknown",
                duration_seconds=csv_duration,
                original_sylheti_transcript=orig_transcript,
                reference_standard_bangla=std_bangla,
                english_translation=row.get("english_translation", "").strip(),
                reviewer=row.get("verified_by", "").strip(),
                consent_status="yes" if row.get("consent_recorded", "").lower().startswith("y") else "unconfirmed",
                audio_properties=audio_props,
            )
            records.append(record)

        # Detect files on disk missing from CSV
        csv_files = {r.audio_filename for r in records}
        unindexed_audio = [f for f in disk_audio_files if f not in csv_files and f.endswith(".wav")]
        if unindexed_audio:
            validation_errors.append(f"Audio files on disk not indexed in CSV: {unindexed_audio}")

        is_valid = (
            len(records) == 16
            and len(missing_audio_files) == 0
            and len(duplicate_ids) == 0
            and len(duplicate_filenames) == 0
            and len(missing_transcripts) == 0
        )

        return DatasetValidationResult(
            is_valid=is_valid,
            total_csv_records=len(rows),
            total_audio_files=len(disk_audio_files),
            matched_records=len(records) - len(missing_audio_files),
            missing_audio_files=missing_audio_files,
            missing_transcript_records=missing_transcripts,
            duplicate_ids=duplicate_ids,
            duplicate_filenames=duplicate_filenames,
            duration_mismatches=duration_mismatches,
            validation_errors=validation_errors,
            records=records,
        )
