# API Contract: FocusTask Agent Backend

**Feature**: 001-focustask-agent (refinement 2026-07-02) | **Base**: FastAPI service, no auth (public portfolio endpoint)

**Path prefix**: ALL routes are mounted under `/api` (see `backend/app/main.py` — `app.include_router(..., prefix="/api")`). Paths below are the real, full paths.

## POST /api/process/audio (MODIFIED)

Full pipeline: audio → transcription → Stage 1 (summarize) → Stage 2 (decompose) → structured JSON + Markdown.

**Request**: `multipart/form-data`, field `file` (mp3 | wav | ogg | m4a | webm), duration ≤ 45 min (measured from audio metadata BEFORE transcription), size ≤ `max_upload_bytes`.

**Response modes** (FR-023):

- **Short audio** (duration ≤ `sync_processing_max_seconds`, default 300): synchronous — 200 with the full `ProcessResponse` below.
- **Long audio** (> threshold): asynchronous — **202** with `{"job_id": "uuid", "status": "pending", "status_url": "/api/jobs/{job_id}"}`; processing continues in background (`job_runner.run_job`); client polls the status URL.

**Response 200** (`application/json`):

```json
{
  "job_id": "uuid",
  "raw_transcript": "…",
  "structured": {
    "objetivo": "Entregar X até Y",
    "checklist": ["Criar …", "Validar …"],
    "fluxo": ["Áudio bruto recebido", "…", "Relatório entregue"]
  },
  "markdown": "# Entregar X até Y\n\n## 🎯 Objetivo Direto\n…\n## ✅ Micro-Tasks\n\n- [ ] Criar …\n- [ ] Validar …\n…",
  "markdown_url": "/api/jobs/{job_id}/download.md"
}
```

**Errors**:

| Status | Condition | Detail format |
|--------|-----------|---------------|
| 400 | empty file / unsupported format | plain message |
| 400 | duration > 45 min (checked from metadata, before Whisper runs) | `"Áudio excede o limite de 45 minutos."` |
| 500 | transcription failure (sync mode) | `"Transcription failed: …"` |
| 500 | Stage 1 failure (sync mode) | `"LLM processing failed: [summarization] …"` |
| 500 | Stage 2 failure (sync mode) | `"LLM processing failed: [decomposition] …"` |

Async-mode failures are reported via job status (`status: "error"`, stage-tagged `error` field), not HTTP errors.

## POST /api/process/text (MODIFIED)

Same as `/api/process/audio` from Stage 1 onward (skips Whisper; always synchronous — text input has no transcription cost). Request `{"transcript": "…"}`. Response/errors identical to sync mode above (no transcription error case).

## GET /api/jobs/{job_id} (NEW in this refinement)

Job status polling — required by the async mode above. **Note**: despite the Telegram panel link referencing `/jobs/{id}`, no such route existed before this refinement; this makes it real. Backed by existing `repository.get_job` + `JobStatus` schema.

**Response 200** (`application/json`):

```json
{
  "job_id": "uuid",
  "status": "pending | processing | done | error",
  "structured": { "objetivo": "…", "checklist": ["…"], "fluxo": ["…"] },
  "transcript": "…",
  "error": null,
  "markdown_url": "/api/jobs/{job_id}/download.md"
}
```

`structured`/`transcript` null until available; `markdown_url` present only when `status == "done"`. `error` is stage-tagged (`"[summarization] …"` / `"[decomposition] …"`) for LLM failures.

**Errors**: 404 unknown job_id.

## GET /api/jobs/{job_id}/download.md (NEW)

Download the structured output as an Obsidian-ready Markdown file.

**Response 200**:
- `Content-Type: text/markdown; charset=utf-8`
- `Content-Disposition: attachment; filename="{slug}.md"; filename*=UTF-8''{encoded}`
- Body: pure Markdown; every checklist item as `- [ ]`; no HTML

**Filename**: `{slugify(objetivo)[:60]}-{YYYY-MM-DD}.md`; fallback `focustask-{job_id[:8]}-{YYYY-MM-DD}.md` when slug is empty. Charset `[a-z0-9-]`.

**Errors**:

| Status | Condition |
|--------|-----------|
| 404 | unknown job_id |
| 409 | job exists but status ≠ `done` (body says current status: pending/processing/error) |

## GET /api/health (existing, unchanged)

## Internal service contracts (not HTTP)

```python
# app/services/gemini_service.py
def summarize(transcript: str, language: str = "pt") -> str
    # → ConsolidatedSummary prose; sections: Entendimento Geral / Escopo / Regras de Negócio
    # raises PipelineStageError(stage="summarization")

def decompose(summary: str, language: str = "pt") -> dict
    # → {"objetivo": str, "checklist": [str], "fluxo": [str]} — summary is the ONLY content input
    # raises PipelineStageError(stage="decomposition")

def structure_two_stage(transcript: str, language: str = "pt") -> tuple[str, dict]
    # → (summary, structured); chains the above

# app/services/markdown_service.py
def render(objetivo: str, checklist: list[str], fluxo: list[str]) -> str
def make_filename(objetivo: str, job_id: str, date: datetime.date) -> str

# app/services/audio_converter.py (extended)
def get_duration_seconds(audio_bytes: bytes, filename: str) -> float
    # pydub metadata probe — used for upfront 45-min rejection and sync/async routing
```

## Config additions (`app/core/config.py`)

- `job_timeout_factor: float = 1.5` — dynamic timeout multiplier (research R4)
- `sync_processing_max_seconds: int = 300` — audio duration threshold for sync vs. async web response
