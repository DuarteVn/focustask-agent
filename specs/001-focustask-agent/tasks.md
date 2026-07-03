# Tasks: FocusTask Agent — Two-Stage Pipeline + Obsidian Export

**Input**: Design documents from `/specs/001-focustask-agent/`

**Prerequisites**: plan.md, spec.md (refined 2026-07-02), research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: INCLUDED — plan.md's Technical Context specifies pytest coverage (unit: markdown/prompt contracts; integration: download endpoint), and quickstart.md defines the validation scenarios. Write tests first within each story; ensure they fail before implementing.

**Scope note**: This tasks.md covers the 2026-07-02 refinement only — User Story 6 (Long Audio Deep Processing) and User Story 7 (Obsidian Markdown Export). US1–US5's core pipeline already exists in `backend/app` (features 001/002 merged). Story labels [US6]/[US7] map to spec.md numbering.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US6, US7)
- Exact file paths in every description

## Path Conventions

Web app backend: `backend/app/` (existing FastAPI layout), tests in `backend/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test scaffolding — the only missing infrastructure; no new runtime dependencies (plan constraint)

- [x] T001 Create test scaffolding: `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/integration/__init__.py`, and `backend/tests/conftest.py` with an httpx `ASGITransport` client fixture for `app.main:app` and a mocked-DB fixture (repository functions monkeypatched — tests must not require live PostgreSQL)
- [x] T002 [P] Add dev/test dependencies (`pytest`, `pytest-asyncio`) to `backend/requirements.txt` under a `# Dev/Test` section, and add `[tool.pytest.ini_options]` (asyncio mode, testpaths) to `backend/pyproject.toml` (create file if absent)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB column, repository write, and config knobs both user stories build on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Add `summary TEXT` column to the jobs schema: update the `CREATE TABLE`/init DDL in `backend/app/db/database.py` and document the live-DB migration (`ALTER TABLE jobs ADD COLUMN IF NOT EXISTS summary TEXT;`) in a comment per data-model.md
- [x] T004 Add `async def set_summary(job_id: str, summary: str)` to `backend/app/db/repository.py` (UPDATE jobs SET summary=$1 WHERE job_id=$2), following the existing pool/acquire pattern
- [x] T005 [P] Add `job_timeout_factor: float = 1.5` setting to `backend/app/core/config.py` (research R4 dynamic timeout; `max_audio_duration_seconds=2700` already present)

**Checkpoint**: Foundation ready — US6 and US7 can proceed in parallel

---

## Phase 3: User Story 6 - Long Audio Deep Processing (Priority: P2) 🎯 MVP

**Goal**: Replace single-pass LLM call with two sequential stages — `summarize(transcript)` → consolidated prose summary (Entendimento Geral / Escopo / Regras de Negócio) → `decompose(summary)` → existing JSON schema. Stage-tagged errors, summary persisted, timeout scales with audio duration, 45-min audio viable end-to-end.

**Independent Test**: quickstart.md Scenarios 1, 2, 4, 6 — two LLM phases visible in logs, `jobs.summary` populated, early business rule survives to output, `[summarization]`/`[decomposition]` tags in error details.

### Tests for User Story 6 (write first, must fail)

- [x] T006 [P] [US6] Unit tests in `backend/tests/unit/test_gemini_service.py` (mocked `genai.Client`): `summarize()` returns prose containing the three section headers; `decompose()` accepts only a summary string and returns objetivo/checklist/fluxo dict; `structure_two_stage()` chains them; Stage 1 failure raises `PipelineStageError(stage="summarization")`, Stage 2 failure raises `PipelineStageError(stage="decomposition")`; per-stage retry on transient 503
- [x] T007 [P] [US6] Integration test in `backend/tests/integration/test_two_stage_pipeline.py` (ASGI client, whisper + gemini mocked): POST `/process/text` → 200 with structured output and both stages invoked in order; Stage 2 mock failure → 500 detail contains `[decomposition]` AND `set_summary` was called (summary preserved on Stage-2 failure); POST `/process/audio` with mocked 46-min duration → 400 upfront rejection

### Implementation for User Story 6

- [x] T008 [US6] Refactor `backend/app/services/gemini_service.py`: add `PipelineStageError(RuntimeError)` with `stage` attr; split `SYSTEM_PROMPT` into `SUMMARIZE_PROMPT` (consolidador de contexto — three prose sections, captures ALL business rules, drops fillers/tangents, same language, no tasks) and `DECOMPOSE_PROMPT` (current JSON-schema prompt with input renamed to "Resumo Consolidado"); implement `summarize(transcript, language) -> str` (plain-text response) and `decompose(summary, language) -> dict` (`response_mime_type="application/json"`, temp 0.1), each wrapped by the existing key-fallback/retry loop and raising stage-tagged errors; add `structure_two_stage(transcript, language) -> tuple[str, dict]`; delete single-pass `structure()` (research R1–R3)
- [x] T009 [US6] Update `backend/app/services/job_runner.py::run_job`: call `summarize` → `await set_summary(job_id, summary)` → `decompose`; progress dict stages `"sumarizando"` then `"estruturando"`; persist stage-tagged message (`"[{stage}] {msg}"`) via `set_error` on `PipelineStageError`; update `_heartbeat` copy in `run_job_telegram` for the new `"sumarizando"` stage
- [x] T010 [US6] Dynamic timeout in `backend/app/services/job_runner.py::run_job_telegram`: whisper result already carries duration — compute `effective_timeout = max(settings.job_timeout_seconds, duration_seconds * settings.job_timeout_factor)`; since duration is known only after transcription, restructure the `asyncio.wait_for` so transcription runs under the base timeout and the LLM stages under the extended one (or apply the factor from measured duration once available — keep the approach documented in research R4)
- [x] T011 [US6] Update `backend/app/api/routes/process.py`: both `/api/process/audio` and `/api/process/text` call `structure_two_stage`; catch `PipelineStageError` and raise HTTP 500 with detail `"LLM processing failed: [{stage}] {msg}"`; `/api/process/audio` rejects duration > `settings.max_audio_duration_seconds` with 400 ("Áudio excede o limite de 45 minutos.") measured via `audio_converter.get_duration_seconds` (pydub metadata probe — add it in `backend/app/services/audio_converter.py`) BEFORE Whisper runs; persist transcript + summary via repository as in job_runner
- [x] T012 [US6] Run and pass T006–T007 tests; verify quickstart.md Scenario 1 manually (two-phase logs, `has_summary = t` in DB)
- [x] T024 [US6] Async web flow for long audio (FR-023; added by /speckit-analyze remediation — executes after T011): in `backend/app/api/routes/process.py`, when audio duration > `settings.sync_processing_max_seconds` (new setting, default 300, add in `backend/app/core/config.py`), return 202 `{"job_id", "status": "pending", "status_url": "/api/jobs/{job_id}"}` and schedule `job_runner.run_job` as a background task; short audio keeps the synchronous 200 path; extend `backend/tests/integration/test_two_stage_pipeline.py` with a mocked long-duration upload asserting 202 + background dispatch

**Checkpoint**: Two-stage pipeline fully functional and independently testable — single-pass path gone

---

## Phase 4: User Story 7 - Obsidian Markdown Export (Priority: P2)

**Goal**: Deterministic Markdown renderer (`- [ ]` tasks, pure Markdown), `markdown` + `markdown_url` on ProcessResponse, and `GET /jobs/{job_id}/download.md` serving an attachment with a filesystem-safe filename.

**Independent Test**: quickstart.md Scenarios 3 and 5 — download a `.md`, drop into Obsidian vault, checkboxes clickable; 404/409 guards. Does NOT depend on US6 (renders from persisted structured data regardless of how it was produced).

### Tests for User Story 7 (write first, must fail)

- [x] T013 [P] [US7] Unit tests in `backend/tests/unit/test_markdown_service.py`: every checklist item rendered as `- [ ] ` line; three section headings present; no HTML tags in output; fluxo renders first stage as Input and last as Output; `make_filename` slug cases — PT-BR accents ("Relatório de Vendas até Sexta" → `relatorio-de-vendas-ate-sexta-<date>.md`), Windows-forbidden chars stripped, >60-char truncation at word boundary, symbols-only objective → `focustask-{job_id[:8]}-<date>.md` fallback, result matches `^[a-z0-9-]+\.md$`
- [x] T014 [P] [US7] Integration test in `backend/tests/integration/test_download_endpoint.py` (ASGI client, repository mocked): done job → 200 with `text/markdown` content-type, `Content-Disposition: attachment` + valid filename, body checklist lines match `^- \[ \] `; unknown job_id → 404; job with status `processing`/`error` → 409 with current status in body

### Implementation for User Story 7

- [x] T015 [P] [US7] Create `backend/app/services/markdown_service.py`: `render(objetivo, checklist, fluxo) -> str` per research R5 template (title from objetivo, `## 🎯 Objetivo Direto`, `## ✅ Micro-Tasks` with `- [ ]` items, `## 🔁 Fluxo de Execução` numbered with Input/Output labels); `slugify(text) -> str` (stdlib `unicodedata` NFKD + `re`, lowercase, runs of non-alphanumerics → `-`, 60-char word-boundary truncation); `make_filename(objetivo, job_id, date) -> str` with empty-slug fallback (research R7)
- [x] T016 [P] [US7] Update `backend/app/models/schemas.py`: add `markdown: str` and `markdown_url: str` fields to `ProcessResponse` (additive — data-model.md)
- [x] T017 [US7] Create `backend/app/api/routes/jobs.py` with TWO routes (no jobs router exists today — the Telegram panel link points at nothing): (a) `GET /jobs/{job_id}` returning `JobStatus` (existing schema) from `repository.get_job`, 404 if missing, stage-tagged `error` passthrough, `markdown_url` when done; (b) `GET /jobs/{job_id}/download.md` — 404 if missing; 409 with current status if status ≠ `done`; else `markdown_service.render` + `Response(media_type="text/markdown; charset=utf-8")` with `Content-Disposition: attachment; filename="..."` plus RFC 5987 `filename*` for the UTF-8 original (contracts/api.md); register router in `backend/app/main.py` with `prefix="/api"` like the others (depends on T015)
- [x] T018 [US7] Update `backend/app/api/routes/process.py`: populate `markdown=markdown_service.render(...)` and `markdown_url=f"/api/jobs/{job_id}/download.md"` in both endpoints' `ProcessResponse` (depends on T015, T016; coordinate with T011/T024 — same file, do after US6 lands or on the same branch)
- [x] T019 [US7] Run and pass T013–T014 tests; verify quickstart.md Scenario 3 manually — download `task.md`, open in an Obsidian vault, confirm interactive checkboxes (SC-010)

**Checkpoint**: Both stories independently functional — full refinement delivered

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Consumer-facing touches, stale docs, final validation

- [x] T020 [P] Add Markdown download link to the Telegram reply in `backend/app/telegram/` (`job_runner.py::_format_result`): append `{web_panel_base_url}/jobs/{job_id}/download.md` line after the panel link
- [x] T021 [P] Update stale project docs in `CLAUDE.md` (root): core-flow description still says "Ollama LLM (local)" and "Stateless — no DB" — reflect actual stack (Gemini primary with Ollama fallback dormant, PostgreSQL job persistence, two-stage pipeline, Obsidian export); update Common Commands if needed
- [ ] T022 Run full quickstart.md validation (Scenarios 1–6) against a live server and record results in `specs/001-focustask-agent/quickstart.md` footer or PR description; confirm SC-006 (45-min audio) and SC-010 (zero-reformatting Obsidian import)
- [x] T023 Run `cd backend && python -m pytest tests/ -v` — full suite green; commit

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS both user stories (T003 → T004; T005 independent)
- **US6 (Phase 3)** and **US7 (Phase 4)**: Both depend only on Phase 2 — can run in parallel (different files), EXCEPT T018 touches `process.py` alongside T011/T024 (sequence those or share a branch); T024's status polling route lands in T017 (US7) — if US6 ships first, polling arrives with US7 (202 + job_id still functional via DB)
- **Polish (Phase 5)**: T020 needs T017; T021 anytime; T022–T023 need both stories done

### User Story Dependencies

- **US6 (P2)**: Independent after Foundational
- **US7 (P2)**: Independent after Foundational — renders from persisted job data, works even against jobs produced by the old pipeline

### Within Each User Story

- Tests first (fail) → services → orchestrators/endpoints → verify
- US6: T006/T007 → T008 → T009/T010 → T011 → T024 → T012
- US7: T013/T014 → T015/T016 → T017 → T018 → T019

### Parallel Opportunities

- T002 ∥ T001; T005 ∥ T003–T004
- After Phase 2: entire US6 track ∥ entire US7 track (one dev each), minding the T011/T018 `process.py` overlap
- Within US6: T006 ∥ T007
- Within US7: T013 ∥ T014, then T015 ∥ T016
- Polish: T020 ∥ T021

---

## Parallel Example: after Foundational

```bash
# Developer A — US6 tests:
Task: "Unit tests for two-stage gemini_service in backend/tests/unit/test_gemini_service.py"
Task: "Integration test for two-stage pipeline in backend/tests/integration/test_two_stage_pipeline.py"

# Developer B — US7 tests + pure functions (no US6 dependency):
Task: "Unit tests for markdown renderer/slug in backend/tests/unit/test_markdown_service.py"
Task: "Integration test for download endpoint in backend/tests/integration/test_download_endpoint.py"
Task: "Create backend/app/services/markdown_service.py"
```

---

## Implementation Strategy

### MVP First (US6 only)

1. Phase 1 (T001–T002) + Phase 2 (T003–T005)
2. Phase 3: US6 (T006–T012)
3. **STOP and VALIDATE**: quickstart Scenarios 1, 2, 4, 6 — two-stage pipeline is the architectural core; ship/demo it alone if needed

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US6 → validate independently → merge (pipeline refit, MVP)
3. US7 → validate independently (Obsidian import test) → merge
4. Polish (T020–T023) → final quickstart sweep → done

---

## Notes

- [P] = different files, no incomplete-task dependencies
- Single-pass `structure()` is deleted in T008 — spec FR-020 bans it; don't leave a deprecated path
- Tests must not require live PostgreSQL or a Gemini key (mock repository + client); quickstart scenarios cover live validation
- Commit after each task or logical group; stop at any checkpoint to validate story independently
- Ollama two-stage parity explicitly deferred (research R9) — not a task here
