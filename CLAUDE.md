<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/001-focustask-agent/plan.md` (two-stage LLM pipeline + Obsidian
Markdown export — refined 2026-07-02). Supporting artifacts: research.md,
data-model.md, contracts/api.md, quickstart.md in the same directory.
<!-- SPECKIT END -->

# FocusTask Agent — Project Context for Claude

## What this project is

ADHD-friendly audio-to-structured-task pipeline.

**Core flow**: audio (web upload, mic, or Telegram voice note) → faster-whisper (local) → Gemini free tier (retry + fallback key) → 3-section structured output (objetivo + checklist + fluxo) → PostgreSQL job history + Telegram reply / web response.

A local Ollama path (`backend/app/services/ollama_service.py`) is kept as a dormant, interface-compatible fallback per constitution Principle I — not wired into the runtime today.

## Stack

- **Backend**: FastAPI + Uvicorn (`backend/app/main.py`)
- **Transcription**: faster-whisper (local, CPU int8, no API key needed)
- **LLM**: Gemini 2.5 Flash free tier (primary); Ollama dormant local fallback
- **Persistence**: PostgreSQL (asyncpg) — job history only, no accounts/sessions
- **Bot**: python-telegram-bot (voice notes → same pipeline)
- **Frontend**: Gradio (planned, for HF Spaces)
- **Language**: Python 3.11+

## Project structure

```
backend/
  app/
    api/        # FastAPI route handlers (health, transcribe, process)
    core/       # Config, settings (pydantic-settings + .env), event loop ref
    db/         # asyncpg pool, jobs table, repository functions
    models/     # Pydantic schemas (StructuredOutput enforces ADHD limits)
    services/   # whisper_service, gemini_service, ollama_service, job_runner
    telegram/   # Bot wiring + handlers
  tests/        # pytest — no live deps, services mocked at the boundary
  requirements.txt
specs/
  001-focustask-agent/   # spec.md, plan.md, tasks.md, research, contracts
.specify/
  memory/constitution.md # Project constitution (v1.0.1) — read before big changes
```

## Key constraints (see constitution for the authoritative version)

- Local-first, zero-cost core: transcription local; local LLM fallback must stay viable
- PostgreSQL persists job artifacts only — no user accounts, no sessions, no cross-job reads
- ADHD output limits are enforced in code (`schemas.py`): objetivo ≤30 words, checklist 3–10, fluxo 3–6
- PT-BR primary language; output matches input audio language
- Deployment target: HF Spaces free tier (CPU-only, ephemeral FS, cold starts)
- Windows-first for the desktop capture companion script (WASAPI loopback, no virtual cable)
- Tests must not require live LLM/PostgreSQL/network/audio — mock at the service boundary

## Common commands

```bash
# Install deps
pip install -r backend/requirements.txt

# Run API locally (from backend/ — app imports are rooted there)
cd backend && uvicorn app.main:app --reload --port 8000

# Run tests
cd backend && python -m pytest tests/ -v
```

Required `.env` (in `backend/`): `GEMINI_API_KEY` (and optional `GEMINI_API_KEY_FALLBACK`), `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`.

## Active spec

`specs/001-focustask-agent/spec.md` — user stories, functional requirements, success criteria. Read it before implementing any new feature. Workflow and quality gates: `.specify/memory/constitution.md`.
