# Kotha (কথা) — System Architecture & Technical Specification

> **Hackathon Prototype Specification**  
> **Target Event:** CoU AI Hackathon 2026 | Phase 1 Idea Proposal (`Kotha.pdf`)  
> **Domain:** Healthcare & Accessibility  
> **Core Mandate:** Dialect-to-clinical-note voice assistant for rural Bangladeshi patients. **Kotha is NOT a diagnostic tool.** Medical decisions are strictly reserved for qualified clinicians.

---

## 1. Repository Assessment

A grounded evaluation of the repository state as of November 22, 2026:

### 1.1 What Exists Now
* **Backend Architecture & Code (`backend/app/`)**:
  * Scaffolded FastAPI application with routers for health, transcription, normalization, confirmation, extraction, safety, summary, and speech.
  * In-memory TTL session management (`app/core/session_manager.py`) tracking stages `CREATED` through `SUMMARIZED`.
  * Deterministic safety engine (`app/services/red_flag_engine.py`) with rule definitions in `app/data/safety_rules/rules.json`.
  * Dialect glossaries for Chittagonian, Noakhali, Sylheti, and Standard Bangla in `app/data/dialects/*.json`.
  * Normalization service (`app/services/dialect_normalizer.py`) with meaning-preservation checks (negation counting, numeral preservation).
  * Clinical extraction service (`app/services/clinical_extractor.py`) using Pydantic schemas with evidence quoting.
  * TTS integration (`app/services/text_to_speech.py`) using `gTTS` with deterministic non-clinical Bangla templates.
  * Backend test suite: 6 test files covering confirmation gates, extraction, normalization, red flags, sessions, and inputs.
* **Frontend Architecture & Code (`frontend/src/`)**:
  * React 18 + Vite + TypeScript + Tailwind CSS structure.
  * Audio recording hook (`useRecorder.ts`) using browser `MediaRecorder` API with Web Audio API `AnalyserNode` level visualization and 90-second hard cap.
  * Pages: Landing (`/`), Intake (`/intake`), Transcribe (`/transcribe`), Confirm (`/confirm`), Processing (`/processing`), Summary (`/summary`), About (`/about`).
  * In-memory context state (`FlowContext.tsx`) with zero localStorage/cookie retention.
  * Frontend test suite: Vitest test specifications (`frontend/src/test/app.test.tsx`).
* **Demo Scenarios (`backend/app/data/demo/scenarios.json`)**:
  * Three predefined scenarios:
    * **Scenario A (Ordinary)**: Headache and mild fever; no red flags triggered.
    * **Scenario B (Red Flag)**: Chest pain and breathing difficulty; triggers emergency rule.
    * **Scenario C (Uncertain/Incomplete)**: Intermittent abdominal pain with unstated duration and unknown fever; preserves "uncertain" status.
  * *Note*: These scenarios contain synthetic, illustrative text; they are not verified native speaker field recordings.

### 1.2 What Is Missing / Deficits
* **Native Dialect Audio & Verified Transcripts (`demo_assets/`)**:
  * The `kotha/demo_assets` directory is empty. No `.wav`, `.webm`, or `.mp3` native speaker test recordings exist.
  * No `demo_assets/transcripts.json` with field-verified dialect-to-standard-Bangla transcript pairs exists.
* **Runtime Environments**:
  * `backend/.venv` is not created; Python dependencies in `backend/requirements.txt` are not installed.
  * `frontend/node_modules` is not installed (`npm install` has not been run).
* **Environment Configuration & API Credentials**:
  * `backend/.env` is absent (only `.env.example` exists). Live speech recognition (Hugging Face / OpenAI-compatible) and LLM providers are unconfigured (`SPEECH_PROVIDER=none`, `LLM_PROVIDER=none`).
* **Root Specification Files**:
  * `CLAUDE.md` is missing at the repository root (its specification was defined in `Kotha_Claude_Code_Prompts.md`).
  * `docs/MASTER_PROMPT.md` is missing from the workspace.
  * `docs/Kotha.pdf` is located in `kotha/docs/Kotha.pdf` rather than `docs/Kotha.pdf`.

---

## 2. Technical Architecture

### 2.1 Frontend Structure
The frontend is a single-page application built on Vite, React 18, TypeScript, and Tailwind CSS.
```
frontend/
├── index.html                  # HTML entrypoint, Hind Siliguri & Inter fonts
├── package.json                # Dependencies: React Router, Lucide React, Vitest
├── vite.config.ts              # Proxy config: /api -> http://localhost:8000
├── src/
│   ├── main.tsx                # React DOM mount
│   ├── App.tsx                 # BrowserRouter & Route configuration
│   ├── App.css / index.css     # Tailwind imports, typography, font-bangla rules
│   ├── types/
│   │   └── api.ts              # Strict TypeScript interfaces matching backend schemas
│   ├── state/
│   │   └── FlowContext.tsx     # In-memory session and patient data state provider
│   ├── services/
│   │   └── api.ts              # Typed fetch API client (error handling, abort timeouts)
│   ├── hooks/
│   │   └── useRecorder.ts      # Audio capture, VU analyzer, 90s timer, permission state
│   ├── layouts/
│   │   └── AppLayout.tsx       # Navbar, brand logo, mode badge, disclaimer footer
│   ├── pages/
│   │   ├── Landing.tsx         # Problem context, workflow visual, disclaimer, CTA
│   │   ├── Intake.tsx          # Audio recording, dialect selector, demo scenario picker
│   │   ├── Transcribe.tsx      # ASR progress indicator and typed text fallback
│   │   ├── Confirm.tsx         # Side-by-side original/normalized comparison & patient edit
│   │   ├── Processing.tsx      # Extraction and safety rule evaluation progress
│   │   ├── Summary.tsx         # Doctor summary dashboard (bilingual toggle, red flags)
│   │   └── About.tsx           # Architecture, safety disclosures, ethics
│   ├── components/
│   │   ├── ui.tsx              # Button, Card, Badge, Modal, Input components
│   │   └── SpokenReply.tsx     # Spoken Bangla playback widget with TTS fallback
│   └── test/
│       ├── app.test.tsx        # Vitest UI flow, permission, and rendering tests
│       └── fixtures.tsx        # Mock API data fixtures
```

### 2.2 Backend Structure
The backend follows Section 6 of the project design, implementing clean separation of routing, domain models, services, and external adapters:
```
backend/
├── requirements.txt            # FastAPI, Uvicorn, Pydantic v2, httpx, gTTS, pytest
├── .env.example                # Sample environment template
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI initialization, CORS, global error handlers
│   ├── config.py               # Pydantic Settings (TTL, providers, timeouts, origins)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # Dependency injection for SessionManager & Settings
│   │   └── routes/
│   │       ├── health.py         # GET /api/health (system status & provider readiness)
│   │       ├── transcription.py   # POST /api/transcription, /api/transcription/typed
│   │       ├── normalization.py   # POST /api/normalization (glossary + LLM)
│   │       ├── confirmation.py    # POST /api/confirmation (patient gate)
│   │       ├── extraction.py      # POST /api/clinical/extract (structured clinical schema)
│   │       ├── safety.py          # POST /api/safety/evaluate (deterministic rules)
│   │       ├── summary.py         # POST /api/summary/generate (bilingual dashboard data)
│   │       └── speech.py          # POST /api/speech/generate (Bangla TTS synthesis)
│   ├── core/
│   │   ├── exceptions.py       # KothaError and FastAPI exception handlers
│   │   ├── logging.py          # Redacting logger (no patient transcripts or audio logged)
│   │   ├── security.py         # Audio container signature checks & byte validation
│   │   └── session_manager.py  # In-memory TTL state machine with Stage gates
│   ├── data/
│   │   ├── demo/
│   │   │   └── scenarios.json  # Prepared demo scenarios (A, B, C)
│   │   ├── dialects/
│   │   │   ├── chittagonian.json
│   │   │   ├── noakhali.json
│   │   │   ├── sylheti.json
│   │   │   └── standard_bangla.json
│   │   └── safety_rules/
│   │       └── rules.json      # Deterministic red-flag keyword & context rules
│   ├── schemas/
│   │   ├── clinical.py         # ClinicalExtraction, ReportedField, Confirmation
│   │   ├── normalization.py    # NormalizationResponse, GlossaryMatch
│   │   ├── safety.py           # SafetyResponse, RuleResult
│   │   ├── summary.py          # SummaryCard, SummarySection
│   │   └── transcription.py    # TranscriptionResponse
│   └── services/
│       ├── clinical_extractor.py # LLM extractor with quote evidence validation
│       ├── demo_data.py          # Scenario loader
│       ├── dialect_normalizer.py # Hybrid glossary + LLM normalizer with guards
│       ├── glossary_service.py   # Longest-prefix Trie/Regex glossary matcher
│       ├── red_flag_engine.py    # Rule evaluator with clause-level negation handling
│       ├── summary_generator.py  # Deterministic bilingual note synthesizer
│       ├── text_to_speech.py     # gTTS client with fixed patient-safe templates
│       └── providers/
│           ├── llm.py            # Anthropic & OpenAI-compatible LLM adapters
│           └── stt.py            # Hugging Face & OpenAI-compatible STT adapters
└── tests/
    ├── conftest.py             # Pytest fixtures and mock session factories
    ├── test_confirmation_gate.py # Verification of strict 409 gating before confirmation
    ├── test_extraction.py      # Schema compliance, evidence checks, retry logic
    ├── test_input_and_providers.py # Audio container validation, provider error wrapping
    ├── test_normalization.py   # Negation preservation, numeral preservation
    ├── test_red_flags.py       # Rule triggers, explicit negation, absence handling
    └── test_sessions_and_e2e.py # End-to-end flow, TTL expiration, session deletion
```

### 2.3 The AI Pipeline
The system integrates AI where necessary for comprehension while restricting AI where clinical safety is critical:
```
[ Patient Voice (Dialect) ]
           │
           ▼
[ Speech-to-Text Adapter ] ──(Transcription: Regional dialect speech to text)
           │
           ▼
[ Dialect Normalizer ] ─────(Curated Glossary longest-match + LLM guided rewrite)
           │                 └─ Meaning-preservation guards (negation & numbers)
           ▼
[ PATIENT CONFIRMATION ] ───(MANDATORY GATE: Patient/helper edits & confirms)
           │
           ├─────────────────────────────────────────┐
           ▼                                         ▼
[ Clinical Extractor (LLM) ]           [ Deterministic Red-Flag Engine ]
  - Pydantic schema validation           - Zero LLM involvement
  - Exact evidence quoting checks        - JSON rules + Negation window
  - Banned diagnostic language filter    - Emergency / Urgent classifications
           │                                         │
           └───────────────────┬─────────────────────┘
                               ▼
               [ Bilingual Summary Generator ]
                 - Deterministic data merge
                 - English & Bangla Doctor Card
                               │
                               ▼
               [ Bangla Spoken Reply (TTS) ]
                 - Fixed reassurance & triage template
                 - gTTS synthesis (no patient data sent)
```

### 2.4 Data Flow per Request

| Step | Endpoint | Method | Input | Processing | Output / State Transition |
|---|---|---|---|---|---|
| 1 | `/api/transcription` | `POST` | Audio file (multipart) OR `demo_scenario_id` (Form) | Audio validated (magic bytes, size); STT adapter transcribes audio OR scenario loaded; in-memory session created. | Returns transcript, `session_id`, `mode`. Session state: `CREATED` → `TRANSCRIBED`. |
| 1b | `/api/transcription/typed` | `POST` | `session_id`, typed text | Manual text entry if ASR fails; tagged as `typed_by_user`. | Returns transcript. Session state: `TRANSCRIBED`. |
| 2 | `/api/normalization` | `POST` | `session_id` | Requires `TRANSCRIBED`. Glossary matching applied; LLM performs standard Bangla rewrite; negation/number guards verified. | Returns normalized text, changes, uncertain spans. State: `TRANSCRIBED` → `NORMALIZED`. |
| 3 | `/api/confirmation` | `POST` | `session_id`, `confirmed_text`, `confirmed` (bool) | Requires `NORMALIZED`. Compares confirmed text with normalized; stores confirmed text; invalidates downstream extractions. | Returns confirmed status. State: `NORMALIZED` → `CONFIRMED`. |
| 4 | `/api/clinical/extract` | `POST` | `session_id` | Requires `CONFIRMED`. Clinical extractor calls LLM with confirmed text; validates schema and quote evidence. | Returns `ClinicalExtraction` JSON. State: `CONFIRMED` → `EXTRACTED`. |
| 5 | `/api/safety/evaluate` | `POST` | `session_id` | Requires `CONFIRMED`. Deterministic red-flag engine scans confirmed text against rule patterns with negation window. | Returns `SafetyResponse` with triggered rules. State: `EXTRACTED` → `SAFETY_EVALUATED`. |
| 6 | `/api/summary/generate` | `POST` | `session_id` | Requires `SAFETY_EVALUATED`. Assembles doctor summary card deterministically without LLM. | Returns bilingual `SummaryCard`. State: `SAFETY_EVALUATED` → `SUMMARIZED`. |
| 7 | `/api/speech/generate` | `POST` | `session_id` | Requires `SUMMARIZED`. Selects pre-scripted Bangla template (reassurance + urgent care if flagged); synthesizes audio via gTTS. | Returns base64 audio and template text. |
| 8 | `/api/session/{id}` | `DELETE` | `session_id` (Path) | Explicit consultation termination; purges session from memory immediately. | 204 No Content. |

### 2.5 Session State Machine
The workflow enforces a strict linear progression. Calling an endpoint prematurely raises HTTP `409 Conflict`.

```
                  ┌─────────────┐
                  │   CREATED   │ (0)
                  └──────┬──────┘
                         │ POST /api/transcription (or /api/transcription/typed)
                         ▼
                  ┌─────────────┐
                  │ TRANSCRIBED │ (1)
                  └──────┬──────┘
                         │ POST /api/normalization
                         ▼
                  ┌─────────────┐
                  │ NORMALIZED  │ (2)
                  └──────┬──────┘
                         │ POST /api/confirmation  ◄── MANDATORY GATE
                         ▼
                  ┌─────────────┐
        ┌─────────┤  CONFIRMED  ├─────────┐
        │ (Edit)  └──────┬──────┘         │
        │                │ POST /api/clinical/extract
        │                ▼                │
        │         ┌─────────────┐         │
        │         │  EXTRACTED  │ (4)     │
        │         └──────┬──────┘         │
        │                │ POST /api/safety/evaluate
        │                ▼                │
        │         ┌─────────────┐         │
        │         │  EVALUATED  │ (5)     │
        │         └──────┬──────┘         │
        │                │ POST /api/summary/generate
        │                ▼                │
        │         ┌─────────────┐         │
        │         │ SUMMARIZED  │ (6)     │
        │         └──────┬──────┘         │
        │                │                │
        └────────────────┴────────────────┘
     Re-confirming or editing invalidates downstream states
```

* **Session Lifetime (TTL)**: 30 minutes (`session_ttl_seconds = 1800`).
* **Storage Invariant**: In-memory dictionary `self._sessions: dict[str, Session]`.
* **State Invalidation Rule**: If `/api/confirmation` is called with edited text after extraction or summary was already run, all downstream keys (`extraction`, `safety`, `summary`) are purged from memory, forcing re-execution on verified text only.

---

## 3. AI Model & API Selection (Provider-Adapter Design)

Every provider adapter implements a typed `Protocol`. Model IDs are marked **TO VERIFY** and will be verified individually against active provider endpoints before integration.

### 3.1 Speech-to-Text (STT)
* **Candidate 1**: `bangla-speech-processing/BanglaASR` via Hugging Face Inference API [TO VERIFY]
  * *Characteristics*: Fine-tuned Whisper model specifically trained on Bangla Common Voice and regional speech corpora.
  * *Input format*: 16 kHz Mono WAV or WebM audio bytes.
  * *Authentication*: `HF_TOKEN` (`Bearer` header).
* **Candidate 2**: `openai/whisper-large-v3` via Groq / OpenAI-compatible endpoint [TO VERIFY]
  * *Characteristics*: High inference speed on cloud LPUs/GPUs; broad multilingual base including standard Bangla (`bn`).
  * *Input format*: Multipart audio upload (`/audio/transcriptions`).
  * *Authentication*: API Key via `Authorization: Bearer <KEY>`.
* **Fallback Strategy**:
  1. Manual typing fallback: `POST /api/transcription/typed` where the community health worker or patient types what was said (tagged `source: "typed_by_user"`).
  2. Demo mode: Prepared synthetic scenarios with pre-loaded transcripts (`source: "demo_prepared_text"`).

### 3.2 Large Language Model (Normalization & Clinical Extraction)
* **Candidate 1**: `claude-3-5-sonnet-20241022` via Anthropic Messages API [TO VERIFY]
  * *Characteristics*: Exceptional reasoning, complex multilingual instruction-following (Bangla dialect nuances), strict adherence to structured JSON schemas without hallucinating banned fields.
  * *Authentication*: `x-api-key` header with `anthropic-version: 2023-06-01`.
* **Candidate 2**: `gpt-4o-mini` (or `llama-3.3-70b-versatile`) via OpenAI-compatible API [TO VERIFY]
  * *Characteristics*: High speed, low cost, built-in JSON mode (`response_format: {"type": "json_object"}`).
  * *Authentication*: Standard Bearer token authentication.
* **Fallback Strategy**:
  1. Normalization Fallback: Deterministic glossary-only term replacement (`glossary_service.py`) without LLM paraphrase.
  2. Extraction Fallback: Prepared scenario clinical extraction JSON (`scenarios.json`) in demo mode, or clean `502 Provider Unavailable` error state in live mode.

### 3.3 Bangla Text-to-Speech (TTS)
* **Candidate 1**: `gTTS` (Google Translate TTS Python package, `lang="bn"`) [TO VERIFY]
  * *Characteristics*: Lightweight, zero-credential requirement, official support for standard Bangla pronunciation, outputs standard MP3 stream.
* **Candidate 2**: Azure Cognitive Services Speech (`bn-BD-PradeepNeural` / `bn-BD-NabanitaNeural`) [TO VERIFY]
  * *Characteristics*: High-fidelity natural neural voices specifically tailored to Bangladeshi Bangla dialect/accent.
* **Fallback Strategy**:
  1. Browser Web Speech API (`window.speechSynthesis`) querying for available `bn-BD` or `bn-IN` system voices.
  2. UI Visual Display Fallback: Rendering the exact Bangla template text clearly on-screen with an explicit badge: "ভয়েস চালানো যায়নি (Voice unavailable)".

---

## 4. Safety Architecture

```
   ┌─────────────────────────────────────────────────────────────────┐
   │                       SAFETY ARCHITECTURE                       │
   ├───────────────────────────────┬─────────────────────────────────┤
   │ 1. Mandatory Confirmation Gate│ 2. Deterministic Red Flags      │
   │    Backend 409 enforcement    │    Zero LLM involvement         │
   │    Extraction blocked prior   │    Clause-bounded negation      │
   │    Client cannot bypass       │    No alert ≠ Safe statement    │
   ├───────────────────────────────┼─────────────────────────────────┤
   │ 3. Strict No-Storage Invariant│ 4. Structured Log Redaction     │
   │    Zero database persistence  │    Transcripts strictly banned │
   │    30-min TTL in memory only  │    Audio bytes never logged     │
   │    Audio temp deleted finally │    Tokens/Keys never logged     │
   └───────────────────────────────┴─────────────────────────────────┘
```

### 4.1 Confirmation Gate
* **Backend Enforcement**: Extraction (`/api/clinical/extract`), safety evaluation (`/api/safety/evaluate`), and summary generation (`/api/summary/generate`) strictly require `Stage.CONFIRMED`.
* **Direct Call Prevention**: A malicious client or direct API consumer attempting to bypass the UI to extract data from an unconfirmed transcription receives an immediate `409 Conflict` (`CONFIRMATION_REQUIRED`).
* **Source Tracking**: Any edits made during confirmation are flagged (`edited_by_patient: true`). If text is modified, all previous extractions are automatically invalidated and cleared from memory.

### 4.2 Deterministic Red-Flag Engine
* **No LLM Dependency**: Safety-critical red flags are calculated purely via deterministic keyword matching and context rules loaded from `rules.json`.
* **Clause-Bounded Negation Handling**:
  * A negation term (e.g., "না", "নাই", "নেই", "নয়", "নি") only suppresses a flag if it occurs within a window of **3 tokens** following the term within the same clause (delimited by punctuation: `,`, `;`, `।`, `.`, `?`, `!`, `\n`).
  * If a symptom is mentioned both with negation and affirmatively elsewhere, the engine triggers the alert (safety-first approach).
* **Contextual Triggering**: Certain rules (e.g., infant fever) require intake metadata (`age_group == "infant"`). If fever is mentioned but age is unstated, the engine records `insufficient_information`.
* **Universal Disclaimer**: Every safety evaluation outputs:  
  * *Bangla*: "কোনো সতর্কতা না থাকার অর্থ এই নয় যে রোগী নিরাপদ। এটি রোগীর কথার ওপর নির্ধারিত নিয়মভিত্তিক পরীক্ষা, চিকিৎসা মূল্যায়ন নয়।"  
  * *English*: "No alert does NOT mean the patient is safe. Alerts are keyword rules over what the patient said, not a clinical assessment. Kotha is not a diagnostic tool."

### 4.3 No-Storage Guarantees
* **Ephemeral Memory Only**: The application operates without a database (no SQLite, Postgres, Redis, or disk caching).
* **Audio Handling**: Audio files sent to `/api/transcription` are validated in memory; any temporary files created for transcoding (e.g. ffmpeg conversion) are wiped inside `finally` blocks immediately after processing.
* **Session TTL**: Sessions automatically expire after 30 minutes. Explicit session termination via `DELETE /api/session/{id}` wipes all data immediately from memory.

### 4.4 Log Redaction
* Structured logging via `app.core.logging.get_logger`.
* Logs are strictly restricted to: timestamp, log level, logger name, session ID prefix (first 6 characters), stage transitions, HTTP status codes, and provider error types.
* **Prohibited in Logs**: Patient audio, raw transcripts, normalized transcripts, clinical summaries, and API keys.

---

## 5. Implementation Order (Steps 2–16)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        IMPLEMENTATION PHASES                           │
├─────────┬──────────────────────────────┬───────────────────────────────┤
│ Phase   │ Steps                        │ Deliverables                  │
├─────────┼──────────────────────────────┼───────────────────────────────┤
│ Phase 1 │ Step 2: Scaffold             │ Backend venv, Frontend Vite,  │
│         │ Step 3: Session State Machine│ health checks, 409 gates      │
├─────────┼──────────────────────────────┼───────────────────────────────┤
│ Phase 2 │ Step 4: Voice Recording (A)  │ MediaRecorder UI, VU meter    │
│         │ Step 5: Speech-to-Text (B)   │ STT adapter, audio validation │
├─────────┼──────────────────────────────┼───────────────────────────────┤
│ Phase 3 │ Step 6: Normalization (C)    │ Glossaries, LLM rewrite, check│
│         │ Step 7: Confirmation Gate (D)│ Review screen, edit & confirm │
├─────────┼──────────────────────────────┼───────────────────────────────┤
│ Phase 4 │ Step 8: Extraction (E)       │ Clinical Pydantic schema, LLM │
│         │ Step 9: Red-Flag Engine (F)  │ Deterministic rule evaluator  │
├─────────┼──────────────────────────────┼───────────────────────────────┤
│ Phase 5 │ Step 10: Doctor Summary (G)  │ Bilingual dashboard card      │
│         │ Step 11: Spoken Reply (H)    │ Bangla TTS template synthesis │
├─────────┼──────────────────────────────┼───────────────────────────────┤
│ Phase 6 │ Step 12: Demo Mode           │ Scenarios A, B, C; fallbacks  │
│         │ Step 13: UI Polish           │ Typography, mobile-first, a11y│
├─────────┼──────────────────────────────┼───────────────────────────────┤
│ Phase 7 │ Step 14: Full Test Suite     │ Unit, regression, E2E checks  │
│         │ Step 15: README & Credits    │ Documentation, model tables   │
│         │ Step 16: Final Verification  │ Demo rehearsal, safety audit  │
└─────────┴──────────────────────────────┴───────────────────────────────┘
```

1. **Step 2 — Scaffold**: Set up `backend/.venv`, pin requirements, configure FastAPI CORS, create Vite + Tailwind frontend base with Inter & Hind Siliguri fonts.
2. **Step 3 — Session State Machine**: Build `app/core/session_manager.py` with in-memory lock, random UUIDs, 30-minute TTL cleanup, and `require_state` 409 exception handling.
3. **Step 4 — Voice Recording (Module A)**: Implement `useRecorder` hook (MediaRecorder, WebM/Opus, 90s cap, 30s hint, VU meter) and `/intake` UI with dialect selector.
4. **Step 5 — Speech-to-Text (Module B)**: Verify STT candidate models; implement `STTProvider` adapter with magic byte validation, audio conversion, and typed manual entry fallback.
5. **Step 6 — Glossary + Normalization (Module C)**: Load dialect JSON glossaries (Sylheti, Chittagonian, Noakhali); build LLM normalizer with deterministic negation & number preservation guards.
6. **Step 7 — Patient Confirmation (Module D)**: Implement `/confirm` screen showing original vs normalized text, highlighting changes; enforce backend transition to `CONFIRMED`.
7. **Step 8 — Clinical Extraction (Module E)**: Implement Pydantic schema for reported/uncertain/not_reported fields; build LLM extractor with quote evidence verification and anti-diagnosis filters.
8. **Step 9 — Red-Flag Safety Engine (Module F)**: Implement deterministic `red_flag_engine.py` without LLM; evaluate rules against confirmed text with clause-bounded negation logic.
9. **Step 10 — Doctor Summary Dashboard (Module G)**: Implement deterministic summary generator; create `/summary` responsive view with red-flag alert banners, language toggle, and print/PDF styling.
10. **Step 11 — Bangla TTS Spoken Reply (Module H)**: Implement template-based reassurance and urgent triage voice reply via `gTTS`; handle browser speech synthesis fallback.
11. **Step 12 — Demo Mode**: Integrate prepared scenarios A (ordinary), B (red flag), and C (uncertain) with clear badges across UI and API.
12. **Step 13 — UI Polish**: Accessibility audit (WCAG AA), Bangla typography line-height (`leading-loose` ≥ 1.7), responsiveness across 360px, 768px, and 1280px widths.
13. **Step 14 — Full Test Suite**: Execute backend pytest (69+ tests) and frontend Vitest (20+ tests); verify no persistent files and zero patient text in logs.
14. **Step 15 — README & Attribution**: Document models, limitations, verified vs unverified dialects, team credits, and setup instructions.
15. **Step 16 — Final Verification**: Run fresh-clone dry run, rehearse 3-minute judge demo script, execute security and safety verification checklists.

---

## 6. Critical Risks & Mitigations

| Risk | Impact | Concrete Mitigation |
|---|---|---|
| **Dialect ASR Failure** | Foundation models produce high WER on Sylheti, Chittagonian, and Noakhali. | 1. Prominent confirmation screen where patient/helper can review and edit.<br>2. Typed text fallback (`POST /api/transcription/typed`).<br>3. Prepared demo mode with verified dialect transcripts for reliable presentation. |
| **LLM Hallucination / Diagnostic Creep** | LLM invents symptoms or offers medical advice/diagnoses. | 1. Extraction schema explicitly lacks diagnosis/treatment fields.<br>2. Every reported symptom requires exact quote evidence from the confirmed text.<br>3. Deterministic regex filter rejects banned clinical advice terms.<br>4. Prominent medical disclaimers on every view. |
| **Provider Outage / Latency** | Cloud APIs time out during live demonstration. | 1. Strict timeouts (default 60s) returning clean 504/502 errors.<br>2. Provider-independent architecture allowing instant failover.<br>3. Self-contained demo mode using pre-computed scenario outputs. |
| **Bangla Font / Conjunct Rendering** | Regional conjuncts (যুক্তাক্ষর) render improperly or clip on mobile. | 1. Load Google Font `Hind Siliguri` explicitly.<br>2. Apply `font-bangla` class enforcing `line-height: 1.7` (`leading-loose`) across all Bangla text containers.<br>3. Run NFC Unicode normalization on all strings. |
| **Microphone Permissions on Mobile/HTTP** | Browser blocks audio recording on non-HTTPS origins. | 1. Clear dual-language UI alert explaining HTTPS/localhost requirements.<br>2. Support file upload as an alternative to live recording.<br>3. Pre-loaded demo scenarios requiring zero microphone access. |
| **Hackathon 5-Hour Time Limit** | Scope creep leads to unfinished core flow. | 1. Strict adherence to the linear step-by-step plan.<br>2. Prioritize thin end-to-end vertical slice over complex model fine-tuning.<br>3. Use existing working modules rather than rewriting functional code. |

---

## 7. Setup & Execution Commands

### 7.1 Backend Setup & Execution
Run in PowerShell from the repository root:
```powershell
# 1. Navigate to backend directory
cd backend

# 2. Create Python virtual environment
python -m venv .venv

# 3. Activate virtual environment
.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt

# 5. Initialize environment variables
copy .env.example .env
# Edit .env to configure API keys (if running live mode)

# 6. Run backend test suite
pytest -q

# 7. Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```
* Backend API documentation available at: `http://localhost:8000/docs`

### 7.2 Frontend Setup & Execution
Run in a separate PowerShell terminal:
```powershell
# 1. Navigate to frontend directory
cd frontend

# 2. Install Node dependencies
npm install

# 3. Run frontend unit tests
npm test

# 4. Start Vite development server
npm run dev
```
* Web application available at: `http://localhost:5173`

---

## 8. Open Questions & Blockers

1. **Absence of Native Speaker Audio Assets (`demo_assets/audio/`)**:
   * *Status*: BLOCKER for live dialect evaluation.
   * *Impact*: The `demo_assets` directory is currently empty. No native speaker audio clips or team-verified transcripts exist.
   * *Required Action*: The team must provide at least 2–3 `.wav`/`.webm` recordings with corresponding native speaker transcripts to populate `demo_assets/transcripts.json`.
2. **Missing Live API Keys (`backend/.env`)**:
   * *Status*: BLOCKER for live STT and live LLM extraction.
   * *Impact*: In the absence of API keys, the system operates exclusively in demo mode or falls back to typed input.
   * *Required Action*: Provide credentials for Hugging Face Inference (`SPEECH_API_KEY`) and Anthropic/OpenAI (`LLM_API_KEY`).
3. **Model Availability Verification**:
   * *Status*: PENDING VERIFICATION.
   * *Impact*: `bangla-speech-processing/BanglaASR` on Hugging Face Inference must be checked for active endpoint hosting, cold-start latency, and accepted audio formats before live reliance.
