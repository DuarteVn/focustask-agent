# Data Model: FocusTask Agent

**Generated**: 2026-06-22 | **Plan**: [plan.md](plan.md)

## Entities

### ProcessingJob *(in-memory only — not persisted)*

Tracks the lifecycle of a background audio processing task. Stored in a module-level dict keyed by `job_id`, guarded by `asyncio.Lock`. Destroyed by TTL cleanup loop after 30 minutes.

| Field | Type | Notes |
|---|---|---|
| `job_id` | `str` (UUID4) | Primary key |
| `status` | `Enum` | `received` → `transcribing` → `analyzing` → `complete` \| `failed` |
| `created_at` | `datetime` (UTC) | Set on creation |
| `updated_at` | `datetime` (UTC) | Updated on each status change |
| `error_message` | `str \| None` | Populated on `failed` status |
| `task_id` | `str \| None` | Populated on `complete`; references `TaskRecord.task_id` |
| `expires_at` | `datetime` (UTC) | `created_at + 30min`; TTL loop marks job `failed` after this |

**State machine**:
```
received → transcribing → analyzing → complete
                                    ↘ failed (any stage)
```

**Uniqueness**: UUID4 generated at upload time; globally unique per process lifetime.

---

### TaskRecord *(persisted to SQLite)*

Immutable record of a successfully completed processing output. Written once on job completion; never updated.

| Field | Type | SQLite Column | Notes |
|---|---|---|---|
| `task_id` | `str` (UUID4) | `TEXT PRIMARY KEY` | Shareable URL key |
| `created_at` | `str` (ISO 8601 UTC) | `TEXT NOT NULL` | e.g., `2026-06-22T10:00:00Z` |
| `audio_duration_seconds` | `float \| None` | `REAL` | From audio metadata; null if undetectable |
| `raw_transcript` | `str` | `TEXT NOT NULL` | Full faster-whisper output |
| `detected_language` | `str` | `TEXT NOT NULL` | e.g., `pt`, `en` |
| `objective` | `str` | `TEXT NOT NULL` | Single-sentence direct objective |
| `checklist` | `str` (JSON) | `TEXT NOT NULL` | JSON-encoded `list[str]` |
| `flow_input` | `str` | `TEXT NOT NULL` | Execution flow: input |
| `flow_logic` | `str` | `TEXT NOT NULL` | Execution flow: logic |
| `flow_output` | `str` | `TEXT NOT NULL` | Execution flow: expected output |

**Shareable URL**: `GET /api/tasks/{task_id}` — full deployed URL is the shareable link (SC-009).

**Retention**: No automated cleanup in v1.

---

### TaskOutput *(computed — not stored as-is)*

Assembled from `TaskRecord` fields for API responses and Gradio display.

| Field | Source |
|---|---|
| `objective` | `task_records.objective` |
| `checklist` | `json.loads(task_records.checklist)` → `list[str]` |
| `flow` | `{input, logic, output}` assembled from `task_records.flow_*` |
| `raw_transcript` | `task_records.raw_transcript` |

---

### AudioInput *(transient — discarded after job completes)*

Uploaded audio file during processing. Temp file deleted after job reaches `complete` or `failed`.

| Field | Notes |
|---|---|
| `temp_file_path` | Absolute path; file in `TEMP_AUDIO_DIR` (env var) |
| `original_filename` | Sanitized original upload filename |
| `content_type` | MIME type from upload header |
| `size_bytes` | Validated ≤500MB at upload |

---

### DesktopCapture *(local to desktop script — never sent to API)*

Represents an active local recording session. Ephemeral struct; mixed output `.wav` is uploaded and preserved on failure.

| Field | Notes |
|---|---|
| `system_audio_device_id` | sounddevice device index for WASAPI loopback |
| `mic_device_id` | sounddevice device index for microphone input |
| `start_time` | Local datetime |
| `output_path` | `recording_<timestamp>.wav` — preserved on API failure (FR-019) |
| `sample_rate` | `16000` Hz (Whisper-optimal) |
| `channels` | `1` (mono, mixed down) |

---

## SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS task_records (
    task_id             TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    audio_duration_seconds REAL,
    raw_transcript      TEXT NOT NULL,
    detected_language   TEXT NOT NULL,
    objective           TEXT NOT NULL,
    checklist           TEXT NOT NULL,   -- JSON array of strings
    flow_input          TEXT NOT NULL,
    flow_logic          TEXT NOT NULL,
    flow_output         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_records_created_at
    ON task_records (created_at DESC);
```

Database file path: configured via `DB_PATH` env var (default: `./focustask.db`).

---

## Validation Rules

| Rule | Where enforced |
|---|---|
| Upload file ≤ 500MB | FastAPI middleware (before route handler) |
| Accepted MIME types: `audio/mpeg`, `audio/wav`, `audio/ogg`, `audio/mp4`, `audio/webm`, `video/webm` | `POST /api/jobs` route handler |
| Audio duration ≤ 2700s (45 min) | `job_runner.py` before invoking Whisper |
| `objective` ≤ 30 words | LLM prompt enforced; logged as warning if exceeded, not rejected |
| `checklist` min 1 item, max 20 items | `ollama_service.py` post-parse validation |
| Each checklist item non-empty string | `ollama_service.py` post-parse validation |
| `flow.input`, `flow.logic`, `flow.output` all non-empty | `ollama_service.py` post-parse validation |
