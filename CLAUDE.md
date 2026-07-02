<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at `specs/001-focustask-agent/plan.md`
<!-- SPECKIT END -->

# FocusTask Agent — Project Context for Claude

## What this project is

ADHD-friendly audio-to-structured-task pipeline. 

**Core flow**: audio upload or mic → faster-whisper (local) → Ollama LLM (local) → 3-section structured output (objective + checklist + flow) → copy to clipboard.

## Stack

- **Backend**: FastAPI + Uvicorn (`backend/app/main.py`)
- **Transcription**: faster-whisper (local, no API key needed)
- **LLM**: Ollama running locally (`ollama serve` + `ollama pull llama3:8b`)
- **Frontend**: Gradio 4.x mounted at `/ui` (`backend/app/ui/gradio_app.py`)
- **Database**: SQLite via aiosqlite (`focustask.db`)
- **Desktop capture**: `desktop/capture.py` (Windows WASAPI loopback + F9 hotkey)
- **Language**: Python 3.11+

## Project structure

```
backend/
  app/
    api/routes/   # health.py, jobs.py, tasks.py
    core/         # config.py (pydantic-settings)
    db/           # database.py (schema init), repository.py (CRUD)
    models/       # schemas.py (Pydantic models)
    services/     # whisper_service.py, ollama_service.py, job_runner.py
    ui/           # gradio_app.py (Gradio Blocks UI)
    main.py       # FastAPI app + middleware + router registration + Gradio mount
  requirements.txt
  .env / .env.example

desktop/
  capture.py        # WASAPI loopback + F9 hotkey + upload + poll + clipboard
  requirements.txt

specs/
  001-focustask-agent/
    spec.md         # Feature spec (7 user stories, 24 FRs, 10 SCs)
    plan.md         # Implementation plan
    tasks.md        # Task breakdown (35 tasks)
```

## Key constraints

- SQLite persistence (TaskRecords survive server restarts; in-flight jobs do not)
- Deployment target: HF Spaces free tier (port 7860, single process)
- PT-BR primary language, English secondary
- Windows-first for desktop capture (WASAPI loopback, no virtual audio cable)
- No paid software or API keys for core flow (all local)

## Common commands

```bash
# Install backend deps
cd backend && pip install -r requirements.txt

# Copy and edit env (set WHISPER_DEVICE=cpu if no GPU)
copy backend\.env.example backend\.env

# Run Ollama model (must be running before API starts)
ollama serve
ollama pull llama3:8b

# Start API + Gradio UI (local dev)
uvicorn backend.app.main:app --reload --port 8000
# Gradio UI: http://localhost:8000/ui
# REST API:  http://localhost:8000/api

# Desktop capture (Windows only)
cd desktop && pip install -r requirements.txt
python capture.py   # Press F9 to start/stop recording
```

## Active spec

`specs/001-focustask-agent/spec.md` — 7 user stories, 24 FRs, 10 success criteria. Read before implementing any new feature. Plan: `specs/001-focustask-agent/plan.md`.
