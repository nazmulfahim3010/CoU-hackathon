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
