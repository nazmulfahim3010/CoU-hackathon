# Kotha (কথা) — Step-by-Step Claude Code Prompt Pack

Use this alongside `MASTER_PROMPT.md` (your master build prompt) and `Kotha.pdf`.
The master prompt is the **spec**. These prompts are the **execution order**: one focused job per prompt, each ending in tests and a stop point, so Claude Code never tries to build the whole product in one go.

---

## How to use this pack

1. **One prompt = one session chunk.** Paste a prompt, let Claude Code finish, check the result, commit, then move on.
2. **Run `/clear` between steps.** Each prompt tells Claude Code to re-read `CLAUDE.md` and the relevant docs, so it doesn't need old chat history. Clearing keeps it focused and cheaper.
3. **Use plan mode for big steps.** For Steps 1, 3, 6, 8 and 9, switch to plan mode first (Shift+Tab), review the plan, then approve.
4. **Commit after every green step.** `git add -A && git commit -m "Step N: ..."`. If a step goes badly, `git reset --hard` back to the last good one.
5. **Don't skip the "STOP and report" checks.** Read what Claude Code reports. If it says something failed or it used a fallback, fix that before moving on.
6. **Things only your team can provide** (Claude Code must not invent these):
   - Verified dialect glossary entries (from your native-speaker work).
   - Recorded test clips and their verified transcripts.
   - Red-flag rule review against triage guidance.
   - API keys in `backend/.env`.

---

## STEP 0 — Do this yourself before opening Claude Code

```bash
mkdir kotha && cd kotha
git init
mkdir -p docs demo_assets/audio
# Copy your files in:
#   docs/MASTER_PROMPT.md   ← the master build prompt
#   docs/Kotha.pdf          ← the proposal
#   demo_assets/audio/      ← your verified dialect test clips (.wav/.webm/.mp3)
#   demo_assets/transcripts.json ← verified transcripts for those clips (see format below)
```

Check you have: **Python 3.11+**, **Node 20+**, **ffmpeg** (`ffmpeg -version`), and **git**.

Suggested `demo_assets/transcripts.json` format (fill with YOUR verified data):

```json
[
  {
    "id": "sylheti_01",
    "audio_file": "sylheti_01.wav",
    "dialect": "sylheti",
    "speaker": "Fictional patient / consented volunteer",
    "original_transcript": "<verified dialect transcript>",
    "standard_bangla": "<verified standard Bangla version>",
    "verified_by": "<native speaker name/initials>",
    "scenario": "A_ordinary | B_red_flag | C_uncertain"
  }
]
```

Then create `CLAUDE.md` in the project root with this content. Claude Code reads this file automatically at the start of every session, so these rules apply to every step:

```markdown
# CLAUDE.md — Kotha (কথা)

## What this is
Kotha is a hackathon prototype: a dialect-to-clinical-note voice assistant for rural Bangladeshi patients.
Full spec: docs/MASTER_PROMPT.md. Product requirements: docs/Kotha.pdf. Architecture: docs/ARCHITECTURE.md.

## Stack
- backend/: Python 3.11, FastAPI, Pydantic v2, Uvicorn, pytest
- frontend/: React + TypeScript + Vite + Tailwind + React Router + Lucide, Vitest
- No database. In-memory, session-scoped state only.

## Non-negotiable rules
1. Kotha is NOT diagnostic. Never generate diagnoses, medication or treatment advice.
2. Workflow order is enforced by the BACKEND session state machine:
   CREATED → TRANSCRIBED → NORMALIZED → CONFIRMED → EXTRACTED → EVALUATED → SUMMARIZED.
   Clinical extraction must be impossible before CONFIRMED, even via direct API calls.
3. The red-flag engine is deterministic and rule-based. No LLM decides whether a rule fires.
4. Never store audio or transcripts on disk or in logs. Temp files are deleted in `finally`.
   Logs contain session IDs, stage names, timings, and error types only.
5. Never fake AI output. Demo mode is clearly labelled in the UI and API (`"mode": "demo"`).
   Live mode never returns canned responses. A manually typed transcript is labelled as typed.
6. Never mark a glossary entry, dialect, or safety rule as "verified" unless the team supplied that verification.
7. Missing information is "not_reported", never a negative finding.
8. No API keys in code or frontend. Use backend/.env (gitignored) and keep .env.example updated.
9. Never claim something works without running it. Run tests after every change.

## Commands
- Backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`
- Backend tests: `cd backend && pytest -q`
- Frontend: `cd frontend && npm run dev`
- Frontend tests/build: `cd frontend && npm run test -- --run && npm run build`

## Working style
- Small, focused changes. Don't rewrite working code without a reason.
- After each task: run tests, report what passed/failed, list any fallbacks used, then stop.
```

Commit: `git add -A && git commit -m "Step 0: docs and CLAUDE.md"`

Now start Claude Code inside the `kotha` folder: `claude`

---

## STEP 1 — Read everything, assess, and plan (no app code yet)

> Use plan mode for this step.

```text
Read CLAUDE.md, docs/MASTER_PROMPT.md and docs/Kotha.pdf completely. Also look at demo_assets/ to see what audio clips and verified transcripts we have.

Do NOT write application code in this step. Produce docs/ARCHITECTURE.md containing:

1. Repository assessment: what exists now, what is missing.
2. Technical architecture: frontend structure, backend structure (follow the layout in section 6 of the master prompt unless you justify a change), the AI pipeline, data flow per request, and the session state machine (CREATED → TRANSCRIBED → NORMALIZED → CONFIRMED → EXTRACTED → EVALUATED → SUMMARIZED) including which endpoint moves which state and the 30-minute session TTL.
3. AI model and API selection, with a provider-adapter design for: speech-to-text, LLM (normalization + extraction), and Bangla TTS. For each, list 2 candidate options and the fallback. Mark every model ID as "TO VERIFY" — we will verify each one in its own step before integrating it.
4. Safety architecture: confirmation gate, deterministic red-flag engine, no-storage guarantees, log redaction.
5. Implementation order (matching steps 2–16 of our plan: scaffold, session state machine, recording, STT, glossary+normalization, confirmation, extraction, red flags, summary, TTS, demo mode, UI polish, tests, README, final verification).
6. Critical risks and mitigations (dialect ASR accuracy, LLM hallucination, provider outage, Bangla font rendering, mic permissions on mobile/HTTP, time limit).
7. Exact commands to set up and run the project.

Then list any questions or blockers you have (e.g., missing API keys, missing demo data). Stop and report.
```

✅ **Check:** read `docs/ARCHITECTURE.md`. Make sure the state machine and "TO VERIFY" labels are there. Answer its questions. Commit.

---

## STEP 2 — Scaffold backend and frontend

```text
Read CLAUDE.md and docs/ARCHITECTURE.md.

Task: scaffold the project so both apps run. No AI features yet.

Backend (backend/):
- Python venv in backend/.venv, requirements.txt with pinned versions (fastapi, uvicorn[standard], pydantic, pydantic-settings, python-multipart, httpx, pytest, pytest-asyncio).
- app/main.py with CORS for the Vite dev origin, routers mounted under /api, OpenAPI docs enabled.
- app/config.py using pydantic-settings, reading backend/.env. Include: APP_MODE, SESSION_TTL_MINUTES, SPEECH_PROVIDER, SPEECH_MODEL, LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LLM_BASE_URL, TTS_PROVIDER, TTS_API_KEY, MAX_AUDIO_SECONDS=90, MAX_UPLOAD_MB.
- app/core/exceptions.py: typed app exceptions + handlers that return a consistent JSON error shape {error: {code, message}} without leaking internals.
- app/core/logging.py: structured logging with a redaction filter. Logs must never include transcripts, audio, or keys.
- GET /api/health returning status, app mode, and which providers are configured (true/false only, never key values).
- backend/.env.example with placeholders only; make sure .env is in .gitignore.
- tests/test_health.py.

Frontend (frontend/):
- Vite + React + TypeScript + Tailwind + React Router + Lucide.
- Load Inter and Hind Siliguri fonts. Bangla text gets a `font-bangla` class with line-height ≥ 1.7.
- Tailwind theme colors from the master prompt palette (deep teal #0F4C5C, primary #167D8D, bg #F5F8F8, text #18343B, warning #E5A000, emergency #C62828, success #21845B).
- A base layout (navbar with "Kotha কথা" logo text, footer with the disclaimer "Kotha is not a diagnostic tool. Medical decisions must be made by a qualified healthcare professional.").
- Routes with placeholder pages: / (Landing), /intake, /review, /confirm, /processing, /summary, /about.
- src/services/api.ts: a typed fetch wrapper with base URL from VITE_API_BASE_URL, timeout, and consistent error handling.
- Vitest + React Testing Library set up with one smoke test.

Verify: run backend tests, start the backend and hit /api/health, run the frontend build and tests. Stop and report results.
```

✅ **Check:** open `http://localhost:8000/docs` and `http://localhost:5173`. Commit.

---

## STEP 3 — Backend session state machine (the safety backbone)

> Use plan mode for this step.

```text
Read CLAUDE.md and docs/ARCHITECTURE.md.

Task: implement app/core/session_manager.py, the backend-enforced workflow. This is the most important safety feature, so build it before any AI.

Requirements:
- In-memory session store (dict + lock). No disk, no database.
- POST /api/session creates a session and returns {session_id, state, expires_at, mode}. mode is "live" or "demo" and is fixed for the session.
- States in order: CREATED → TRANSCRIBED → NORMALIZED → CONFIRMED → EXTRACTED → EVALUATED → SUMMARIZED.
- A helper like `require_state(session, allowed_states)` that raises a 409 Conflict with a clear error code (e.g. WORKFLOW_ORDER_VIOLATION) if a step is called out of order.
- Re-recording resets the session back to CREATED and wipes all downstream data.
- Editing after confirmation invalidates CONFIRMED and everything after it.
- Store per session: original transcript, transcript_source ("speech_recognition" | "demo_sample" | "typed_by_user"), normalized transcript, normalization notes, confirmed text, extraction, safety result, summary. All in memory only.
- TTL expiry (SESSION_TTL_MINUTES, default 30) with a background cleanup task, plus DELETE /api/session/{id} for explicit wipe at the end of a consultation.
- Session IDs are random UUID4s.

Tests (tests/test_session_workflow.py):
- Calling extraction, safety, or summary on a session that is not CONFIRMED returns 409.
- Skipping states is impossible.
- Editing after confirmation removes CONFIRMED.
- Expired sessions return 404/410 and their data is gone from memory.
- DELETE wipes the session.
- Use temporary stub endpoints for extract/evaluate if real ones don't exist yet, but keep the gate logic real.

Run pytest. Stop and report.
```

✅ **Check:** all workflow tests pass. Commit.

---

## STEP 4 — Module A: Patient voice recording UI

```text
Read CLAUDE.md. Build Module A from docs/MASTER_PROMPT.md section 4.

Task: the /intake page and a reusable `useAudioRecorder` hook.

Requirements:
- Use the MediaRecorder API. Pick a supported mime type at runtime (audio/webm;codecs=opus, then audio/mp4, then audio/ogg).
- Large Record / Stop buttons, recording timer, a live level meter or waveform using the Web Audio AnalyserNode.
- Hard stop at 90 seconds. Show a gentle note if the recording is under 30 seconds (recommended, not required).
- Audio preview player, then "Use this recording", "Record again" and "Discard" buttons.
- Handle: unsupported browser, permission denied, no microphone found, and insecure context (mic needs HTTPS or localhost). Each gets a clear simple-Bangla message plus a small English line.
- Simple Bangla instructions on the page, e.g. "বোতাম চাপুন এবং আপনার সমস্যার কথা নিজের ভাষায় বলুন।" Keep text large, buttons ≥ 48px tall, mobile-first.
- Optional patient fields: age group (infant under 1 year / child / adult / older adult / not stated). This is needed later by the infant fever rule. Don't require it.
- Dialect selector (Sylheti / Chittagonian / Noakhali / Standard / Not sure), marking any dialect we haven't tested as "পরীক্ষাধীন / not yet tested".
- Release mic tracks and revoke object URLs on stop/unmount. Keep the audio blob in memory only.
- A clear mode badge in the header area: "LIVE" vs "DEMO".

Write Vitest tests with mocked navigator.mediaDevices for: permission denied, recording start/stop, 90s auto-stop (fake timers), discard clears the blob.

Run the frontend tests and build. Stop and report.
```

✅ **Check:** test it in Chrome on your laptop and on a phone (phone needs HTTPS or a tunnel). Commit.

---

## STEP 5 — Module B: Speech-to-text service

```text
Read CLAUDE.md and docs/ARCHITECTURE.md. Build Module B.

First, VERIFY before coding. For each speech-to-text candidate in ARCHITECTURE.md, check and report: the exact model ID or API endpoint, whether it officially supports Bangla (bn), the input format it expects, whether it can run on this machine (CPU/GPU/RAM) or needs an API key, and licence. Prefer a Whisper model fine-tuned on Bangla from Hugging Face; keep the model configurable via SPEECH_MODEL. Tell me which you chose and why. Do not claim it handles Sylheti/Chittagonian/Noakhali well.

Then implement:
- app/services/speech_to_text.py with a `SpeechToTextProvider` interface and at least two adapters:
  1. Local Hugging Face Transformers pipeline (lazy-loaded once at startup or first use).
  2. An HTTP API adapter (OpenAI-compatible or HF Inference) as the alternative.
- Audio handling: validate type and size, convert to 16 kHz mono WAV with ffmpeg in a temp directory, reject empty/silent or >90s audio, delete temp files in `finally` (always).
- POST /api/transcription (multipart: session_id, audio, dialect_hint). Requires state CREATED. Returns {transcript, source: "speech_recognition", provider, model, duration_seconds, confidence|null, mode}. Only return confidence if the model genuinely provides it; otherwise null.
- Timeouts and provider errors return clean 502/504 errors with a Bangla-friendly message. Never return fake text on failure.
- Also add POST /api/transcription/typed for when ASR fails: the helper types the text, source becomes "typed_by_user", and the UI must label it that way.
- Frontend: after "Use this recording", upload, show a processing state ("আপনার কথা লেখা হচ্ছে..."), then route to /review. Handle errors with a retry option and the typed fallback.

Tests: invalid file type, empty audio, oversized audio, temp file deleted after success AND after failure, wrong session state → 409, provider failure → no fake transcript. Mock the provider in tests.

Run one REAL transcription using one of our clips in demo_assets/audio and report the actual output next to the verified transcript (honest comparison, no edits). Stop and report.
```

✅ **Check:** look at the real transcription vs your verified transcript. That gap is the problem your normalization step solves, so it's worth showing judges. Commit.

---

## STEP 6 — Module C: Dialect glossary + normalization engine

> Use plan mode for this step.

```text
Read CLAUDE.md. Build Module C from docs/MASTER_PROMPT.md.

Part 1: Glossary
- Create backend/app/data/dialects/{sylheti,chittagonian,noakhali,standard_bangla}.json and a Pydantic schema per entry: id, regional_expression, standard_bangla, english_meaning, dialect, category (body_part | symptom | pain_description | fever | time_expression | severity | common_medical), example_sentence, verification_status ("verified" | "unverified"), source, contributor.
- IMPORTANT: Do not invent "verified" entries. If I have provided glossary data (check docs/ and demo_assets/ for any glossary file), import it. Otherwise create a small number of clearly marked "unverified" example entries and a scripts/import_glossary.py that converts a CSV (columns matching the schema) into these JSON files, so my team can drop in our real 150–200 terms.
- app/services/glossary_service.py: load + validate at startup, normalize Unicode (NFC), and match multi-word expressions longest-first. Return matched spans with their entries.
- GET /api/glossary/stats: counts per dialect and verification status (used by the landing page to show tested vs unverified dialects honestly).

Part 2: Normalizer (app/services/dialect_normalizer.py)
- Pipeline: glossary matching → build an LLM prompt with matched glossary hints + few-shot examples taken ONLY from verified pairs in demo_assets/transcripts.json → LLM returns strict JSON: {normalized_text, changes: [{original, normalized, reason, source: "glossary"|"llm"}], uncertain_segments: [{text, reason}]}.
- Prompt rules: never add symptoms, never drop medical details, keep durations/numbers/severity, keep negation, keep uncertainty ("মনে হয়", "হয়তো"), don't diagnose.
- Deterministic post-checks after the LLM, no LLM involved:
  1. Negation check: count negation markers (না, নাই, নেই, নি, নয়, and dialect forms from the glossary) in original vs normalized; if they differ, flag it.
  2. Number/duration check: every digit and number word (Bangla and English digits, এক/দুই/তিন..., দিন/সপ্তাহ/মাস) in the original must survive.
  3. If a check fails: retry once with the specific failure in the prompt; if it still fails, return the output with a visible warning flag. Never silently pass it.
- POST /api/normalization (session_id). Requires TRANSCRIBED → moves to NORMALIZED. Returns original + normalized + changes + uncertain segments + warnings + mode.
- Put the LLM call behind an `LLMProvider` interface in app/services/llm_provider.py (we'll reuse it for extraction). Verify the chosen provider's model ID and JSON/structured-output support from its docs before using it, and report what you verified.

Tests: glossary longest-match, Unicode normalization, negation preserved, duration preserved, a mocked LLM that drops "না" gets caught, a mocked LLM that adds an invented symptom gets flagged (check: no new glossary symptom terms appear that weren't in the original), wrong state → 409.

Run one real normalization on a demo transcript and show the real output. Stop and report.
```

✅ **Check:** read the real normalized output carefully with a native speaker if you can. Commit.

---

## STEP 7 — Module D: Patient confirmation screen

```text
Read CLAUDE.md. Build Module D.

Frontend (/review → /confirm can be one page if cleaner):
- Show side by side (stacked on mobile): "আপনার কথা (মূল)" original transcript, and "প্রমিত বাংলা" normalized transcript.
- Highlight glossary-changed words and uncertain segments (with a tooltip/explanation on tap). Show normalization warnings prominently.
- Show the transcript source label: "Speech recognition", "Demo sample", or "Typed by helper".
- The message: "আপনার কথাগুলো আমরা বুঝে লিখেছি। অনুগ্রহ করে ভালোভাবে পড়ে দেখুন। কোনো ভুল থাকলে সংশোধন করুন।"
- Edit button makes the standard Bangla text editable (large textarea). Buttons: "ঠিক আছে, নিশ্চিত করছি" (Confirm), "আবার রেকর্ড করুন" (Record again).
- A checkbox the patient/helper must tick: "আমি পড়েছি এবং এটি সঠিক" before Confirm is enabled (UI convenience only; the backend is the real gate).

Backend:
- POST /api/confirmation (session_id, confirmed_text, edited: bool, confirmed_by: "patient" | "helper"). Requires NORMALIZED. Validates non-empty and length limits. Stores confirmed_text, moves to CONFIRMED. Re-running the normalization deterministic checks on edited text is fine, but never overwrite what the patient confirmed.
- Any later edit calls the same endpoint only from NORMALIZED; editing from a later state must first reset to NORMALIZED (clear downstream data).

Tests: backend confirmation happy path, empty text rejected, confirm twice behaves correctly, extraction blocked before confirm (direct API call). Frontend: edit then confirm sends edited text; Record again resets.

Run all tests. Stop and report.
```

✅ **Check:** try calling `/api/clinical/extract` directly in `/docs` before confirming. It must return 409. Commit.

---

## STEP 8 — Module E: Structured clinical extraction

> Use plan mode for this step.

```text
Read CLAUDE.md. Build Module E.

Schema (app/schemas/clinical.py, Pydantic v2, strict):
- A generic `ReportedField` with: status ("reported" | "not_reported" | "uncertain"), value_bn, value_en, evidence (exact quote from the confirmed transcript, required when status is reported or uncertain).
- ClinicalExtraction fields: chief_complaint, symptoms (list of items each with name_bn, name_en, status, duration, severity, evidence), symptom_duration, severity, medical_history, current_medications, allergies, associated_symptoms, negative_symptoms (only ones the patient explicitly denied, each with evidence), uncertain_or_missing (list of what a clinician should ask about), potential_red_flag_mentions (informational only — the safety engine does NOT use this).
- No diagnosis field. No treatment field.

Service (app/services/clinical_extractor.py):
- Uses the LLMProvider from Step 6 with structured JSON output.
- Input is ONLY the session's confirmed_text. Requires state CONFIRMED → moves to EXTRACTED.
- System prompt: extract only what is said; missing = not_reported; hedged = uncertain; never infer diagnosis; never fill gaps; give Bangla and English values.
- Validation after the LLM:
  1. Pydantic validation.
  2. Evidence check: every evidence string must actually appear in the confirmed text (after Unicode/whitespace normalization). Fields with fake evidence are downgraded to "uncertain" with a flag, or trigger the retry.
  3. A banned-content check: reject output containing diagnosis/prescription language (a small deterministic list of terms in Bangla and English, e.g. "diagnosis", "prescribe", "রোগ নির্ণয়", "ওষুধ খান").
- Controlled retry: up to 2 retries with the validation errors fed back; then return a clean 502 with code EXTRACTION_FAILED. Never return partial fabricated data.
- POST /api/clinical/extract (session_id).

Tests (mock the LLM): valid output passes; malformed JSON → retry then error; invented evidence → caught; missing info stays not_reported (not converted to negative); diagnosis language rejected; state gate enforced.

Run one real extraction on a confirmed demo transcript and show the real JSON. Stop and report.
```

✅ **Check:** compare the extraction against what the patient actually said. Commit.

---

## STEP 9 — Module F: Deterministic red-flag safety engine

> Use plan mode for this step.

```text
Read CLAUDE.md. Build Module F. This module must NOT call or depend on the LLM.

Rules file: backend/app/data/safety_rules/red_flags.json (or YAML), validated by a Pydantic schema. Each rule: rule_id, name_en, name_bn, trigger (terms_bn: list incl. dialect forms from the glossary, terms_en, optional required_context like age_group == "infant", optional co-occurrence like fever + infant), negation_window (tokens), alert_level ("emergency" | "urgent" | "caution"), explanation_bn, explanation_en, recommended_action_bn, recommended_action_en, review_status ("pending_clinical_review" | "reviewed"), reviewed_against (source text or null).

Starter rules (all marked pending_clinical_review until my team reviews them): chest pain, difficulty breathing, heavy bleeding, high fever in an infant (needs age_group == infant from intake), loss of consciousness/fainting, seizure/convulsion, severe dehydration signs, stroke-like signs (sudden face drooping/weakness/slurred speech), blood in vomit/stool, pregnancy with bleeding. Recommended actions only say to seek urgent care / go to the nearest health facility / call emergency services — never a medicine or treatment.

Engine (app/services/red_flag_engine.py):
- Input: the session's confirmed_text (standard Bangla) + intake fields (age_group). It may also scan the original dialect transcript for dialect trigger terms.
- Unicode normalization, longest-match term search, negation detection within the window (e.g. "বুকে ব্যথা নেই" must NOT trigger, but must be recorded as "explicitly denied").
- Output per rule: status "triggered" | "explicitly_denied" | "not_mentioned" | "insufficient_information" (e.g. fever mentioned but age not stated for the infant rule), with the matched text span and rule ID, so the clinician sees exactly why.
- Overall result always includes this statement: "No alert does not mean the patient is safe. Clinician assessment is required." (Bangla + English).
- POST /api/safety/evaluate (session_id). Requires EXTRACTED → moves to EVALUATED. GET /api/safety/rules lists all rules for transparency.

Tests: each starter rule triggers on a positive sentence; negated sentence doesn't trigger and shows explicitly_denied; not mentioned stays not_mentioned (never "absent"); infant fever with no age → insufficient_information; no LLM import anywhere in the engine (write a test that asserts the module doesn't import llm_provider); state gate enforced.

Run tests. Stop and report.
```

✅ **Check:** your team reviews `red_flags.json` against triage guidance and sets `review_status`. Commit.

---

## STEP 10 — Module G: Bilingual doctor summary dashboard

```text
Read CLAUDE.md. Build Module G.

Backend:
- app/services/summary_generator.py builds the summary DETERMINISTICALLY from the stored extraction + safety result + transcripts. No new LLM call here, so no new content can appear.
- Sections (bn + en): chief complaint, symptoms, duration, severity, medical history, medications taken, allergies (if reported), important negative symptoms, uncertain/missing information ("Ask about…"), red-flag alerts (with rule IDs and matched text), original patient statement, normalized statement, confirmed statement.
- Metadata: session timestamp, mode (live/demo), transcript source, providers/models used, and the label "AI-assisted patient intake summary — clinician verification required."
- POST /api/summary/generate (session_id). Requires EVALUATED → moves to SUMMARIZED.

Frontend (/summary — doctor-facing, information-dense):
- Red-flag panel at the top (emergency = red #C62828, urgent = amber #E5A000), each showing the rule, why it fired, and the recommended action. If none fired, show the "no alert ≠ safe" statement, not a green "safe" badge.
- Bangla/English toggle for the whole card.
- "Not reported" shown in muted grey; "uncertain" with an amber marker. Never show not_reported as "No".
- Transcript comparison panel (original / normalized / confirmed), collapsible.
- Extraction details panel showing evidence quotes for each field.
- Copy summary (plain text, both languages), Print (print stylesheet: hides nav/buttons, black-on-white, fits A4), Download PDF via window.print().
- "End session" button that calls DELETE /api/session/{id} and clears frontend state.
- Must be skimmable in about 30 seconds: clear hierarchy, short lines.

Tests: backend summary contains every section and the disclaimer; frontend renders the red-flag panel, toggles language, shows not_reported correctly. Run all tests and the build. Stop and report.
```

✅ **Check:** print preview the summary. Commit.

---

## STEP 11 — Module H: Bangla text-to-speech reply

```text
Read CLAUDE.md. Build Module H.

First VERIFY: for each TTS candidate in ARCHITECTURE.md, check its docs for Bangla voice support (bn-BD and/or bn-IN voice names), API format, auth, and limits. Report what you verified. Implement a `TextToSpeechProvider` interface with one cloud adapter plus a browser fallback.

Reply text:
- Built from a deterministic Bangla TEMPLATE (not the LLM), using the summary:
  1. "আপনার তথ্য ডাক্তারের কাছে পাঠানোর জন্য লেখা হয়েছে।"
  2. 1–3 things the doctor may ask about (taken from uncertain_or_missing).
  3. If any emergency/urgent rule fired: a calm instruction to seek urgent care at the nearest health facility now.
  4. "ডাক্তারই আপনার চিকিৎসার সিদ্ধান্ত নেবেন।"
- Never says a diagnosis was made. Short, simple words.

Backend: POST /api/speech/generate (session_id). Requires SUMMARIZED. Returns audio (base64 or streamed) + the exact text + provider. Audio is generated in memory, never written to disk persistently.

Frontend: a large Play/Pause button, Replay, and the spoken text shown on screen. If cloud TTS fails, try the browser's speechSynthesis only if a Bangla voice is actually available; otherwise show "ভয়েস চালানো যায়নি" with the text still visible. Never show a fake "playing" state.

Tests: template includes urgent-care line only when a rule fired, no diagnosis words, TTS failure handled. Run tests. Do one real TTS generation and report. Stop and report.
```

✅ **Check:** listen to it on a phone speaker. Commit.

---

## STEP 12 — Demo mode and the three scenarios

```text
Read CLAUDE.md. Build demo mode per section 9 of docs/MASTER_PROMPT.md.

- A mode switch in the UI (Live / Demo). Demo sessions are created with mode "demo" and carry a visible "DEMO — prepared sample" banner on every page and in every API response.
- Demo flow: pick a sample clip from demo_assets/ (list via GET /api/demo/samples; play it in the browser). The transcript comes from the team-verified transcript in demo_assets/transcripts.json with source "demo_sample" — never labelled as speech recognition.
- Optionally offer "Run live ASR on this sample" so judges can see real ASR output on the same clip, labelled as live.
- After transcription, demo mode uses the SAME real normalization, confirmation, extraction, safety, summary and TTS pipeline. If the LLM provider is unavailable, it may fall back to pre-saved outputs for that exact sample stored in demo_assets/cached_outputs/, which must be labelled "cached demo output" in the UI. Live mode never uses cached outputs.
- Make sure demo_assets has three fictional scenarios (ask me if I haven't provided them; do not invent dialect transcripts and label them verified):
  A: ordinary symptoms, no red flag.
  B: symptoms that trigger a red-flag rule.
  C: uncertain/incomplete information (hedged statements, missing duration).
- A script scripts/generate_demo_cache.py that runs the real pipeline on each sample and saves the outputs for the fallback, recording provider, model and timestamp.

Tests: demo responses always carry mode "demo"; live mode never reads cached outputs; scenario B triggers its rule; scenario C produces uncertain_or_missing items. Run tests. Run the full demo for all three scenarios and report what happened. Stop and report.
```

✅ **Check:** run all 3 scenarios yourself end to end. Commit.

---

## STEP 13 — Landing page, About page and UI polish

```text
Read CLAUDE.md. Polish the frontend so it looks like a credible healthcare product, not a generic AI dashboard. Mobile-first.

Landing page (/):
- Navbar with logo "Kotha কথা", links (How it works, Dialects, Privacy, About), and the CTA "Start Voice Consultation / পরামর্শ শুরু করুন".
- Hero: "Every Voice Deserves to Be Understood." plus "Your Voice. Your Language. Better Understanding." and a short Bangla line.
- The dialect problem in 3 short points (from docs/Kotha.pdf).
- How Kotha works: the 8-step flow as a simple visual (Record → Transcribe → Normalize → Confirm → Extract → Safety check → Doctor summary → Spoken reply).
- Supported dialects pulled live from GET /api/glossary/stats, with honest badges: "Tested with native speakers" vs "Not yet tested".
- Benefits for patients and for doctors. Privacy section (no storage, session-only). Medical disclaimer.

About page: problem, solution, safety design, team, credits (link to README).

Polish across all pages:
- A progress stepper across the patient flow.
- Consistent loading, empty, error and success states.
- Subtle transitions only (respect prefers-reduced-motion).
- Accessibility: proper labels, focus states, colour contrast AA, aria-live for status changes, keyboard usable.
- Check layouts at 360px, 768px and 1280px widths.

Run the build and tests. Take screenshots at the three widths if you can, and report any layout issues you fixed. Stop and report.
```

✅ **Check:** open it on your phone. Commit.

---

## STEP 14 — Full test pass and end-to-end test

```text
Read CLAUDE.md. Make the test suite complete against section 10 of docs/MASTER_PROMPT.md.

1. Review existing backend tests against the list in section 10 (audio validation, transcription validation, glossary matching, normalization output, negation preservation, duration preservation, confirmation enforcement, extraction schema, missing info handling, red-flag triggering and non-triggering, session expiry, no persistent patient data). Add what's missing. For "no persistent data": run a full workflow and assert no new files appear in the project or temp dirs, and that logs contain no transcript text.
2. Review frontend tests against section 10 and add what's missing.
3. Add Playwright E2E for the full sequence: (fake audio via Chrome's --use-fake-device-for-media-stream with a demo clip, or demo mode) → transcription → normalization → edit → confirm → extract → safety → bilingual summary → spoken reply. Mock external providers in E2E so it is reliable, and add one optional @live test that uses real providers.
4. Add a mobile viewport E2E run.

Run everything. Fix real failures (don't weaken tests to make them pass). Report the final counts: passed/failed/skipped per suite.
```

✅ **Check:** all green. Commit.

---

## STEP 15 — README and attribution

```text
Read CLAUDE.md, docs/ARCHITECTURE.md and the actual code. Write README.md per section 12 of docs/MASTER_PROMPT.md.

Include: overview, problem, solution, features, tech stack, a Mermaid architecture diagram, setup (backend + frontend), environment variables (matching .env.example), API reference (all endpoints, states they require, sample request/response), AI models and providers ACTUALLY integrated (exact model IDs and versions you verified), model limitations (especially dialect ASR), datasets actually used with licences (only list a dataset if we actually used it; otherwise list it under "Planned / reviewed, not integrated"), third-party libraries, AI coding assistant attribution (Claude Code by Anthropic, plus any others we tell you), demo instructions for the 3 scenarios, test results from Step 14, known limitations, privacy and safety design, future improvements.

Rules: no invented accuracy numbers, no claim of clinical validation, red-flag rules described with their real review_status. Read the code to confirm every claim. Stop and report.
```

✅ **Check:** read the README fully and add your team names. Commit.

---

## STEP 16 — Final verification and demo rehearsal

```text
Read CLAUDE.md. Final pre-demo verification. Do not add features.

1. Fresh-clone check: in a temp dir, clone the repo, follow the README setup exactly, and confirm it runs. Fix the README if any step is wrong.
2. Run all backend tests, frontend tests, the frontend production build, and the E2E suite.
3. Run all three demo scenarios in live mode and in demo mode. Confirm the mode labels are correct everywhere.
4. Safety checklist — verify each and report pass/fail with evidence:
   - Extraction endpoint returns 409 before confirmation (direct curl).
   - No audio/transcript files on disk after a full session; logs contain no patient text.
   - No API keys in the git history or frontend bundle (grep the dist/ folder and git log).
   - Every summary shows the clinician-verification label; every page shows the disclaimer.
   - No diagnosis or medication text appears anywhere in outputs.
   - Live mode never serves cached outputs.
5. Kill the LLM provider (wrong key) and confirm the app fails honestly and demo mode still works.
6. Write docs/DEMO_SCRIPT.md: a 3-minute judge walkthrough (problem → live recording → dialect vs standard comparison → correction → confirmation → red-flag scenario B → bilingual summary → spoken reply), plus a backup plan if Wi-Fi or a provider fails.

Report the full checklist results. Stop.
```

✅ **Check:** rehearse with the demo script at least twice. Final commit and tag: `git tag v1.0-demo`.

---

## Helper prompts (use any time)

**When something breaks:**
```text
Read CLAUDE.md. This is broken: <paste error / describe what you see>.
Steps to reproduce: <steps>. Expected: <x>. Actual: <y>.
Find the root cause before changing code. Explain the cause, then make the smallest fix, add a test that would have caught it, run the tests, and report.
```

**When Claude Code stopped halfway:**
```text
Read CLAUDE.md and run `git status` and `git diff`. We were in the middle of Step <N> (<name>). Tell me what's done and what's left, then finish the remaining items and run the tests.
```

**Check-in after any step:**
```text
Review the work from Step <N> against docs/MASTER_PROMPT.md and CLAUDE.md. List anything missing, any rule broken (especially safety, privacy, and honest labelling), and any test that is weak. Don't change code yet; just report.
```

**Running out of time (priority rule):**
```text
Read CLAUDE.md. We have <X> minutes left. Following the priority rule in section 11 of docs/MASTER_PROMPT.md, tell me what to cut and what to finish so the core flow (record → transcribe → normalize → confirm → extract → red flags → summary) works end to end. Then do only the must-finish items.
```

---

## Time map for the 5-hour final

| Hour | Steps |
|---|---|
| Before the final (prep days) | 0, 1, 2, 3, plus glossary data, clips, and rule review |
| Hour 1 | 4, 5 |
| Hour 2 | 6, 7 |
| Hour 3 | 8, 10 (summary can use mocked safety until Step 9) |
| Hour 4 | 9, 11, 12 |
| Hour 5 | 13 (light), 14, 15, 16 |

If the hackathon rules require all code to be written during the final window, do Steps 0–1 (docs, CLAUDE.md, architecture plan) beforehand and start coding at Step 2 when the clock starts.
