# Quickstart & Validation Guide: FocusTask Agent

**Generated**: 2026-06-22 | **Plan**: [plan.md](plan.md) | **API contract**: [contracts/api.md](contracts/api.md)

## Prerequisites

- Python 3.11+
- Ollama installed and running (`ollama serve` in a terminal)
- Model pulled: `ollama pull llama3:8b`
- CUDA-capable GPU recommended; CPU fallback works (slower)
- (Desktop capture only) Windows 11; `sounddevice`, `numpy`, `scipy`, `pyperclip`, `keyboard` installed

## Setup

```bash
# From repo root
cd backend
python -m venv .venv
.venv\Scripts\activate           # Windows
# or: source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt

# Configure environment
copy .env.example .env           # Windows
# or: cp .env.example .env       # Linux/macOS
# Edit .env: set WHISPER_DEVICE=cpu if no GPU

# Start API + Gradio UI
uvicorn app.main:app --reload --port 8000
```

- Gradio UI: `http://localhost:8000/ui`
- REST API: `http://localhost:8000/api`

---

## Validation Scenarios

### V-001: Health Check

```bash
curl http://localhost:8000/api/health
```

**Pass**: `{"status": "ok", "whisper": "ready", "ollama": "ready"}`

**Fail signals**: `"ollama": "unavailable"` → Ollama not running. Start `ollama serve`.

---

### V-002: Core Flow — File Upload → Poll → Retrieve

Requires a short PT-BR audio file (30–90s work instruction). Place test audio at `tests/fixtures/sample_pt.mp3`.

```bash
# Step 1: Upload
JOB=$(curl -s -X POST http://localhost:8000/api/jobs \
  -F "file=@tests/fixtures/sample_pt.mp3" | python -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB"

# Step 2: Poll (repeat until status == "complete")
curl http://localhost:8000/api/jobs/$JOB

# Step 3: Get task_id from complete job, then retrieve
TASK=$(curl -s http://localhost:8000/api/jobs/$JOB | python -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
curl http://localhost:8000/api/tasks/$TASK
```

**Pass criteria** (per spec):
- POST response arrives in <5s (SC-006)
- Status transitions visible: `received` → `transcribing` → `analyzing` → `complete`
- Full response has non-empty `objective` (≤30 words), `checklist` (3–10 items), `flow` with all 3 parts
- End-to-end completes in <60s for 1-min audio (SC-001)

---

### V-003: Verbal Noise Filtering

Upload an audio file containing filler phrases: "vê lá", "espera", "ah", "não, volta lá".

A suitable test: record yourself saying: *"Ah, espera. Então, vê lá com o fulano. Não, volta lá. O que precisamos é entregar o dashboard pro cliente até terça."*

**Pass criteria** (SC-004): None of the filler phrases appear in `objective`, `checklist`, or `flow` in the response. The output should contain only the actionable content.

---

### V-004: Task History

After V-002 completes:

```bash
curl http://localhost:8000/api/tasks
```

**Pass criteria**: Response includes the completed task with `objective` preview, `created_at`, and `detected_language`. Tasks ordered newest-first.

---

### V-005: Task Retrieval by URL (SC-009)

After V-002: note the `task_id`. Close and reopen browser or terminal session (simulate restart for SQLite persistence check — *do not restart the server for this test*; server restart wipes in-memory jobs but SQLite persists).

```bash
curl http://localhost:8000/api/tasks/<task_id_from_V002>
```

**Pass criteria**: Full 3-section output returned from SQLite without re-processing.

---

### V-006: Gradio UI Smoke Test

Open `http://localhost:8000/ui` in browser.

**Check in order**:
1. File upload panel is visible and accepts audio files
2. Upload `tests/fixtures/sample_pt.mp3` → status indicator appears ("Processing" or similar)
3. Status updates without page reload (SC-010)
4. After completion: output panel shows all 3 sections (Direct Objective, Micro-Tasks Checklist, Execution Flow)
5. Raw transcript is visible alongside structured output
6. Copy button places all 3 sections in clipboard with formatting intact (SC-004 proxy)

---

### V-007: File Size Rejection

```bash
# Generate a 600MB dummy file (Windows PowerShell)
$out = [System.IO.File]::OpenWrite("big.bin")
$out.SetLength(629145600)
$out.Close()

curl -X POST http://localhost:8000/api/jobs -F "file=@big.bin"
```

**Pass**: HTTP 413 with `{"error": "File exceeds 500MB limit"}`

---

### V-008: Unsupported Format Rejection

```bash
curl -X POST http://localhost:8000/api/jobs -F "file=@somefile.pdf"
```

**Pass**: HTTP 422 with `{"error": "Unsupported audio format. Accepted: mp3, wav, ogg, m4a, webm"}`

---

### V-009: Desktop Capture Script (Windows only)

```bash
cd desktop
pip install sounddevice numpy scipy pyperclip keyboard requests
python capture.py
```

**Steps**:
1. Script starts → press **F9** → terminal shows "Recording started (system audio + microphone)"
2. Play audio (YouTube, music, etc.) and/or speak for 30–60 seconds
3. Press **F9** again → terminal shows job ID and "Polling for result..."
4. Wait for completion → terminal shows "Output copied to clipboard"
5. Paste into any text editor

**Pass criteria** (SC-007, SC-008):
- `recording_<timestamp>.wav` file created locally
- Job ID displayed
- Structured Markdown output appears in clipboard within expected time
- No admin privileges required
- Local `.wav` preserved in all cases

**If "Stereo Mix" device not found**: script prints instructions to enable it in Windows Sound settings (Control Panel → Sound → Recording → Show Disabled Devices → Enable Stereo Mix).

---

### V-010: Stuck Job TTL

Start a job. Manually patch the `expires_at` to the past (dev-only endpoint or direct dict mutation in debug mode). Wait for TTL loop to fire (every 5 minutes).

**Pass**: Job status transitions to `failed` with `error_message = "Processing timeout after 30 minutes"`.

*Note*: This validation requires a test or debug hook; not testable via public API alone.
