# API Contract: FocusTask Agent REST API

**Version**: v1 | **Auth**: None (public)

**Base URLs**:
- Local dev: `http://localhost:8000`
- HF Spaces: `https://<space-name>.hf.space`

**Content type**: JSON responses; `multipart/form-data` for uploads.

**Error format** (all non-2xx responses):
```json
{ "error": "Human-readable description" }
```

---

## Health

### `GET /api/health`

**Response 200**:
```json
{
  "status": "ok",
  "whisper": "ready",
  "ollama": "ready"
}
```

If Ollama unreachable, `"ollama"` is `"unavailable"` (still 200 — service is up, dependency is degraded).

---

## Jobs

### `POST /api/jobs`

Upload audio file; start background processing job. Returns immediately (HTTP 202) with job ID.

**Request**: `multipart/form-data`

| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | binary | yes | Audio file; max 500MB; accepted formats: mp3, wav, ogg, m4a, webm |

**Response 202**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "received",
  "created_at": "2026-06-22T10:00:00Z"
}
```

**Response 413** — file too large:
```json
{ "error": "File exceeds 500MB limit" }
```

**Response 422** — unsupported format:
```json
{ "error": "Unsupported audio format. Accepted: mp3, wav, ogg, m4a, webm" }
```

---

### `GET /api/jobs/{job_id}`

Poll job processing status. Call repeatedly until `status` is `complete` or `failed`.

**Path param**: `job_id` — UUID4 string returned from `POST /api/jobs`

**Response 200** — in progress:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "transcribing",
  "created_at": "2026-06-22T10:00:00Z",
  "updated_at": "2026-06-22T10:00:05Z",
  "task_id": null,
  "error_message": null
}
```

**Response 200** — complete:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "complete",
  "created_at": "2026-06-22T10:00:00Z",
  "updated_at": "2026-06-22T10:01:30Z",
  "task_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "error_message": null
}
```

**Response 200** — failed:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "created_at": "2026-06-22T10:00:00Z",
  "updated_at": "2026-06-22T10:00:10Z",
  "task_id": null,
  "error_message": "Audio too short (< 1 second of speech detected)"
}
```

**Response 404** — job not found or TTL expired:
```json
{ "error": "Job not found or expired" }
```

**Polling guidance**: Poll every 3–5 seconds. Job TTL is 30 minutes; stop polling if `status` stays `received` or `transcribing` beyond 35 minutes.

---

## Tasks

### `GET /api/tasks`

Return recent completed tasks, newest-first.

**Query params**:

| Param | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | 20 | Max 100 |

**Response 200**:
```json
{
  "tasks": [
    {
      "task_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "created_at": "2026-06-22T10:01:30Z",
      "objective": "Entregar o relatório Q3 para os stakeholders até sexta-feira.",
      "detected_language": "pt"
    }
  ],
  "total": 1
}
```

---

### `GET /api/tasks/{task_id}`

Return full task output. This URL is the shareable link (SC-009).

**Path param**: `task_id` — UUID4 string from `GET /api/jobs/{job_id}` response `task_id` field

**Response 200**:
```json
{
  "task_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "created_at": "2026-06-22T10:01:30Z",
  "detected_language": "pt",
  "audio_duration_seconds": 47.3,
  "raw_transcript": "Então, vê lá... ah, não espera. Precisamos entregar o relatório Q3 pros stakeholders até sexta. Primeiro consolida os dados de vendas, depois cria os slides, aí revisa com a gerência antes de enviar.",
  "objective": "Entregar o relatório Q3 para os stakeholders até sexta-feira.",
  "checklist": [
    "Consolidar dados de vendas do Q3",
    "Criar slides com gráficos de desempenho",
    "Revisar apresentação com gerência",
    "Enviar relatório para stakeholders"
  ],
  "flow": {
    "input": "Dados de vendas Q3 e lista de stakeholders",
    "logic": "Compilar relatório, criar apresentação visual, obter aprovação gerencial",
    "output": "Relatório Q3 entregue por e-mail até sexta-feira"
  }
}
```

**Response 404**:
```json
{ "error": "Task not found" }
```

---

## Gradio UI

The Gradio interface is mounted at `/ui`. All Gradio-internal routes are handled by the Gradio ASGI sub-application.

| Path | Description |
|---|---|
| `GET /ui` | Main Gradio interface (upload + output display) |
| `GET /ui/*` | Gradio static assets, websocket queue, API |

---

## Desktop Script Integration

The desktop script uses exactly three endpoints in sequence:

1. `POST /api/jobs` — upload mixed WAV → receive `job_id`
2. `GET /api/jobs/{job_id}` — poll every 5s until `status == "complete"` → extract `task_id`
3. `GET /api/tasks/{task_id}` — fetch full output → copy to clipboard

On any HTTP error or `status == "failed"`: preserve local `.wav` file, print `job_id` and file path to terminal (FR-019).
