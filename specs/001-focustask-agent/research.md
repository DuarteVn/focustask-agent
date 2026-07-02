# Research: FocusTask Agent

**Generated**: 2026-06-22 | **Plan**: [plan.md](plan.md)

## Decision 1: Background Job Execution

**Decision**: ThreadPoolExecutor (2–4 workers) for CPU-bound Whisper + Ollama calls; asyncio.create_task for job orchestration; in-memory dict + asyncio.Lock for job state tracking.

**Rationale**: faster-whisper and Ollama calls are CPU/GPU-bound and not async-native. Running them via `loop.run_in_executor(thread_pool, ...)` keeps the FastAPI event loop unblocked while allowing concurrent processing. Job state stored in a module-level dict (`jobs: dict[str, ProcessingJob]`) guarded by `asyncio.Lock`. No external queue needed at portfolio scale (<100 jobs/day). A background TTL loop (`asyncio.create_task`) runs every 5 minutes to mark stuck jobs as failed.

**Alternatives considered**:
- **Celery + Redis**: Overkill — external broker unavailable on HF Spaces free tier
- **APScheduler**: Extra dependency; asyncio + ThreadPoolExecutor is sufficient and zero-dep
- **FastAPI BackgroundTasks**: No built-in status tracking; job state lost on server restart
- **Pure asyncio.create_task (no executor)**: Whisper blocks the event loop — unacceptable

**Trade-off accepted**: Server restart loses in-progress jobs (acceptable for v1 portfolio; SQLite preserves completed TaskRecords).

---

## Decision 2: Gradio + FastAPI Integration

**Decision**: Mount Gradio 4.x Blocks on FastAPI via `gr.mount_gradio_app(app, demo, path="/ui")`; FastAPI REST routes at `/api/*`.

**Rationale**: Gradio 4.x natively supports being mounted as a FastAPI sub-application. One process, one port — required for HF Spaces free tier (single service constraint). FastAPI routes at `/api` avoid path conflicts with Gradio's internal routes (`/file/`, `/queue/`, `/run/`). For HF Spaces deployment, run on port 7860.

**Known issue mitigated**: Gradio's internal routes (`/api/`) conflict with a top-level `/api` prefix. Resolution: use `/api` for REST (FastAPI registers first) and let Gradio handle `/ui/*`. Tested pattern confirmed in Gradio 4.x docs.

**Alternatives considered**:
- **Separate processes (nginx reverse proxy)**: Not viable on HF Spaces free tier (single port); adds ops complexity
- **Pure Gradio app**: Cannot expose clean REST endpoints needed by desktop script

---

## Decision 3: SQLite + Async

**Decision**: `aiosqlite` for async SQLite; raw SQL with Python dataclasses (no ORM); DB file at path from `DB_PATH` env var.

**Rationale**: aiosqlite wraps sqlite3 with asyncio compatibility, is purpose-built, and has zero friction. Raw SQL keeps dependency surface minimal for a 1-table schema. SQLite is appropriate for HF Spaces free tier (ephemeral disk; acceptable for portfolio with no uptime SLA). UUIDs as primary keys — generated with `uuid.uuid4()`.

**Alternatives considered**:
- **SQLAlchemy async**: Adds boilerplate and ORM overhead for a single-table schema
- **SQLModel**: Heavier dependency; overkill for this scope
- **sqlite3 + run_in_executor**: Works but aiosqlite is cleaner

---

## Decision 4: LLM Output Format Enforcement

**Decision**: Ollama `format="json"` parameter + system prompt specifying exact JSON schema → `json.loads()` parse → strip markdown code block wrappers → retry up to 2 times on JSONDecodeError.

**Rationale**: Ollama ≥0.1.9 supports `format="json"` which biases the model toward valid JSON output. llama3:8b has weak JSON schema adherence (known limitation) — mitigated by an explicit system prompt that names the three required keys and their types. Strip ` ```json … ``` ` wrappers before parsing (llama3 frequently outputs markdown code blocks even in JSON mode). Two retries with progressively stricter prompt language cover edge cases.

**Expected JSON schema from LLM**:
```json
{
  "objective": "Single sentence, ≤30 words, stating what must be delivered",
  "checklist": ["Step 1", "Step 2", "..."],
  "flow": {
    "input": "What enters the process",
    "logic": "What is processed or decided",
    "output": "Expected result or deliverable"
  }
}
```

**Fallback**: If 2 retries fail, mark job as `failed` with error "LLM output could not be parsed after 2 retries".

**Alternatives considered**:
- **Prompt-only Markdown headers**: Brittle; model-dependent formatting variance; harder to parse reliably
- **OpenAI function calling**: Not available in Ollama's Llama3 without additional tooling

---

## Decision 5: WASAPI Loopback Audio Capture (Desktop)

**Decision**: `sounddevice` library for audio capture; `numpy` for real-time channel mixing; `scipy.io.wavfile` for WAV export at 16kHz mono (Whisper-optimal).

**Rationale**: sounddevice has native WASAPI support on Windows, requires no admin privileges, and has a clean Python API. Loopback device selected by scanning `sd.query_devices()` for names containing "Stereo Mix" or "What U Hear" (Windows built-in WASAPI loopback). Both streams (system + mic) captured simultaneously in separate threads; mixed to mono by averaging and normalizing.

**Important**: "Stereo Mix" may be disabled by default in Windows Sound settings. Desktop script prints actionable instructions if device not found.

**Alternatives considered**:
- **PyAudio**: Unmaintained (last release 2017); WASAPI loopback support fragile on Windows 11
- **pyaudiowpatch**: PyAudio fork with WASAPI loopback support; viable alternative if sounddevice issues arise
- **Virtual audio cable (VB-Cable etc.)**: Paid software — violates SC-008

---

## Decision 6: Upload Size + Duration Enforcement

**Decision**: 500MB max file size enforced at FastAPI middleware (`RequestSizeLimitMiddleware`); audio duration checked post-upload via file metadata before transcription starts.

**Rationale**: 45-min uncompressed WAV (stereo, 44.1kHz, 16-bit) ≈ 450MB; compressed formats (mp3 @ 128kbps) ≈ 43MB. 500MB covers uncompressed edge cases. Duration check uses `mutagen` or `ffprobe` for metadata (no full decode). Files exceeding 45 minutes rejected with clear error before Whisper is invoked.

**Alternatives considered**:
- **Client-side enforcement only**: Not enforceable from API perspective
- **Reject uncompressed WAV**: Too restrictive — WAV is primary desktop capture output format

---

## Decision 7: Job TTL for Stuck Jobs

**Decision**: 30-minute TTL per ProcessingJob; background asyncio task (`asyncio.create_task`) checks every 5 minutes and marks expired jobs as `failed` with `error_message = "Processing timeout after 30 minutes"`.

**Rationale**: 45-min recording takes ≤10 min to process (SC-007). 30-min TTL gives 3× headroom. Background checker is a simple `while True: await asyncio.sleep(300)` loop started at FastAPI startup. No external scheduler needed.

**Alternatives considered**:
- **No TTL**: Stuck jobs accumulate memory indefinitely
- **Per-job asyncio.wait_for**: Harder to implement with ThreadPoolExecutor; TTL loop is simpler
