# Kotha (কথা) — Every Voice Deserves to Be Understood

AI-assisted **dialect-to-clinical-note voice assistant** for rural Bangladeshi patients. A patient speaks in their own
Bangla dialect; Kotha transcribes, normalizes to standard Bangla, has the patient/helper **confirm** the text, extracts a
structured note, runs **deterministic red-flag rules**, and produces a bilingual (Bangla/English) doctor summary plus a
short spoken Bangla reply.

> **Kotha is not a diagnostic tool.** Medical decisions must be made by a qualified healthcare professional.
> This is a hackathon prototype, **not a certified medical system**. Nothing here has been clinically validated.

Built for CoU AI Hackathon 2026 (proposal: `Kotha.pdf`).

## Problem
Regional Bangla dialects (Sylheti, Chittagonian, Noakhali, …) differ in vocabulary and pronunciation. Clinicians work in
standard Bangla/English and can misread symptom words, body parts and durations. ASR is built mostly for standard Bangla.

## Features
| Module | What it does | Where |
|---|---|---|
| A. Voice recording | MediaRecorder capture, level meter, timer, 90 s cap, 30 s hint, preview/retake/discard, permission & unsupported-browser handling | `frontend/src/hooks/useRecorder.ts`, `pages/Intake.tsx` |
| B. Speech-to-text | Provider-independent STT adapters; no fake output when unconfigured | `backend/app/services/providers/stt.py` |
| C. Dialect normalization | Curated glossary + LLM with meaning-preservation guards (negation, numbers, duration units); falls back to glossary-only | `services/dialect_normalizer.py`, `data/dialects/*.json` |
| D. Confirmation gate | **Backend-enforced** workflow state; extraction/safety/summary/TTS return `409` until confirmed | `core/session_manager.py`, `api/routes/confirmation.py` |
| E. Extraction | Strict Pydantic schema (`reported / uncertain / not_reported`), validation + 3 attempts | `services/clinical_extractor.py`, `schemas/clinical.py` |
| F. Red-flag engine | Deterministic rules from JSON, explicit negation handling, no LLM | `services/red_flag_engine.py`, `data/safety_rules/rules.json` |
| G. Doctor summary | Bilingual toggle, red-flag panel, transcript comparison, copy, print/Save-as-PDF | `pages/Summary.tsx` |
| H. Bangla TTS | Template text (contains no patient data) → gTTS; honest failure state | `services/text_to_speech.py`, `components/SpokenReply.tsx` |

## Architecture
```
Browser (React/Vite/Tailwind) ──/api (Vite proxy)──▶ FastAPI
   record ─▶ POST /api/transcription ─▶ [STT adapter] ─▶ session(TRANSCRIBED)
          ─▶ POST /api/normalization ─▶ glossary + [LLM adapter] ─▶ session(NORMALIZED)
          ─▶ POST /api/confirmation  ─▶ patient-edited text ─▶ session(CONFIRMED)   ◀── mandatory gate
          ─▶ POST /api/clinical/extract (confirmed text only) ─▶ [LLM adapter]
          ─▶ POST /api/safety/evaluate  (deterministic rules, no LLM)
          ─▶ POST /api/summary/generate (deterministic assembly)
          ─▶ POST /api/speech/generate  (template text ─▶ gTTS)
```
Sessions are in-memory with a TTL (default 30 min). No database, no files, no audio retained. Extraction takes only a
`session_id`; the server uses the text stored at confirmation, so a client cannot bypass the gate or inject unconfirmed text.

## Run it
Requirements: Python 3.11+ (tested on 3.14), Node 20+.

```powershell
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          # add keys for live mode (optional for demo mode)
.venv\Scripts\python -m uvicorn app.main:app --port 8000
# API docs: http://localhost:8000/docs

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```
Microphone capture needs `localhost` or HTTPS.

### Configuration (`backend/.env`, never committed; keys never reach the browser)
| Variable | Values |
|---|---|
| `SPEECH_PROVIDER` | `none` \| `hf_inference` \| `openai_compatible` |
| `SPEECH_MODEL` | e.g. `bangla-speech-processing/BanglaASR` (HF) or `whisper-1` (OpenAI-compatible) |
| `SPEECH_API_KEY`, `SPEECH_BASE_URL` | key; optional base URL override |
| `LLM_PROVIDER` | `none` \| `anthropic` \| `openai_compatible` |
| `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL` | model id, key, optional base URL |
| `TTS_PROVIDER` | `gtts` \| `none` |

## Demo mode
Switch to **Demo samples** on the intake page. Three fictional scenarios: **A** ordinary symptoms (no alert),
**B** chest pain + breathing difficulty (rules trigger), **C** uncertain/incomplete info (unknowns stay "uncertain").
Demo mode is labelled on every screen. What is real in demo mode: glossary matching, the confirmation gate, red-flag
rules, summary assembly, TTS. What is **prepared**: the starting text (not speech recognition), the standard-Bangla
rewrite, and the structured extraction. Editing the text in demo mode makes the prepared extraction unavailable
(`409 DEMO_TEXT_EDITED`) rather than showing mismatched output; use live mode for edited text.

Native-speaker audio recordings were **not** available when this was built; none are bundled. Add verified clips with
transcripts before claiming any dialect is supported.

## Tests
```powershell
cd backend;  .venv\Scripts\python -m pytest -q      # 69 tests
cd frontend; npm test                               # 20 tests (vitest)
cd frontend; npm run build
```
Covered: audio validation, transcription responses, glossary matching, negation/duration preservation, confirmation
enforcement, extraction schema + retry, missing-info handling, red-flag trigger/non-trigger/negation, session expiry,
no files written, demo scenarios end to end through the API, recorder permission handling, confirmation flow,
loading/error states, summary rendering. Mobile layout was checked manually at 375 px.

## What was and was not verified
- **Verified in this build:** all of the above automated tests; the full demo flow through the real HTTP stack and browser
  UI; real Bangla TTS via gTTS (network call succeeded, audio returned); mobile layout at 375 px.
- **NOT verified (no credentials in the build environment):** live STT with any Hugging Face / OpenAI-compatible
  endpoint, and live LLM normalization/extraction. The adapters follow the providers' documented request formats and are
  unit-tested against scripted fake clients, but **have never run against a real provider**. Confirm model IDs, access,
  and rate limits before the demo. In particular, whether `bangla-speech-processing/BanglaASR` is served by the HF
  Inference endpoint for your account must be checked; if not, point `SPEECH_BASE_URL` at an OpenAI-compatible Whisper host.
- **No metrics claimed:** no word-error-rate, accuracy or clinical validation figures exist.

## Models, APIs, datasets, libraries
- **Speech-to-text (configurable, none bundled):** Hugging Face Inference API (default model id
  `bangla-speech-processing/BanglaASR`, a Whisper-based Bangla model — *unverified here*) or any OpenAI-compatible
  `/audio/transcriptions` endpoint (e.g. OpenAI `whisper-1`). No model is trained or fine-tuned.
- **LLM (configurable):** Anthropic Messages API or any OpenAI-compatible chat endpoint; used for normalization and extraction.
- **TTS:** gTTS (Google Translate TTS, unofficial; language `bn`). Receives only fixed template text.
- **Datasets:** none integrated. The proposal names RegSpeech12, Ben-10 and the Bangla Regional Dialects Speech Dataset
  as candidates for future adaptation; **none were used**, and their licences have not been checked here.
- **Glossary:** ~28 draft entries (Chittagonian, Sylheti, Noakhali) written by the AI coding assistant from general
  knowledge. **All are marked `unverified`** and need native-speaker review.
- **Red-flag rules:** draft keyword rules, `clinically_reviewed: false`. Must be reviewed against recognised triage
  guidance (e.g. WHO IMCI/ETAT, national guidelines) before any validity claim.
- **Libraries:** FastAPI, Pydantic, Uvicorn, httpx, python-multipart, gTTS, pytest; React, React Router, Vite, Tailwind CSS,
  Lucide, Vitest, Testing Library. Fonts: Inter, Hind Siliguri (Google Fonts).
- **AI coding assistant:** Claude Code (Anthropic, model Claude Sonnet 5.5) wrote and tested this codebase under human direction.

## Privacy & safety
- No persistent audio/transcripts; in-memory session data with TTL; `DELETE /api/session/{id}` clears immediately.
- Logs contain event names/ids only; no transcripts, audio or secrets. No analytics.
- Audio goes to the speech provider and text to the LLM provider you configure — review their data terms.
- LLM never decides alerts. Absence of an alert is never presented as safety. Guidance is limited to "seek urgent care".
- LLM normalization output is rejected (glossary-only fallback) if it changes negation, drops numbers or duration units.

## Known limitations
- No dialect has been tested with native speakers; zero-shot ASR on dialects is expected to be weak.
- Negation/guard heuristics are simple and Bangla-morphology-naive; rules are keyword-based and will miss paraphrases
  (they intentionally over-alert on ambiguous negation).
- Sessions are per-process memory (single server instance only).
- "Download as PDF" is the browser's Save-as-PDF via the print stylesheet.
- gTTS is an unofficial service and may rate-limit or fail; the UI then shows the text and an explicit error.
- Not a certified medical device; no regulatory review.

## Future work
Native-speaker verified glossary and test clips; dialect-adapted ASR on open dialect data (licence-checked); clinician
review of rules; WER and extraction-accuracy evaluation; offline/low-bandwidth mode; an official Bangla TTS provider.
