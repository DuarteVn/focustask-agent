# FocusTask Agent

ADHD-friendly audio-to-task pipeline. Speak a work instruction — get a clean, structured task breakdown. No notes, no re-reading, no losing the thread.

Built as a Hugging Face Spaces portfolio project.

---

## What it does

1. **Upload audio or record live** — mp3, wav, ogg, m4a, webm, or browser mic
2. **Transcribe** via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (local, no API key)
3. **Filter noise** — removes filler words, self-corrections, tangents
4. **Structure output** via local LLM (Ollama) into three sections:
   - **Direct Objective** — one sentence, what must be delivered
   - **Micro-Tasks Checklist** — 3–10 specific, independently actionable steps
   - **Execution Flow** — input → logic → expected result
5. **Copy to clipboard** — paste into any task manager or team chat

### Bonus: Desktop Meeting Capture

A companion Python script captures system audio + microphone simultaneously (Windows WASAPI loopback, no paid software). Press `F9` to start/stop. Mixed audio is sent automatically to the API.

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI + Uvicorn |
| Transcription | faster-whisper (local) |
| LLM | Ollama (local) |
| Frontend | Gradio (HF Spaces) |
| Language | Python 3.11+ |

---

## Setup

```bash
# 1. Clone
git clone https://github.com/DuarteVn/focustask-agent.git
cd focustask-agent

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your Ollama model and settings

# 4. Start Ollama (must be running locally)
ollama run llama3

# 5. Run the API
uvicorn backend.app.main:app --reload
```

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── core/         # Config, settings
│   │   ├── models/       # Pydantic schemas
│   │   └── services/     # Whisper, LLM, audio processing
│   └── requirements.txt
└── specs/
    └── 001-focustask-agent/
        └── spec.md       # Full feature specification
```

---

## Target Audience

PT-BR speaking knowledge workers (managers, developers, team leads) who have or suspect ADHD. Primary language is Portuguese; English supported as secondary.

---

## Deployment

Target: Hugging Face Spaces (free tier). Stateless — no user accounts, no data stored.

---

## License

MIT
