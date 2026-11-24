"""Loader and validator for the Sylheti audio evaluation corpus.

Layout (data/audio/sylheti/):
    sylheti_recordings_log_completeV2.csv   (a title line may precede the real header)
    recordings/<audio files, original names preserved>

Purpose: ASR and normalization EVALUATION only. The reference transcripts here are ground truth for scoring;
they must never be returned as live transcription output. The originals are treated as immutable: this module
reads them and never writes them.
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import unicodedata
import wave
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# backend/app/services/dataset/this_file.py -> repo root is parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATASET_DIR = REPO_ROOT / "data" / "audio" / "sylheti"
CSV_NAME = "sylheti_recordings_log_completeV2.csv"
REQUIRED_COLUMNS = (
    "id", "audio_file", "dialect", "scenario_card", "speaker", "gender", "age_range", "consent_recorded",
    "duration_sec", "original_transcript", "standard_bangla", "english_translation", "verified_by",
)
MAX_APP_AUDIO_SECONDS = 90.0  # the live app rejects anything longer
DURATION_TOLERANCE_SECONDS = 0.25  # CSV durations are rounded to 2 decimals and measured by the recorder app


def dataset_dir() -> Path:
    """Dataset location: KOTHA_SYLHETI_DATASET_DIR if set, else <repo>/data/audio/sylheti."""
    env = os.environ.get("KOTHA_SYLHETI_DATASET_DIR")
    return Path(env) if env else DEFAULT_DATASET_DIR


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    recording_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "code": self.code, "recording_id": self.recording_id, "message": self.message}


@dataclass(frozen=True)
class AudioInfo:
    container: str  # real container detected from the bytes, NOT from the file extension
    codec: str | None
    sample_rate: int | None
    channels: int | None
    duration_seconds: float | None
    inspector: str  # "wave" | "ffprobe" | "magic-bytes"


@dataclass(frozen=True)
class RecordingRecord:
    recording_id: str
    audio_path: Path = field(repr=False)  # private: never expose through an API
    dialect: str
    scenario_card: str
    anonymized_speaker_id: str
    duration_seconds: float | None  # as declared in the CSV
    original_sylheti_transcript: str = field(repr=False)
    reference_standard_bangla: str = field(repr=False)
    english_translation: str = field(repr=False)
    reviewer: str
    consent_status: str  # "recorded" | "unconfirmed" (a CSV flag is not consent documentation)
    audio: AudioInfo | None = None

    def to_public_dict(self) -> dict[str, Any]:
        """Safe summary: no file path, no file name, no speaker identity, no transcript text."""
        return {
            "recording_id": self.recording_id,
            "dialect": self.dialect,
            "scenario_card": self.scenario_card,
            "anonymized_speaker_id": self.anonymized_speaker_id,
            "duration_seconds": self.duration_seconds,
            "consent_status": self.consent_status,
            "audio_container": self.audio.container if self.audio else None,
        }


@dataclass
class DatasetLoad:
    root: Path
    records: list[RecordingRecord]
    issues: list[ValidationIssue]
    audio_files_found: int = 0
    csv_rows: int = 0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> dict[str, Any]:
        infos = [r.audio for r in self.records if r.audio]
        durations = [i.duration_seconds for i in infos if i.duration_seconds is not None]
        codes = Counter(i.code for i in self.issues)
        return {
            "audio_files_found": self.audio_files_found,
            "transcript_records": self.csv_rows,
            "matched_recordings": len(self.records),
            "missing_audio_files": codes.get("MISSING_AUDIO", 0),
            "missing_transcripts": codes.get("MISSING_TRANSCRIPT", 0),
            "orphan_audio_files": codes.get("ORPHAN_AUDIO", 0),
            "duplicate_ids": codes.get("DUPLICATE_ID", 0),
            "duplicate_filenames": codes.get("DUPLICATE_FILENAME", 0),
            "containers": dict(Counter(i.container for i in infos)),
            "codecs": dict(Counter(i.codec for i in infos)),
            "sample_rates_hz": dict(Counter(i.sample_rate for i in infos)),
            "channels": dict(Counter(i.channels for i in infos)),
            "duration_seconds_min": round(min(durations), 2) if durations else None,
            "duration_seconds_max": round(max(durations), 2) if durations else None,
            "scenario_cards": dict(sorted(Counter(r.scenario_card for r in self.records).items())),
            "distinct_speakers": len({r.anonymized_speaker_id for r in self.records}),
            "consent_status": dict(Counter(r.consent_status for r in self.records)),
            "issue_counts": dict(codes),
            "errors": len(self.errors),
            "warnings": len(self.issues) - len(self.errors),
        }


# ------------------------------------------------------------------ audio inspection
def _sniff(head: bytes) -> str | None:
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"OggS":
        return "ogg"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "webm/matroska"
    if head[4:8] == b"ftyp":
        return "mp4/m4a"
    if head[:4] == b"fLaC":
        return "flac"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    return None


def _ffprobe(path: Path) -> AudioInfo | None:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries", "format=format_name,duration:stream=codec_name,sample_rate,channels",
             "-of", "default=noprint_wrappers=1:nokey=0", str(path)],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    kv = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    try:
        return AudioInfo(
            container=kv.get("format_name", "unknown"), codec=kv.get("codec_name"),
            sample_rate=int(kv["sample_rate"]) if kv.get("sample_rate") else None,
            channels=int(kv["channels"]) if kv.get("channels") else None,
            duration_seconds=float(kv["duration"]) if kv.get("duration") else None, inspector="ffprobe",
        )
    except ValueError:
        return None


def inspect_audio(path: Path) -> tuple[AudioInfo | None, list[ValidationIssue]]:
    """Inspect the REAL encoding from the file's bytes (the extension is never trusted)."""
    issues: list[ValidationIssue] = []
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError as exc:
        return None, [ValidationIssue("error", "UNREADABLE_AUDIO", f"Cannot read audio file ({type(exc).__name__}).")]
    if size == 0:
        return None, [ValidationIssue("error", "EMPTY_AUDIO", "Audio file is empty (0 bytes).")]
    kind = _sniff(head)
    if kind is None:
        return None, [ValidationIssue("error", "INVALID_AUDIO_CONTENT", "File content is not a recognised audio format.")]
    if kind == "wav":
        try:
            with wave.open(str(path), "rb") as w:
                frames, rate, ch, width = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
            if frames == 0 or rate <= 0:
                return None, [ValidationIssue("error", "EMPTY_AUDIO", "WAV file contains no audio frames.")]
            return AudioInfo("wav", f"pcm_s{width * 8}le", rate, ch, frames / float(rate), "wave"), issues
        except (wave.Error, EOFError):
            info = _ffprobe(path)  # e.g. float / ADPCM WAV that the stdlib cannot read
            if info:
                return info, issues
            return None, [ValidationIssue("error", "UNSUPPORTED_WAV_ENCODING", "WAV encoding could not be inspected.")]
    info = _ffprobe(path)
    if info:
        return info, issues
    issues.append(ValidationIssue("warning", "FFPROBE_UNAVAILABLE", f"{kind} audio detected but ffprobe is unavailable; details unknown."))
    return AudioInfo(kind, None, None, None, None, "magic-bytes"), issues


# ------------------------------------------------------------------ CSV
def _read_rows(csv_path: Path, issues: list[ValidationIssue]) -> list[dict[str, str]]:
    try:
        raw = csv_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        issues.append(ValidationIssue("error", "CSV_UNREADABLE", f"Cannot read transcript CSV ({type(exc).__name__})."))
        return []
    lines = raw.splitlines()
    header_idx = next((i for i, l in enumerate(lines) if l.lower().startswith("id,") and "audio_file" in l), None)
    if header_idx is None:
        issues.append(ValidationIssue("error", "CSV_NO_HEADER", "No header row (id,audio_file,...) found."))
        return []
    if header_idx > 0:
        issues.append(ValidationIssue("warning", "CSV_PREAMBLE", f"{header_idx} line(s) precede the header and were skipped."))
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        issues.append(ValidationIssue("error", "CSV_MISSING_COLUMNS", f"Missing columns: {', '.join(missing)}"))
        return []
    return list(reader)


def _safe_name(name: str) -> bool:
    return bool(name) and name == Path(name).name and ".." not in name and "/" not in name and "\\" not in name


def load_sylheti_audio_dataset(root: Path | None = None, *, inspect: bool = True) -> DatasetLoad:
    root = Path(root) if root else dataset_dir()
    issues: list[ValidationIssue] = []
    csv_path, rec_dir = root / CSV_NAME, root / "recordings"
    if not csv_path.exists():
        return DatasetLoad(root, [], [ValidationIssue("error", "DATASET_NOT_INSTALLED", "Transcript CSV not found; dataset is not installed.")])
    files = sorted(p.name for p in rec_dir.iterdir() if p.is_file() and not p.name.startswith(".")) if rec_dir.is_dir() else []
    if not rec_dir.is_dir():
        issues.append(ValidationIssue("error", "RECORDINGS_DIR_MISSING", "recordings/ directory not found."))

    rows = _read_rows(csv_path, issues)
    records: list[RecordingRecord] = []
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    speaker_ids: dict[str, str] = {}
    referenced: set[str] = set()

    for row in rows:
        rid = (row.get("id") or "").strip()
        fname = row.get("audio_file") or ""
        if not rid:
            issues.append(ValidationIssue("error", "MISSING_ID", "A row has no recording id."))
            continue
        if rid in seen_ids:
            issues.append(ValidationIssue("error", "DUPLICATE_ID", "Recording id appears more than once.", rid))
            continue
        seen_ids.add(rid)
        if fname in seen_files:
            issues.append(ValidationIssue("error", "DUPLICATE_FILENAME", "Audio filename is used by more than one row.", rid))
            continue
        seen_files.add(fname)

        original = row.get("original_transcript") or ""
        if not original.strip():
            issues.append(ValidationIssue("error", "MISSING_TRANSCRIPT", "Row has no original transcript.", rid))
            continue
        if original != original.strip():
            issues.append(ValidationIssue("warning", "TRANSCRIPT_WHITESPACE", "Transcript has leading/trailing whitespace (preserved as-is).", rid))
        if unicodedata.normalize("NFC", original) != original:
            issues.append(ValidationIssue("warning", "TRANSCRIPT_NOT_NFC", "Transcript is not NFC-normalised (preserved as-is).", rid))
        if not (row.get("standard_bangla") or "").strip():
            issues.append(ValidationIssue("warning", "MISSING_REFERENCE", "No standard Bangla reference for this row.", rid))

        if not _safe_name(fname):
            issues.append(ValidationIssue("error", "UNSAFE_FILENAME", "Audio filename is empty or contains a path component.", rid))
            continue
        path = rec_dir / fname
        if fname not in files:
            issues.append(ValidationIssue("error", "MISSING_AUDIO", "Referenced audio file does not exist (exact-name match).", rid))
            continue
        referenced.add(fname)

        info: AudioInfo | None = None
        if inspect:
            info, audio_issues = inspect_audio(path)
            issues.extend(ValidationIssue(i.severity, i.code, i.message, rid) for i in audio_issues)
            if info is None:
                continue
            ext = "".join(Path(fname).suffixes).lower()
            if ext.count(".") > 1:
                issues.append(ValidationIssue("warning", "COMPOUND_EXTENSION", f"Compound extension '{ext}'; real container is {info.container}.", rid))
            if info.container not in ("wav",) and ext.endswith(".wav"):
                issues.append(ValidationIssue("warning", "EXTENSION_MISMATCH", f"Extension says wav but content is {info.container}.", rid))

        declared: float | None
        try:
            declared = float(row.get("duration_sec") or "")
        except ValueError:
            declared = None
            issues.append(ValidationIssue("warning", "DURATION_UNPARSEABLE", "duration_sec is not a number.", rid))
        actual = info.duration_seconds if info else None
        if declared is not None and actual is not None and abs(declared - actual) > DURATION_TOLERANCE_SECONDS:
            issues.append(ValidationIssue("error", "DURATION_MISMATCH", f"Declared {declared:.2f}s vs actual {actual:.2f}s.", rid))
        check = actual if actual is not None else declared
        if check is not None and not (0.5 <= check <= MAX_APP_AUDIO_SECONDS):
            issues.append(ValidationIssue("error", "DURATION_OUT_OF_RANGE", f"{check:.2f}s is outside the app's 0.5-{MAX_APP_AUDIO_SECONDS:.0f}s range.", rid))

        speaker = (row.get("speaker") or "").strip() or "unknown"
        anon = speaker_ids.setdefault(speaker, f"S{len(speaker_ids) + 1}")
        consent = "recorded" if (row.get("consent_recorded") or "").strip().lower() == "yes" else "unconfirmed"
        records.append(RecordingRecord(
            recording_id=rid, audio_path=path, dialect=(row.get("dialect") or "").strip(),
            scenario_card=(row.get("scenario_card") or "").strip(), anonymized_speaker_id=anon,
            duration_seconds=declared, original_sylheti_transcript=original,
            reference_standard_bangla=(row.get("standard_bangla") or ""), english_translation=(row.get("english_translation") or ""),
            reviewer=(row.get("verified_by") or "").strip(), consent_status=consent, audio=info,
        ))

    for _ in sorted(set(files) - seen_files):
        issues.append(ValidationIssue("warning", "ORPHAN_AUDIO", "An audio file in recordings/ has no transcript row."))
    return DatasetLoad(root, records, issues, audio_files_found=len(files), csv_rows=len(rows))
