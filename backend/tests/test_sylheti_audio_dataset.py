"""Sylheti audio corpus loader/validator, tested on SYNTHETIC fixtures (never the real recordings)."""
import wave
from pathlib import Path

import pytest

from app.services.dataset.sylheti_audio_dataset import CSV_NAME, REQUIRED_COLUMNS, inspect_audio, load_sylheti_audio_dataset

HEADER = ",".join(REQUIRED_COLUMNS)


def write_wav(path: Path, seconds: float = 1.0, rate: int = 16000, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(rate * seconds) * channels)


def row(rid="rec_001", audio="a.wav", duration="1.00", transcript="আমার জ্বর", **over) -> str:
    cells = {"id": rid, "audio_file": audio, "dialect": "sylheti", "scenario_card": "A1", "speaker": "Speaker One", "gender": "male",
             "age_range": "18-25", "consent_recorded": "yes", "duration_sec": duration, "original_transcript": f'"{transcript}"',
             "standard_bangla": '"আমার জ্বর"', "english_translation": '"I have fever"', "verified_by": "Rev "}
    cells.update(over)
    return ",".join(cells[c] for c in REQUIRED_COLUMNS)


@pytest.fixture
def ds_dir(tmp_path):
    (tmp_path / "recordings").mkdir()
    return tmp_path


def make(ds_dir, rows, preamble="sylheti_recordings_log_complete\n"):
    (ds_dir / CSV_NAME).write_text(preamble + HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def codes(load):
    return [i.code for i in load.issues]


def test_valid_record_with_preamble_and_bengali(ds_dir):
    write_wav(ds_dir / "recordings" / "a.wav", 1.0)
    make(ds_dir, [row()])
    load = load_sylheti_audio_dataset(ds_dir)
    assert load.ok and len(load.records) == 1
    r = load.records[0]
    assert r.original_sylheti_transcript == "আমার জ্বর" and r.reviewer == "Rev"  # trimmed metadata, verbatim transcript
    assert r.audio.container == "wav" and r.audio.sample_rate == 16000 and r.audio.channels == 1
    assert "CSV_PREAMBLE" in codes(load)  # the title line above the header is tolerated and reported


def test_public_view_leaks_no_path_filename_speaker_or_text(ds_dir):
    write_wav(ds_dir / "recordings" / "a.wav")
    make(ds_dir, [row()])
    pub = load_sylheti_audio_dataset(ds_dir).records[0].to_public_dict()
    blob = str(pub)
    assert pub["anonymized_speaker_id"] == "S1"
    for secret in ("Speaker One", "a.wav", str(ds_dir), "আমার জ্বর", "recordings"):
        assert secret not in blob


def test_missing_audio_missing_transcript_duplicates(ds_dir):
    write_wav(ds_dir / "recordings" / "a.wav")
    write_wav(ds_dir / "recordings" / "orphan.wav")
    make(ds_dir, [
        row("rec_001", "a.wav"),
        row("rec_001", "b.wav"),                      # duplicate id
        row("rec_002", "a.wav"),                      # duplicate filename
        row("rec_003", "gone.wav"),                   # missing audio
        row("rec_004", "a2.wav", transcript=""),      # missing transcript
    ])
    c = codes(load_sylheti_audio_dataset(ds_dir))
    for expected in ("DUPLICATE_ID", "DUPLICATE_FILENAME", "MISSING_AUDIO", "MISSING_TRANSCRIPT", "ORPHAN_AUDIO"):
        assert expected in c, expected


def test_duration_mismatch_and_out_of_range(ds_dir):
    write_wav(ds_dir / "recordings" / "a.wav", 2.0)
    write_wav(ds_dir / "recordings" / "long.wav", 1.0)
    make(ds_dir, [row("rec_001", "a.wav", duration="9.47"), row("rec_002", "long.wav", duration="1.0")])
    load = load_sylheti_audio_dataset(ds_dir)
    assert any(i.code == "DURATION_MISMATCH" and i.recording_id == "rec_001" for i in load.issues)
    assert not any(i.recording_id == "rec_002" and i.severity == "error" for i in load.issues)


def test_invalid_empty_and_unsupported_audio(ds_dir):
    (ds_dir / "recordings" / "junk.wav").write_bytes(b"this is not audio" * 50)
    (ds_dir / "recordings" / "empty.wav").write_bytes(b"")
    write_wav(ds_dir / "recordings" / "silent.wav", 0.0)
    make(ds_dir, [row("rec_001", "junk.wav"), row("rec_002", "empty.wav"), row("rec_003", "silent.wav")])
    c = codes(load_sylheti_audio_dataset(ds_dir))
    assert "INVALID_AUDIO_CONTENT" in c and c.count("EMPTY_AUDIO") == 2


def test_real_container_is_detected_not_the_extension(ds_dir):
    write_wav(ds_dir / "recordings" / "Recording 13.m4a.wav", 1.0)  # spaces + compound extension, but really WAV
    (ds_dir / "recordings" / "fake.wav").write_bytes(b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 200)  # really MP4/M4A
    make(ds_dir, [row("rec_001", "Recording 13.m4a.wav"), row("rec_002", "fake.wav", duration="1.0")])
    load = load_sylheti_audio_dataset(ds_dir)
    c = codes(load)
    assert "COMPOUND_EXTENSION" in c and "EXTENSION_MISMATCH" in c
    info, _ = inspect_audio(ds_dir / "recordings" / "Recording 13.m4a.wav")
    assert info.container == "wav"


def test_path_traversal_in_the_csv_is_rejected(ds_dir):
    make(ds_dir, [row("rec_001", "../secret.wav"), row("rec_002", "sub/x.wav")])
    load = load_sylheti_audio_dataset(ds_dir)
    assert codes(load).count("UNSAFE_FILENAME") == 2 and not load.records


def test_dataset_not_installed_is_reported_not_raised(tmp_path):
    load = load_sylheti_audio_dataset(tmp_path / "nowhere")
    assert not load.ok and codes(load) == ["DATASET_NOT_INSTALLED"] and load.records == []


def test_missing_columns_and_no_header(ds_dir):
    (ds_dir / CSV_NAME).write_text("id,audio_file\nrec_001,a.wav\n", encoding="utf-8")
    assert "CSV_MISSING_COLUMNS" in codes(load_sylheti_audio_dataset(ds_dir))
    (ds_dir / CSV_NAME).write_text("just some text\nno header here\n", encoding="utf-8")
    assert "CSV_NO_HEADER" in codes(load_sylheti_audio_dataset(ds_dir))


def test_transcripts_are_never_modified_on_load(ds_dir):
    write_wav(ds_dir / "recordings" / "a.wav")
    make(ds_dir, [row(transcript="  আমার  জ্বর  ")])
    before = (ds_dir / CSV_NAME).read_bytes()
    load = load_sylheti_audio_dataset(ds_dir)
    assert load.records[0].original_sylheti_transcript == "  আমার  জ্বর  "  # verbatim
    assert "TRANSCRIPT_WHITESPACE" in codes(load)
    assert (ds_dir / CSV_NAME).read_bytes() == before  # source file untouched


def test_summary_counts(ds_dir):
    write_wav(ds_dir / "recordings" / "a.wav", 1.0)
    write_wav(ds_dir / "recordings" / "b.wav", 2.0, rate=48000, channels=2)
    make(ds_dir, [row("rec_001", "a.wav"), row("rec_002", "b.wav", duration="2.00", scenario_card="B1")])
    s = load_sylheti_audio_dataset(ds_dir).summary()
    assert s["matched_recordings"] == 2 and s["containers"] == {"wav": 2}
    assert s["sample_rates_hz"] == {16000: 1, 48000: 1} and s["channels"] == {1: 1, 2: 1}
    assert s["duration_seconds_min"] == 1.0 and s["duration_seconds_max"] == 2.0
    assert s["scenario_cards"] == {"A1": 1, "B1": 1} and s["distinct_speakers"] == 1
