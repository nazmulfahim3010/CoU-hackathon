# KOTHA (কথা) — Complete Sylheti Dataset Integration & Architecture Audit

**Date:** 2026-11-24  
**Author:** AI Systems Architect & Senior Software Engineering Review  
**Repository:** `CoU-hackathon` / Kotha Platform  

---

## 1. Executive Summary

Kotha (কথা) is an AI-assisted healthcare voice intake and documentation platform designed for Bangladesh's linguistically diverse population. This audit assesses the repository's current state, identifies the integration points for **Dataset A (16 Sylheti audio recordings + CSV)** and **Dataset B (120 curated Sylheti glossary entries)**, evaluates the end-to-end transcription and normalization pipelines, and provides a zero-regression implementation roadmap.

---

## 2. Current Application Architecture

The system operates as a client-server web architecture:

```
[Browser / Mobile / Desktop Web]
     │
     ├── Audio Recording (WebM/Opus @ 48kHz) or Manual Typed Input
     ├── Frontend UI (React 19 + TypeScript + Vite + Tailwind CSS 4)
     └── Session State Management (FlowContext.tsx)
     │
     ▼ (REST API / JSON / Multipart)
[FastAPI Backend Server (Python 3.14 / 3.12)]
     │
     ├── /api/session (SessionManager: 30-min in-memory TTL, zero disk persistence)
     ├── /api/transcription (Audio validation, FFmpeg conversion to 16kHz mono WAV, STT provider)
     ├── /api/transcription/typed (Manual Bengali / Banglish input + transliteration)
     ├── /api/normalization (Sylheti Glossary matching + LLM context-aware normalization)
     ├── /api/confirmation (Mandatory Patient/Helper Review Gate)
     ├── /api/clinical/extract (Clinician fields extraction from confirmed text)
     ├── /api/safety/evaluate (Deterministic keyword rules with negation detection)
     ├── /api/summary/generate (Bilingual Doctor Summary Card)
     └── /api/speech/generate (Procedural Bengali spoken guidance via TTS)
```

---

## 3. Existing Transcription Workflow & Speech Provider Audit

### 3.1 Configuration
- **Active Provider:** `openai_compatible` pointing to Groq's Whisper API (`https://api.groq.com/openai/v1/audio/transcriptions`).
- **Model:** `whisper-large-v3-turbo` (and `whisper-large-v3`).
- **Fallback Adapters:** Local Hugging Face Transformers (`local_transformers`), HF Inference API (`hf_inference`), and Demo sample cache.

### 3.2 Pre-processing & Audio Validation
- Raw browser recordings (`audio/webm;codecs=opus`) are converted via `ffmpeg` to 16 kHz mono signed 16-bit PCM WAV (`pcm_s16le`).
- Strict checks enforce duration $\ge 0.1\text{s}$ and $\le 90.0\text{s}$, with non-empty frame count.
- Temporary files are guaranteed deleted in `finally` blocks.

### 3.3 Root Cause of Previous Live STT 400 Failures
1. **Multipart Payload Parameter Handling:** Whisper OpenAI-compatible endpoints require `model`, `language="bn"`, `response_format="json"`, and file upload tuple `("recording.wav", audio_bytes, "audio/wav")`. Missing or invalid MIME types or excessive prompt characters previously led upstream gateways to return HTTP 400.
2. **Deterministic Script Validation:** Live recordings occasionally yield Latin or non-Bangla characters. Kotha strictly enforces `validate_bangla_script`: if $<50\%$ of alphabetic characters are Bengali script, it flags `ASR_NON_BANGLA` and prompts manual review or retake.

---

## 4. Existing Normalization Workflow & Glossary Implementation

### 4.1 Glossary Implementation
- The repository previously loaded terms from `backend/app/data/dialects/*.json`.
- The newly provided Dataset B (`data/glossary/sylheti_glossary_120-final.csv`) contains 120 verified entries with rich clinical audit metadata (`id`, `regional_expression`, `standard_bangla`, `english_meaning`, `dialect`, `category`, `example_sentence`, `source`, `contributor`, `verification_status`, `verified_by`, `verification_date`, `verification_note`).
- **Matching Mechanism:** Longest-match first with Bengali word boundary detection (`(?<![ঀ-৿])(?:...)(?![ঀ-৿])`), preventing sub-token corruption.

### 4.2 LLM Normalization & Guardrails
- **Prompt:** Instructs the LLM to standardize only dialect terms while strictly forbidding the addition of new symptoms or alteration of negation, numbers, or time expressions.
- **Deterministic Meaning Preservation Guards (`check_meaning_preservation`):**
  - **Negation Guard:** Tracks dialect negations (e.g. `নায়`, `নাই`, `করসিনা`, `খাইসিনা`) and ensures count consistency.
  - **Number/Duration Guard:** Protects quantities and duration units (e.g. `৩ দিন` $\leftrightarrow$ `তিন দিন`).
  - **Invented Symptom Guard:** Validates that clinical symptoms in the normalized text originate either from the patient's speech or from matched glossary entries. If a symptom was invented by the LLM, the output is rejected and the system falls back to deterministic glossary replacement.

---

## 5. Dataset Audit & Characteristics

### 5.1 Dataset A — Audio Corpus (`dataset/Audio_Record_and_Csv/` & `data/audio/sylheti/`)
- **Metadata File:** `sylheti_recordings_log_completeV2.csv`
  - Total records: 16 (IDs `rec_001` through `rec_016`).
  - Contains introductory label line `sylheti_recordings_log_complete` on line 0 before CSV header.
  - Speaker: Tonmoy (Male, 18-25).
  - Dialect: Sylheti.
  - Scenario cards: A1, A2, A3, B1, B2, B3, C1, C2.
- **Audio Files (`human_varified_audio.m4a/`):**
  - Total files: 16 `.wav` files.
  - All verified: Stereo (2 channels), 16-bit PCM, 48 kHz sample rate.
  - Durations range from 6.83s to 15.87s.
  - Discrepancy observed: `rec_015` audio duration is 15.87s (CSV says 9.47s), and `rec_016` audio duration is 9.47s (CSV says 15.87s) — values were inverted in the metadata log. The loader inspects the actual wave headers.

### 5.2 Dataset B — Curated Glossary (`data/glossary/sylheti_glossary_120-final.csv`)
- Total rows: 120.
- Unique IDs: 120 (`syl_001` to `syl_120`).
- Unique regional expressions: 120.
- All entries verified by named contributors (`Fahim`, `Noyon`).
- Categories: `symptom` (34), `common_medical` (24), `time_expression` (18), `body_part` (16), `pain_description` (9), `fever` (7), `severity` (5), and related.

---

## 6. Identified Missing Components & Implementation Plan

| Component | Status | Action Required |
| :--- | :--- | :--- |
| **Audio Dataset Loader** | Missing | Create `backend/app/services/dataset/sylheti_audio_dataset.py` with wave header inspection, CSV header skip, and Bengali Unicode support. |
| **Glossary CSV Service** | Partial | Enhance `backend/app/services/glossary_service.py` to natively parse `sylheti_glossary_120-final.csv` with full audit fields and caching. |
| **Dataset Validation Tool** | Missing | Create validation runner outputting `reports/sylheti_dataset_validation.json`. |
| **Evaluation Pipeline** | Missing | Implement `backend/scripts/evaluate_sylheti_dataset.py` measuring ASR CER/WER and Normalization semantic fidelity. |
| **Frontend Dataset Linking** | Partial | Ensure audio samples and glossary stats reflect the 120 verified entries and evaluation corpus without leaking raw filesystem paths. |

---

## 7. Safety, Privacy, and Regression Risks

1. **Patient Transcript Confidentiality:** Evaluation audio and reference logs must remain strictly segregated from the live patient session path.
2. **No Ground Truth Leaking:** Under no circumstances should reference transcripts be returned as live speech recognition results.
3. **Preservation of Existing Tests:** The existing 315 backend pytest suite and 36 frontend tests must remain passing with zero regressions.
