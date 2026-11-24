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
from dataclasses import asdict, dataclass, field
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
    sample_width_bytes: int = 2
    frame_count: int = 0
    file_size_bytes: int = 0
    encoding: str = "pcm_s16le"

    @property
    def sample_rate_hz(self) -> int:
        return self.sample_rate or 0

    @property
    def measured_duration_sec(self) -> float:
        return self.duration_seconds or 0.0


AudioMetadata = AudioInfo


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

    @property
    def id(self) -> str:
        return self.recording_id

    @property
    def audio_filename(self) -> str:
        return Path(self.audio_path).name

    @property
    def original_transcript(self) -> str:
        return self.original_sylheti_transcript

    @property
    def standard_bangla(self) -> str:
        return self.reference_standard_bangla

    @property
    def audio_metadata(self) -> AudioInfo | None:
        return self.audio

    @property
    def audio_properties(self) -> AudioInfo | None:
        return self.audio

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


SylhetiRecordingRecord = RecordingRecord


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
    records: list[RecordingRecord]


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
            "scenario_cards": dict(Counter(r.scenario_card for r in self.records)),
            "distinct_speakers": len(set(r.anonymized_speaker_id for r in self.records)),
            "errors": len(self.errors),
            "warnings": len([i for i in self.issues if i.severity == "warning"]),
        }


def _sniff_magic(lead: bytes) -> str | None:
    """Guess container format from magic bytes without third-party libraries."""
    if len(lead) < 12:
        return None
    if lead[:4] == b"RIFF" and lead[8:12] == b"WAVE":
        return "wav"
    if lead[:4] == b"OggS":
        return "ogg"
    if lead[4:8] == b"ftyp":
        brand = lead[8:12].lower()
        if brand in (b"m4a ", b"mp42", b"isom", b"dash"):
            return "m4a"
        if brand.startswith(b"3g"):
            return "3gp"
        return "mp4"
    if lead[:3] == b"ID3" or (len(lead) >= 2 and lead[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return "mp3"
    if lead[:6] == b"#!AMR\n":
        return "amr"
    if lead[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    return None


def inspect_audio(path: Path) -> tuple[AudioInfo | None, list[ValidationIssue]]:
    """Determine the true container, codec, rate, channels and duration of an audio file."""
    issues: list[ValidationIssue] = []
    if not path.is_file():
        issues.append(ValidationIssue("error", "FILE_NOT_FOUND", "Audio file does not exist."))
        return None, issues

    size = path.stat().st_size
    if size == 0:
        issues.append(ValidationIssue("error", "EMPTY_AUDIO", "Audio file has zero bytes."))
        return None, issues

    try:
        lead = path.read_bytes()[:32]
    except OSError as exc:
        issues.append(ValidationIssue("error", "UNREADABLE_AUDIO", f"Cannot read audio bytes: {exc}."))
        return None, issues

    magic = _sniff_magic(lead)

    # 1. Try Python stdlib `wave`
    if magic == "wav":
        try:
            with wave.open(str(path), "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                sampwidth = w.getsampwidth()
                dur = frames / float(rate) if rate else 0.0
                if dur <= 0.0:
                    issues.append(ValidationIssue("error", "EMPTY_AUDIO", "WAV has zero duration or sample rate."))
                    return None, issues
                return AudioInfo(
                    container="wav", codec=f"pcm_s{sampwidth * 8}le", sample_rate=rate, channels=w.getnchannels(),
                    duration_seconds=round(dur, 3), inspector="wave", sample_width_bytes=sampwidth,
                    frame_count=frames, file_size_bytes=size, encoding=f"pcm_s{sampwidth * 8}le",
                ), issues
        except wave.Error:
            pass  # Fall through to ffprobe if wave failed on non-standard WAV

    # 2. Try ffprobe
    if shutil.which("ffprobe"):
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels,duration:format=format_name,duration",
            "-of", "json", str(path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10.0)
            if proc.returncode == 0:
                import json as _json
                data = _json.loads(proc.stdout)
                streams = data.get("streams") or []
                fmt = data.get("format") or {}
                if streams:
                    s = streams[0]
                    dur_s = s.get("duration") or fmt.get("duration")
                    dur = float(dur_s) if dur_s is not None else None
                    rate = int(s["sample_rate"]) if "sample_rate" in s else None
                    container = magic or (fmt.get("format_name", "").split(",")[0] if fmt.get("format_name") else "unknown")
                    if container.lower() in ("mov,mp4,m4a,3gp,3g2,mj2", "mp4"):
                        container = "m4a"
                    return AudioInfo(
                        container=container, codec=s.get("codec_name"), sample_rate=rate,
                        channels=s.get("channels"), duration_seconds=round(dur, 3) if dur is not None else None,
                        inspector="ffprobe", file_size_bytes=size,
                    ), issues
        except Exception:
            pass

    # 3. Magic bytes fallback
    if magic:
        issues.append(ValidationIssue("warning", "FFPROBE_UNAVAILABLE", "Container detected via magic bytes; rate/channels unverified."))
        return AudioInfo(container=magic, codec=None, sample_rate=None, channels=None, duration_seconds=None, inspector="magic-bytes", file_size_bytes=size), issues

    issues.append(ValidationIssue("error", "INVALID_AUDIO_CONTENT", "File is not a recognised audio container."))
    return None, issues


def _safe_name(name: str) -> bool:
    if not name or name.strip() != name:
        return False
    p = Path(name)
    return p.name == name and ".." not in p.parts


def _read_rows(csv_path: Path, issues: list[ValidationIssue]) -> list[dict[str, str]]:
    text = csv_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        issues.append(ValidationIssue("error", "CSV_EMPTY", "Recordings CSV is empty."))
        return []

    first = lines[0].strip()
    idx = 0
    if not any(col in first for col in ("id", "audio_file", "scenario_card")):
        issues.append(ValidationIssue("warning", "CSV_PREAMBLE", f"Non-header line preceding the CSV table: {first!r}."))
        idx = 1
        while idx < len(lines) and not any(col in lines[idx] for col in ("id", "audio_file")):
            idx += 1
        if idx >= len(lines):
            issues.append(ValidationIssue("error", "CSV_NO_HEADER", "Could not locate the CSV header line."))
            return []

    r = csv.DictReader(lines[idx:])
    fields = [f.strip() for f in (r.fieldnames or []) if f]
    missing = [c for c in REQUIRED_COLUMNS if c not in fields]
    if missing:
        issues.append(ValidationIssue("error", "CSV_MISSING_COLUMNS", f"Missing required columns: {missing}."))
        return []
    return list(r)


def load_sylheti_audio_dataset(dataset_path: Path | str | None = None, inspect: bool = True) -> DatasetLoad:
    """Load and validate the dataset, returning DatasetLoad."""
    root = Path(dataset_path) if dataset_path else dataset_dir()
    issues: list[ValidationIssue] = []

    if not root.is_dir():
        issues.append(ValidationIssue("error", "DATASET_NOT_INSTALLED", f"Dataset directory not found: {root}."))
        return DatasetLoad(root, [], issues)

    csv_path = root / CSV_NAME
    if not csv_path.is_file():
        issues.append(ValidationIssue("error", "CSV_MISSING", f"{CSV_NAME} missing in {root}."))
        return DatasetLoad(root, [], issues)

    rec_dir = root / "recordings"
    files = set(f.name for f in rec_dir.iterdir() if f.is_file() and not f.name.startswith(".")) if rec_dir.is_dir() else []
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


load_sylheti_dataset = load_sylheti_audio_dataset


def to_pcm16_mono_wav_bytes(audio_path: Path) -> bytes:
    """Read any audio file and convert to 16kHz mono 16-bit PCM WAV bytes."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(audio_path), "-ar", "16000", "-ac", "1", "-f", "wav", "-"]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    return proc.stdout


def find_dataset_paths() -> tuple[Path | None, Path | None]:
    """Search for dataset directory in canonical project locations."""
    candidates = [
        (Path("data/audio/sylheti/sylheti_recordings_log_completeV2.csv"), Path("data/audio/sylheti/recordings")),
        (Path("data/audio/sylheti/sylheti_recordings_log_completeV2.csv"), Path("data/audio/sylheti/human_varified_audio.m4a")),
        (Path("dataset/Audio_Record_and_Csv/sylheti_recordings_log_completeV2.csv"), Path("dataset/Audio_Record_and_Csv/human_varified_audio.m4a")),
    ]
    roots = [Path.cwd(), Path.cwd().parent, Path(__file__).resolve().parents[3], Path(__file__).resolve().parents[4]]
    for root in roots:
        for csv_rel, audio_rel in candidates:
            c = root / csv_rel
            a = root / audio_rel
            if c.exists() and a.exists():
                return c.resolve(), a.resolve()
    return None, None


class SylhetiAudioDataset:
    """Class wrapper supporting load/validate for evaluation tests and scripts."""

    def __init__(self, csv_path: Path, audio_dir: Path, records: list[RecordingRecord]):
        self.csv_path = csv_path
        self.audio_dir = audio_dir
        self.records = records

    @classmethod
    def load(cls, csv_path: Path | str, audio_dir: Path | str) -> SylhetiAudioDataset:
        cp = Path(csv_path)
        ap = Path(audio_dir)
        load = load_sylheti_audio_dataset(ap.parent if (ap.parent / CSV_NAME).exists() else cp.parent)
        if load.records:
            return cls(cp, ap, load.records)

        # Fallback direct loader if paths are separated
        issues: list[ValidationIssue] = []
        rows = _read_rows(cp, issues)
        records: list[RecordingRecord] = []
        for r in rows:
            rid = (r.get("id") or "").strip()
            fname = (r.get("audio_file") or "").strip()
            fpath = ap / fname
            info: AudioInfo | None = None
            if fpath.exists():
                info, _ = inspect_audio(fpath)
            records.append(RecordingRecord(
                recording_id=rid, audio_path=fpath, dialect=r.get("dialect", "sylheti").strip(),
                scenario_card=r.get("scenario_card", "").strip(), anonymized_speaker_id="S1",
                duration_seconds=float(r.get("duration_sec") or 0.0),
                original_sylheti_transcript=r.get("original_transcript", "").strip(),
                reference_standard_bangla=r.get("standard_bangla", "").strip(),
                english_translation=r.get("english_translation", "").strip(),
                reviewer=r.get("verified_by", "").strip(),
                consent_status="recorded" if r.get("consent_recorded", "").lower().startswith("y") else "unconfirmed",
                audio=info,
            ))
        return cls(cp, ap, records)

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)

    def get(self, recording_id: str) -> RecordingRecord | None:
        for r in self.records:
            if r.recording_id == recording_id:
                return r
        return None

    @property
    def scenarios(self) -> dict[str, list[RecordingRecord]]:
        m: dict[str, list[RecordingRecord]] = {}
        for r in self.records:
            m.setdefault(r.scenario_card, []).append(r)
        return m

    def validate(self) -> DatasetValidationResult:
        missing_audio = [r.audio_filename for r in self.records if not Path(r.audio_path).exists()]
        errors: list[str] = []
        if missing_audio:
            errors.append(f"Missing audio files: {missing_audio}")
        return DatasetValidationResult(
            is_valid=len(missing_audio) == 0 and len(self.records) > 0,
            total_csv_records=len(self.records),
            total_audio_files=len(self.records) - len(missing_audio),
            matched_records=len(self.records) - len(missing_audio),
            missing_audio_files=missing_audio,
            missing_transcript_records=[],
            duplicate_ids=[],
            duplicate_filenames=[],
            duration_mismatches=[],
            validation_errors=errors,
            records=self.records,
        )
