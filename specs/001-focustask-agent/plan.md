# Implementation Plan: FocusTask Agent

**Branch**: `feat/001-focustask-agent` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-focustask-agent/spec.md`

## Summary

ADHD-friendly audio-to-task pipeline: audio upload (file or mic) → async background job → faster-whisper transcription → Ollama LLM structuring → 3-section output (Direct Objective + Micro-Tasks Checklist + Execution Flow). Served via FastAPI with Gradio UI mounted at `/ui`; REST API at `/api`. Desktop companion script captures system + mic audio via WASAPI loopback, uploads to cloud API, polls for completion, copies output to clipboard. SQLite (via aiosqlite) persists completed TaskRecords; live ProcessingJob state is in-memory (dict + asyncio.Lock).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI 0.111+, Uvicorn, faster-whisper, ollama (Python SDK), Gradio 4.x, asyncpg, python-telegram-bot>=20.0, pydub, sounddevice, numpy, scipy, pyperclip, keyboard, python-multipart, pydantic-settings

**Runtime requirement**: ffmpeg must be available in PATH for OGG/OPUS → WAV conversion (included in Docker image)

**Storage**: External PostgreSQL via Supabase + asyncpg — connection pool configured via `DATABASE_URL` env var (Supabase Transaction pooler URL); in-memory dict for live ProcessingJob state. SQLite (aiosqlite) removed — superseded by FR-030.

**Testing**: pytest + pytest-asyncio; httpx AsyncClient for FastAPI route tests

**Target Platform**: HF Spaces (Linux, Docker, port 7860); Windows 11 (desktop script)

**Project Type**: web-service + desktop script

**Performance Goals**:
- Job ID returned within 5s of upload (SC-006)
- Full end-to-end for 1-min audio under 60s (SC-001)
- 45-min meeting audio processed within 10min from stop (SC-007)
- Job status updates visible within 5s of each stage change (SC-010)

**Constraints**:
- No paid APIs or cloud services for core pipeline
- HF Spaces free tier: SQLite removed; external PostgreSQL (Supabase) is persistent across deploys
- Telegram voice files: 20 MB max (Telegram Bot API limit); enforce at download step
- Max upload: 500MB hard limit enforced at FastAPI middleware
- Desktop script: Windows-only, no admin privileges required, no paid software
- Ollama must be running locally before API starts

**Scale/Scope**: Portfolio project, single-owner usage; estimated <100 jobs/day

## Constitution Check

Constitution file (`/.specify/memory/constitution.md`) contains only unfilled template placeholders — no governance rules defined. No gates to enforce.

Post-Phase 1 re-check: N/A — no rules to check against.

## Project Structure

### Documentation (this feature)

```text
specs/001-focustask-agent/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # REST API contract (Phase 1 output)
└── tasks.md             # Phase 2 output (created by /speckit-tasks, NOT by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app creation, Gradio mount, startup events
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py          # GET /api/health
│   │       ├── jobs.py            # POST /api/jobs, GET /api/jobs/{job_id}
│   │       └── tasks.py           # GET /api/tasks, GET /api/tasks/{task_id}
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # pydantic-settings, loads .env
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py            # aiomysql connection pool lifecycle + schema init
│   │   └── repository.py          # TaskRecord CRUD (MySQL queries + dataclass)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic request/response models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── whisper_service.py     # faster-whisper transcription (runs in ThreadPoolExecutor)
│   │   ├── ollama_service.py      # Ollama LLM → structured JSON; format="json" + retry
│   │   ├── job_runner.py          # Background job orchestrator; manages job dict + TTL
│   │   └── audio_converter.py     # OGG/OPUS → WAV conversion via pydub + ffmpeg
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── bot.py                 # python-telegram-bot Application setup + webhook registration
│   │   └── handlers.py            # voice_handler, audio_handler, error_handler
│   └── ui/
│       ├── __init__.py
│       └── gradio_app.py          # Gradio Blocks definition; mounts on FastAPI at /ui
├── requirements.txt
└── .env

desktop/
└── capture.py                     # WASAPI loopback + F9 hotkey + upload + poll + clipboard

tests/
├── __init__.py
├── conftest.py                    # AsyncClient fixture, test DB setup
├── test_health.py
├── test_jobs.py                   # Full job lifecycle (upload → poll → complete)
├── test_tasks.py                  # History + detail endpoints
├── test_whisper_service.py        # Unit: transcription with fixture audio
└── test_ollama_service.py         # Unit: JSON parsing + retry logic
```

**Structure Decision**: Web application with Gradio UI. FastAPI routes prefixed at `/api`. Gradio mounted at `/ui`. Telegram webhook at `POST /telegram/webhook`. One process, one port (7860 for HF Spaces, 8000 for local dev). Desktop script is standalone in `desktop/`. Tests at repo root `tests/`.

**New env vars** (added 2026-07-01):
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_WEBHOOK_URL` — public HTTPS URL for webhook (polling used as fallback in local dev)
- `DATABASE_URL` — asyncpg connection string (Supabase Transaction pooler: `postgresql+asyncpg://user:pass@host:6543/postgres`)
- `WEB_PANEL_BASE_URL` — base URL for task detail links in Telegram replies

## Complexity Tracking

> No constitution violations to justify.
