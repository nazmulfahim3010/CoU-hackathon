# Sylheti transcription and normalization: operations guide

How the Sylheti audio corpus and glossary are used, how to validate and evaluate them, and how to read the results.

## 1. Data layout
```
data/
  glossary/sylheti_glossary_120-final.csv      controlled lexical resource (committed)
  audio/sylheti/                               research corpus: NEVER committed, NEVER in a Docker image
    sylheti_recordings_log_completeV2.csv      title line, then header; transcripts + metadata
    recordings/                                16 WAV files (original names kept, incl. spaces and ".m4a.wav")
reports/                                       generated: public (*.json|md) and git-ignored (*.local.json)
```
The two datasets must not be confused: **audio = evaluation corpus** (ground truth for scoring only), **glossary = lexical evidence used during normalization**.
The live app never reads the audio corpus and works when it is not installed. Reference transcripts are never used as transcription output.

## 2. Validate the data
```powershell
cd backend
.venv\Scripts\python scripts\validate_sylheti_dataset.py            # add --strict to fail on errors
```
Checks the transcript CSV (preamble line, Bengali Unicode, required columns), exact audio filename matches, duplicate ids/filenames, missing audio or transcripts,
real container/codec/sample rate/channels (from the bytes, not the extension), declared vs actual duration, path-traversal in filenames, and that the glossary CSV is
well-formed **and identical in content to the runtime `sylheti.json`**. Output: `reports/sylheti_dataset_validation.json` (ids, counts, issue codes; no text, paths or names).

Known results on the supplied data: 16/16 matched, all real WAV (PCM s16, 48 kHz, stereo); **rec_015/rec_016 look swapped** (durations reversed); glossary 120/120 valid.

## 3. Evaluate (real speech recognition)
Runs in Docker because it needs ffmpeg and uses the same code path as the app.
```powershell
docker build -f backend/Dockerfile -t kotha-backend .
docker run --rm --user root --env-file backend/.env `
  -v "${PWD}\data:/app/data:ro" -v "${PWD}\reports:/app/reports" `
  kotha-backend python scripts/evaluate_sylheti_dataset.py --confirm-third-party-processing
```
- **Consent gate:** the recordings are sent to the configured third-party speech provider, so the script refuses to run without
  `--confirm-third-party-processing`. Confirm that each speaker's consent covers this first. `--skip-asr` evaluates normalization only (no audio leaves the machine).
- **ASR** is scored against `original_transcript` (CER, WER, exact match, empty rate, failure rate, time). It is never compared with the standard-Bangla column.
- **Normalization** of the reference Sylheti transcripts is scored against `standard_bangla` plus semantic screens (negation, symptoms, body parts, numbers/duration, severity
  markers, unsupported symptom insertion). `requires_human_review` is an automated screen; a person must judge clinical meaning for every flagged pair.
- `--no-llm` forces glossary-only normalization; otherwise the configured LLM is used when present (and falls back to glossary-only if it is unavailable).
- Outputs: `sylheti_asr_evaluation.{json,md}`, `sylheti_normalization_evaluation.json` (metrics/ids only) and `sylheti_evaluation.local.json` (texts; git-ignored).

## 4. Normalization behaviour
```
original transcript (never overwritten)
  -> glossary matching (exact; multiword phrases matched before their parts; every hit has glossary_id + matching_method)
  -> optional LLM proposal -> independent verification (cited text must exist; "glossary" labels must match a real row)
  -> meaning guards (negation, numbers/duration units, invented symptoms) -> proposal shown to the patient
  -> patient/authorised reviewer confirms (backend-enforced) -> extraction -> summary
```
Response fields: `glossary_evidence[]`, `normalization_status` (`glossary_only_proposal`, `no_glossary_match_unchanged`, `llm_proposal_validated`,
`llm_rejected_glossary_fallback`), `changes[].glossary_evidence_ids`, `warnings[]`. Glossary mappings are lexical evidence, not proof that a sentence keeps its meaning.
If the LLM fails or is rejected, the glossary-only proposal is shown and the original is untouched.

## 5. Speech-recognition safeguards in the app
- Leaked model tokens (e.g. `<|sq|>`) and stray invalid code points are removed.
- Transcripts where many words are orthographically impossible in Bengali script are rejected with `ASR_UNINTELLIGIBLE` ("please say it again or type it").
- Non-Bangla or empty output is rejected (`ASR_NON_BANGLA`, `NO_SPEECH_DETECTED`) and is **not** reported as a provider outage.
- These checks cannot catch well-formed but wrong words. That is why the confirmation screen and the typed fallback exist.

## 6. Privacy and consent
- Raw audio and the audio CSV are git-ignored, excluded from Docker contexts, never served by any API, and never logged. Public reports contain no audio, transcripts, file paths,
  speaker names, keys or provider bodies; the speaker is exposed only as an anonymised id (`S1`).
- `consent_recorded=yes` in the CSV is a flag, not consent documentation. Confirm permitted uses (including third-party AI processing and publication) before sharing data or reports further.
- Single speaker, 16 short recordings: not representative of Sylheti regional variation. No clinical or accuracy claim is made.

## 6b. Measured speech-recognition quality (16 clips, one speaker, indicative only)
Groq `whisper-large-v3`, `language=bn`, no prompt: 16/16 returned text, mean CER 0.495, mean WER 0.921, exact match 0. Set `SPEECH_MODEL=whisper-large-v3` for dialect speech;
`whisper-large-v3-turbo` was worse in our exploratory run. Leave `SPEECH_PROMPT` empty (a Bangla prompt caused empty transcripts). Treat recognised text as a draft the patient must confirm or retype.

## 7. Configuration
`KOTHA_SYLHETI_DATASET_DIR` (default `data/audio/sylheti`) and `KOTHA_GLOSSARY_CSV` (default `data/glossary/sylheti_glossary_120-final.csv`) are read only by the offline scripts.
Speech and LLM settings are the normal ones in `backend/.env` (see `.env.example`); keys are never printed.

## 8. Tests
`docker compose --profile test run --rm backend-test` runs everything, including the new suites:
`test_sylheti_audio_dataset.py`, `test_glossary_csv.py`, `test_sylheti_evaluation.py`, `test_normalization_safety.py`, `test_stt_provider_errors.py`.
Dataset tests use synthetic fixtures, never the real recordings. Real-provider verification is separate (section 3).
