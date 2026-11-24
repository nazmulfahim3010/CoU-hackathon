"""Offline dataset tooling (evaluation corpora, glossary CSV validation, metrics).

Nothing in this package is imported by the live patient request path: Kotha must keep working when the
research datasets are not installed.
"""
from .evaluation import (
    asr_metrics,
    asr_rollup,
    by_scenario,
    normalization_rollup,
    possible_label_mismatches,
    semantic_checks,
)
from .glossary_csv import (
    GlossaryCsvLoad,
    compare_with_runtime,
    glossary_csv_path,
    load_glossary_csv,
)

GlossaryCSVLoad = GlossaryCsvLoad
from .metrics import cer, wer
from .sylheti_audio_dataset import (
    AudioInfo,
    AudioMetadata,
    DatasetLoad,
    DatasetValidationResult,
    RecordingRecord,
    SylhetiAudioDataset,
    SylhetiRecordingRecord,
    dataset_dir,
    find_dataset_paths,
    inspect_audio,
    load_sylheti_audio_dataset,
    to_pcm16_mono_wav_bytes,
)
from .sylheti_glossary import (
    find_glossary_csv_path,
    get_sylheti_glossary_stats,
    parse_sylheti_glossary_csv,
    sync_glossary_json,
)

__all__ = [
    "AudioInfo",
    "AudioMetadata",
    "DatasetLoad",
    "DatasetValidationResult",
    "GlossaryCSVLoad",
    "RecordingRecord",
    "SylhetiAudioDataset",
    "SylhetiRecordingRecord",
    "asr_metrics",
    "asr_rollup",
    "by_scenario",
    "cer",
    "compare_with_runtime",
    "dataset_dir",
    "find_dataset_paths",
    "find_glossary_csv_path",
    "get_sylheti_glossary_stats",
    "glossary_csv_path",
    "inspect_audio",
    "load_glossary_csv",
    "load_sylheti_audio_dataset",
    "normalization_rollup",
    "parse_sylheti_glossary_csv",
    "possible_label_mismatches",
    "semantic_checks",
    "sync_glossary_json",
    "to_pcm16_mono_wav_bytes",
    "wer",
]
