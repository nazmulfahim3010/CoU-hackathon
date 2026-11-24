# Sylheti ASR and normalization evaluation

Generated 2026-11-24T06:50:32+00:00. Speech: `openai_compatible` / `whisper-large-v3` (credentials configured: True). Normalization LLM used: False.

## ASR (scored against the original Sylheti transcript)

| Metric | Value |
|---|---|
| recordings | 16 |
| successful_transcriptions | 16 |
| failed_transcriptions | 0 |
| failure_rate | 0.0 |
| empty_transcripts | 0 |
| empty_transcript_rate | 0.0 |
| exact_match_rate | 0.0 |
| mean_cer | 0.4949 |
| mean_wer | 0.9205 |
| mean_processing_seconds | 3.0488 |

### By scenario card

| Card | n | ok | failed | mean CER | mean WER |
|---|---|---|---|---|---|
| A1 | 2 | 2 | 0 | 0.4243 | 0.9062 |
| A2 | 2 | 2 | 0 | 0.5305 | 0.9621 |
| A3 | 2 | 2 | 0 | 0.4576 | 1.0402 |
| B1 | 2 | 2 | 0 | 0.3287 | 0.825 |
| B2 | 2 | 2 | 0 | 0.5089 | 0.9285 |
| B3 | 1 | 1 | 0 | 0.5385 | 1.0 |
| C1 | 3 | 3 | 0 | 0.3993 | 0.8198 |
| C2 | 2 | 2 | 0 | 0.8411 | 0.9722 |

### Possible audio/transcript label mismatches (diagnostic; dataset not altered)

- `rec_015` recognised text is closer to `rec_016`'s reference (CER 0.8632 vs 0.3714)
- `rec_016` recognised text is closer to `rec_015`'s reference (CER 0.819 vs 0.5895)

## Normalization of the reference Sylheti transcripts (scored against standard Bangla)

| Metric | Value |
|---|---|
| pairs_evaluated | 16 |
| mean_cer_vs_reference | 0.4396 |
| mean_wer_vs_reference | 0.6826 |
| exact_match_reference | 0 |
| negation_preserved_vs_reference | 15 |
| negation_guard_failures | 0 |
| symptom_preserved | 15 |
| body_part_preserved | 15 |
| severity_marker_preserved | 11 |
| numbers_preserved | 16 |
| duration_unit_guard_failures | 0 |
| unsupported_symptom_insertions | 0 |
| requires_human_review | 11 |

## Limitations

- Single speaker, 16 short recordings: not representative of Sylheti regional variation.
- Reference transcripts are team-authored; independent adjudication is not established.
- Metrics are descriptive, not a claim of clinical accuracy.

_requires_human_review is an automated screen. A human must judge clinical meaning for every flagged pair._
