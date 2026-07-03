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

**Core flow**: audio upload or mic → faster-whisper (local) → Ollama LLM (local) → 3-section structured output (objective + checklist + flow) → copy to clipboard.

## Stack

- **Backend**: FastAPI + Uvicorn (`backend/app/main.py`)
- **Transcription**: faster-whisper (local, no API key needed)
- **LLM**: Ollama running locally
- **Frontend**: Gradio (planned, for HF Spaces)
- **Language**: Python 3.11+

## Project structure

```
backend/
  app/
    api/        # FastAPI route handlers
    core/       # Config, settings (pydantic-settings + .env)
    models/     # Pydantic request/response schemas
    services/   # Whisper service, LLM service, audio processing
  requirements.txt
specs/
  001-focustask-agent/
    spec.md     # Full feature spec with user stories, FRs, success criteria
```

## Key constraints

- Stateless — no DB, no user accounts, no persistence (v1)
- Deployment target: HF Spaces free tier (low traffic, portfolio)
- PT-BR primary language, English secondary
- Windows-first for the desktop capture companion script
- No paid software or API keys for core flow (all local)
- Desktop script uses Windows WASAPI loopback — no virtual audio cable required

## Common commands

```bash
# Run API locally
uvicorn backend.app.main:app --reload --port 8000

# Run Ollama (must be running before API starts)
ollama run llama3

# Install deps
pip install -r backend/requirements.txt
```

## Active spec

`specs/001-focustask-agent/spec.md` — covers all 5 user stories, 19 functional requirements, and 8 success criteria. Read it before implementing any new feature.
