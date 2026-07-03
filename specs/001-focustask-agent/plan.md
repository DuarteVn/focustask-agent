# Implementation Plan: FocusTask Agent — Two-Stage Pipeline + Obsidian Export

**Branch**: `main` (feature branches merged; refinement lands on a new branch at implementation time) | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-focustask-agent/spec.md` (refined 2026-07-02: two-stage LLM analysis + Obsidian-compatible Markdown export)

## Summary

Refine the existing audio→task backend pipeline in two ways:

1. **Two-stage LLM analysis** (FR-020–FR-024): replace the single `gemini_service.structure(transcript)` call with two sequential calls — Stage 1 `summarize(transcript)` consolidates general understanding, scope, and business rules; Stage 2 `decompose(summary)` consumes **only** the Stage 1 output and produces the atomic micro-task checklist + execution flow. Prevents context loss on recordings up to 45 minutes.
2. **Obsidian-compatible Markdown export** (FR-025–FR-027): a rendering service serializes the structured output as pure Markdown (`##` headings, `- [ ]` task syntax) and a new download endpoint serves it as a `.md` file with a filesystem-safe filename (objective slug + date), ready to drop into an Obsidian vault.

Both changes are backend-first, touching `gemini_service`, `job_runner`, `process` routes, schemas, and the jobs table; the Telegram formatter and web panel keep consuming the same structured data (a polish task appends the `.md` download link to the Telegram reply). All HTTP routes live under the existing `/api` prefix.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI 0.115 + Uvicorn, faster-whisper 1.1 (local STT), google-genai ≥1.0 (Gemini 2.5 Flash — current primary LLM; `ollama_service.py` retained as local fallback), asyncpg (PostgreSQL job persistence), python-telegram-bot ≥20, pydub (audio conversion)

**Storage**: PostgreSQL — existing `jobs` table (job_id, status, source, transcript, objetivo, checklist, fluxo, error_msg); this feature adds a `summary` column (Stage 1 artifact)

**Testing**: pytest + httpx `ASGITransport` for endpoint tests; unit tests for markdown rendering and filename slugging (pure functions, no LLM needed)

**Target Platform**: Windows-first local dev; HF Spaces (Linux container) deploy target for the web app

**Project Type**: Web service (FastAPI backend) + Telegram bot + planned Gradio/React frontend

**Performance Goals**: 45-minute audio completes end-to-end without truncation (SC-006); two-stage LLM adds one extra Gemini call (~5–15 s) — negligible vs. Whisper transcription time on long audio

**Constraints**: `max_audio_duration_seconds` already 2700 (45 min) in config; `job_timeout_seconds=600` is the binding constraint for long audio — Whisper `medium/int8/cpu` on 45-min audio exceeds 600 s → timeout must scale (see research.md R4). No paid software for core flow; Gemini free tier acceptable (already in use since feature 002).

**Scale/Scope**: Portfolio/demo traffic — single worker, sequential jobs acceptable

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against Constitution v1.0.0 (ratified 2026-07-02):

| Principle | Status | Note |
|-----------|--------|------|
| I. Local-First, Zero-Cost Core | ✅ PASS | Whisper stays local; Gemini free tier; two-stage method signatures keep Ollama fallback viable (research R9) |
| II. PT-BR First | ✅ PASS | Both stage prompts PT-BR; output language follows input; error copy PT-BR |
| III. ADHD-Friendly Output | ✅ PASS | Three-section structure and numeric limits unchanged; SC-011 pins limits for 45-min audio |
| IV. Spec-Driven Development | ✅ PASS | Refinement recorded in spec + research before implementation; CLAUDE.md update tasked (T021) |
| V. Tests Without Live Dependencies | ✅ PASS | All pytest tasks mock LLM client/repository/whisper; live validation in quickstart only |
| VI. Free-Tier Deployability | ✅ PASS | No disk-persisted exports (render on the fly); duration-scaled timeouts; async web flow avoids long-lived requests |

**Post-Phase-1 re-check (2026-07-02, updated post-/speckit-analyze)**: design introduces one new module (`markdown_service.py`), one DB column, two prompt constants, one router (status + download), async dispatch for long audio — no violations. ✅ PASS.

## Project Structure

### Documentation (this feature)

```text
specs/001-focustask-agent/
├── plan.md              # This file
├── spec.md              # Refined 2026-07-02
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # HTTP contract incl. new download endpoint
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/routes/
│   │   ├── health.py
│   │   ├── process.py           # MODIFY: two-stage orchestration; markdown in response
│   │   ├── transcribe.py
│   │   └── jobs.py              # NEW (or extend existing jobs route): GET /jobs/{id}/download.md
│   ├── core/
│   │   ├── config.py            # MODIFY: dynamic job timeout for long audio
│   │   └── loop.py
│   ├── db/
│   │   ├── database.py          # MODIFY: add `summary` column (migration note in data-model.md)
│   │   └── repository.py        # MODIFY: persist summary in set_processing/set_summary
│   ├── models/
│   │   └── schemas.py           # MODIFY: ConsolidatedSummary flow; markdown field on ProcessResponse
│   ├── services/
│   │   ├── whisper_service.py   # unchanged
│   │   ├── gemini_service.py    # MODIFY: split into summarize() + decompose(); stage-tagged errors
│   │   ├── ollama_service.py    # OPTIONAL parity: mirror two-stage interface
│   │   ├── markdown_service.py  # NEW: render TaskOutput → Obsidian Markdown; slugify filename
│   │   ├── job_runner.py        # MODIFY: run summarize → decompose; progress stages; persist summary
│   │   └── audio_converter.py   # unchanged
│   └── telegram/                # unchanged (formatter already consumes structured dict)
└── tests/
    ├── unit/
    │   ├── test_markdown_service.py   # NEW
    │   └── test_gemini_prompts.py     # NEW (prompt contract shape tests, mocked client)
    └── integration/
        └── test_download_endpoint.py  # NEW
```

**Structure Decision**: Existing single-backend layout retained. Two-stage pipeline is a refactor inside `gemini_service` + orchestrators (`job_runner`, `process.py`); Obsidian export is one new pure-function service + one new GET endpoint. No frontend work required for the API contract (button lands with the frontend feature).

## Design Decisions (summary — details in research.md)

1. **Stage split lives in the LLM service, orchestration in callers.** `gemini_service` exposes `summarize(transcript, language) -> str` and `decompose(summary, language) -> dict` (keeps the existing JSON schema). A thin `structure_two_stage()` helper chains them and tags failures with the failing stage name (`PipelineStageError(stage="summarization"|"decomposition")`) to satisfy FR-024.
2. **Stage 1 output is prose, not JSON.** The consolidated summary is structured prose (sections: entendimento geral / escopo / regras de negócio) — richer input for Stage 2 than a lossy JSON squeeze, and trivially storable in the new `jobs.summary` text column.
3. **Stage 2 is blind to the transcript.** `decompose()` receives only the summary string — enforced by function signature, satisfying FR-022 structurally rather than by prompt discipline alone.
4. **Markdown rendering is deterministic, not LLM-generated.** `markdown_service.render(objetivo, checklist, fluxo) -> str` builds the document from already-validated structured data. Guarantees FR-025 (`- [ ]` syntax, no HTML) on 100% of outputs — an LLM asked to emit Markdown cannot give that guarantee.
5. **Download reads from the jobs table.** `GET /api/jobs/{job_id}/download.md` fetches the persisted job, renders Markdown on the fly, returns `text/markdown` with `Content-Disposition: attachment; filename="<slug>-<YYYY-MM-DD>.md"`. No files written to disk; stateless rendering. `ProcessResponse` also gains a `markdown` field (string) and `markdown_url` so clients can copy or link immediately. A sibling `GET /api/jobs/{job_id}` status route is created in the same router (none existed) to back the async web flow.
6. **Filename slug**: objective → NFKD-normalize, strip accents, lowercase, non-alphanumerics → `-`, truncate ~60 chars, append date. Fallback `focustask-<job_id[:8]>-<date>.md` when the objective slugs to empty (FR-027 edge case).
7. **Timeout scales with audio duration**: replace fixed 600 s with `max(job_timeout_seconds, duration_seconds * timeout_factor)` — research.md R4.
8. **Async web flow for long audio** (post-analyze addition): `/api/process/audio` returns 202 + `job_id` when duration > `sync_processing_max_seconds` (default 300) and runs the pipeline as a background task; client polls `GET /api/jobs/{job_id}`. Keeps FR-023 honest on the web path — a synchronous HTTP request cannot survive 45–90 min of CPU transcription — and satisfies Principle VI (no long-lived requests on HF Spaces).

## Complexity Tracking

No constitution violations — table not required.
