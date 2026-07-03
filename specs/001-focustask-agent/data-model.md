# Data Model: Two-Stage Pipeline + Obsidian Export

**Feature**: 001-focustask-agent (refinement 2026-07-02) | **Plan**: [plan.md](./plan.md)

## Entities

### Transcript (existing, unchanged)

| Field | Type | Notes |
|-------|------|-------|
| raw_transcript | str | Whisper output |
| language | str | detected, default `pt` |
| duration_seconds | float | drives dynamic job timeout (research R4) |

### ConsolidatedSummary (NEW — Stage 1 output)

| Field | Type | Notes |
|-------|------|-------|
| text | str | structured prose with three mandatory section headers |

**Validation rules**:
- MUST contain the three section headers: `Entendimento Geral`, `Escopo`, `Regras de Negócio` (testable contract of the Stage 1 prompt)
- Non-empty after strip; language matches transcript language
- Sole input accepted by Stage 2 (`decompose(summary: str)` — transcript is not a parameter)

### TaskOutput / StructuredOutput (existing, unchanged shape)

| Field | Type | Notes |
|-------|------|-------|
| objetivo | str | one imperative sentence, ≤30 words |
| checklist | list[str] | 3–10 atomic, action-verb-first steps |
| fluxo | list[str] | 3–6 stages; first = input, last = expected output |

Produced by Stage 2 from ConsolidatedSummary only. JSON contract identical to production (Telegram formatter, jobs table, panel all keep working).

### MarkdownExport (NEW — derived, never stored)

| Field | Type | Notes |
|-------|------|-------|
| content | str | pure Markdown per template in research R5; every checklist item as `- [ ]` |
| filename | str | `{slug(objetivo, 60)}-{YYYY-MM-DD}.md`; fallback `focustask-{job_id[:8]}-{date}.md` |

**Validation rules**:
- No HTML tags in content
- Checklist lines match `^- \[ \] .+`
- Filename matches `^[a-z0-9-]+\.md$`

Rendered on demand from persisted job data — derived value, no storage.

### PipelineStageError (NEW — error semantics, FR-024)

| Field | Type | Notes |
|-------|------|-------|
| stage | enum | `summarization` \| `decomposition` |
| message | str | underlying cause |

Persisted into `jobs.error_msg` as `"[{stage}] {message}"`; surfaced verbatim in HTTP 500 detail and Telegram error copy.

## Database: `jobs` table migration

Existing columns: `job_id, status, source, transcript, objetivo, checklist, fluxo, error_msg, created_at (…)`

**Change (additive, nullable — safe on existing rows)**:

```sql
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS summary TEXT;
```

## State transitions (job lifecycle — updated)

```text
pending
  → processing            (transcription started; transcript saved on completion)
  → processing + summary  (Stage 1 done; summary persisted — NEW intermediate save)
  → done                  (Stage 2 done; objetivo/checklist/fluxo persisted)
  → error                 (any step; error_msg now stage-tagged for LLM stages)
```

Rule: `summary IS NOT NULL AND status='error'` ⇒ Stage 2 failed after successful Stage 1 (summary preserved for diagnosis/future retry — research R8).

## Pydantic schema changes (`app/models/schemas.py`)

```python
class ProcessResponse(BaseModel):        # MODIFIED — additive only
    job_id: str
    raw_transcript: str
    structured: StructuredOutput
    markdown: str                        # NEW: rendered Obsidian Markdown
    markdown_url: str                    # NEW: /api/jobs/{job_id}/download.md

class JobStatus(BaseModel):              # MODIFIED — additive only
    job_id: str
    status: str
    structured: Optional[StructuredOutput] = None
    transcript: Optional[str] = None
    error: Optional[str] = None          # stage-tagged for LLM failures
    markdown_url: Optional[str] = None   # NEW: set when status == "done"
```

`StructuredOutput`, `TranscriptionResponse`, `HealthResponse`: unchanged. Async long-audio uploads return 202 `{job_id, status, status_url}` instead of `ProcessResponse` (contracts/api.md).
