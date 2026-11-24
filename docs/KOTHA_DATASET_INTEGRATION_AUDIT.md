# Kotha: Sylheti dataset integration audit

Audit performed before changing code (2026-11-24). Scope: integrate the supplied Sylheti audio corpus and glossary into the
existing Kotha architecture, repair the transcription/normalization pipeline, and measure it honestly. Nothing was rebuilt.

## 1. Repository state at audit time
- Branch `main`, in sync with `origin/main`, clean working tree (no uncommitted changes to preserve).
- Stack unchanged: FastAPI + Pydantic backend, React/Vite frontend, Docker (backend image includes ffmpeg), in-memory sessions, no database.

## 2. Existing architecture (what already worked)
| Concern | Where | State |
|---|---|---|
| Workflow gate | `core/session_manager.py` stages CREATED to SUMMARIZED; `409 CONFIRMATION_REQUIRED` | Working; backend-enforced |
| STT | `services/speech_to_text.py` (`process_audio` = ffmpeg to 16 kHz mono WAV; adapters: Groq/OpenAI-compatible, Hugging Face, local transformers) | Working; Groq verified live |
| Normalization | `services/dialect_normalizer.py` (`normalize()`: glossary match, optional LLM, meaning guards) used for typed **and** recognised text | Working; one engine |
| Glossary | `data/glossary/*.csv` -> `scripts/import_glossary.py` -> `app/data/dialects/sylheti.json` -> `glossary_service.Glossary` (longest-first regex, word boundaries) | Working; **no traceability** |
| Extraction / grounding | `clinical_extractor.py`, `grounding.py` | Working |
| Summary / sharing | `summary_generator.py`, `routes/share.py` | Working |
| API contracts | `/api/transcription`, `/transcription/typed`, `/normalization`, `/confirmation`, `/clinical/extract`, ... | Unchanged (fields added, none removed) |
| LLM | `llm_provider.py` (OpenAI-compatible, Anthropic) | Code works; the pasted Gemini model id is retired (404), so live LLM was not available for this audit |

## 3. The datasets
**A. Audio corpus** (`data/audio/sylheti/`): 16 recordings, 16 transcript rows (`id, audio_file, dialect, scenario_card, speaker, gender,
age_range, consent_recorded, duration_sec, original_transcript, standard_bangla, english_translation, verified_by`).
Real encoding (probed from bytes, not extensions): **all 16 are WAV, PCM 16-bit, 48 kHz, stereo**, 6.83-15.87 s. Scenario cards A1-C2
(A1 x2, A2 x2, A3 x2, B1 x2, B2 x2, B3 x1, C1 x3, C2 x2). One speaker. Consent is a `yes` flag only.

**B. Glossary** (`data/glossary/sylheti_glossary_120-final.csv`): 120 rows, unique ids and expressions, all `sylheti`, all `verified` with
`verified_by` / date / note. **Byte-identical to the file already imported earlier**, so the runtime glossary already matched it; the CSV was
moved to `data/glossary/` and a validator now proves the runtime JSON cannot drift from it.

## 4. Findings (root causes), in order of importance
1. **Zero-shot ASR does not recognise this Sylheti audio.** Official run (Groq `whisper-large-v3`, language `bn`, no prompt, 16/16 clips returned text):
   mean CER 0.495, mean WER 0.921, exact match 0/16. Output is mostly standard-Bangla-looking text that does not match the Sylheti speech. See `reports/sylheti_asr_evaluation.md`.
   Exploratory single-run comparison (one speaker, no held-out set, so indicative only; usable / empty / rejected-garbage, mean CER of usable):
   turbo + bn + Bangla prompt 12/3/1, 0.82; turbo + bn 15/0/1, 0.69; turbo + auto language 16/0/0, 0.93; large-v3 + bn 16/0/0, 0.50.
   The hardcoded Bangla Whisper prompt produced empty transcripts, so it is now the optional `SPEECH_PROMPT` (default empty). Results also vary between runs.
2. **Gibberish passed as speech.** The Bangla-script check counted only script ratio, so transcripts containing a leaked Whisper token
   (`<|sq|>`) and invalid/unassigned code points were accepted. Fixed: `sanitize_asr_text` strips tokens/invalid characters and rejects text with
   many orthographically impossible words (0 false positives on all 16 references, standard references and 120 glossary rows). It cannot detect
   well-formed but wrong words; that is what patient confirmation is for.
3. **Own validation errors mislabelled as an outage.** `validate_bangla_script` ran inside the adapters' `try`, and the broad `except` turned
   `ASR_NON_BANGLA` / `NO_SPEECH_DETECTED` into "provider unreachable". Fixed (`raise_for_stt` re-raises `KothaError` unchanged).
4. **False negation counts.** `count_negations` treated every word ending in `নি` as a negation (`পানি`, `জানি`, `চুলকানি`, `খিঁচুনি`...). Fixed to past-tense
   negative verb endings with a stoplist; this removed false "negation_changed" results.
5. **False "invented symptom".** The patient's `মাথা বেদনা` (headache) was flagged because only `মাথাত বেদনা` was a known variant. Fixed: a symptom is accepted when
   every one of its words is the patient's own or produced by a glossary mapping of them. Real insertions (chest pain, vomiting) are still rejected.
6. **No glossary traceability.** Matches had no id. Added `glossary_id`, `matching_method`, `glossary_evidence`, `normalization_status`, per-change evidence ids.
7. **LLM outage blocked the patient** (the 404 seen in the UI). `normalize()` now falls back to the glossary-only proposal with a warning.
8. **Dataset label problem (not fixed, reported):** rec_015 and rec_016 declare durations 9.47 s / 15.87 s but the audio files are 15.87 s / 9.47 s, i.e. the two
   rows appear to point at each other's audio. The dataset is immutable here; the evaluator flags possible label mismatches as a diagnostic.
9. `syl_088` in the glossary CSV is not NFC-stable (precomposed `ড়`). Harmless: both glossary and text are NFC-normalised before matching.

## 5. Files added or modified
Added: `backend/app/services/dataset/{__init__,sylheti_audio_dataset,glossary_csv,metrics,evaluation}.py`; `backend/scripts/{validate,evaluate}_sylheti_dataset.py`;
tests `test_sylheti_audio_dataset.py`, `test_glossary_csv.py`, `test_sylheti_evaluation.py`, `test_normalization_safety.py`; docs; `reports/`.
Modified: `schemas/normalization.py`, `services/{glossary_service,dialect_normalizer,speech_to_text,grounding}.py`, `tests/test_stt_provider_errors.py`,
`backend/Dockerfile` (+ glossary CSV only), `.dockerignore`, `.gitignore`, `.env.example`, `README.md`. Glossary CSV moved to `data/glossary/`.

## 6. Not done / out of scope (be explicit)
- The LLM is not forced to emit `semantic_attributes_before/after`. Independent deterministic guards (negation, numbers/duration, symptoms,
  span existence, glossary-label checks) are used instead of trusting model-reported attributes.
- No ASR fine-tuning (16 clips from one speaker is not enough; explicitly out of scope).
- Frontend: the Transcribe page already shows the original transcript, normalization warnings and a typed fallback; no frontend files were changed in this task.
- Live browser microphone test and the Gemini LLM path were not re-verified here (see the final report).

## 7. Regression risks and how they are contained
- Guard changes (negation, invented symptom) affect every normalization: covered by `test_normalization_safety.py` and the existing guard tests; real-data replay shows
  0 negation-guard failures and 0 unsupported insertions on the 16 references.
- `sanitize_asr_text` could reject genuine speech: tested against every verified glossary sentence (must stay unchanged) and all 32 reference texts.
- The evaluation scripts are offline-only and are not imported by any request path; the app runs without the datasets installed.
