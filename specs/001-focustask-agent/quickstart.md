# Quickstart: Validate Two-Stage Pipeline + Obsidian Export

**Feature**: 001-focustask-agent (refinement 2026-07-02) | **Contract**: [contracts/api.md](./contracts/api.md)

## Prerequisites

- Python 3.11+, deps installed: `pip install -r backend/requirements.txt`
- PostgreSQL running, `DATABASE_URL` set in `backend/.env` — apply migration: `ALTER TABLE jobs ADD COLUMN IF NOT EXISTS summary TEXT;`
- `GEMINI_API_KEY` set in `backend/.env`
- Start API from repo root: `uvicorn backend.app.main:app --reload --port 8000`

## Scenario 1 — Two-stage pipeline runs on any audio (FR-020)

```bash
curl -s -X POST http://localhost:8000/api/process/audio \
  -F "file=@sample_short.mp3" | python -m json.tool
```

**Expect**: 200 with `structured` (objetivo / checklist / fluxo), `markdown`, `markdown_url`. API logs show two LLM phases in order: `summarize done` then `decompose done`. DB row has non-null `summary`:

```sql
SELECT status, summary IS NOT NULL AS has_summary FROM jobs ORDER BY created_at DESC LIMIT 1;
-- done | t
```

## Scenario 2 — Early business rule survives long audio (FR-021/022, SC-009)

Use a long recording (10+ min) where a business rule is stated only in the first minutes (test fixture: rule at ~2 min mark, unrelated discussion after).

```bash
curl -s -X POST http://localhost:8000/api/process/audio -F "file=@sample_long_rule_early.mp3"
```

**Expect**: the rule appears in `checklist` or `fluxo`; `jobs.summary` mentions it under `Regras de Negócio`.

## Scenario 3 — Obsidian-ready download (FR-025–027, SC-010)

```bash
JOB=<job_id from scenario 1>
curl -sD - -o task.md "http://localhost:8000/api/jobs/$JOB/download.md"
```

**Expect**:
- Headers: `content-type: text/markdown`, `content-disposition: attachment; filename="<slug>-<date>.md"` — filename only `[a-z0-9-]`, even for accented PT-BR objectives
- `task.md`: every checklist line starts `- [ ] `; headings for the 3 sections; zero HTML tags (`grep -c '<' task.md` → 0 or only from content)
- Drop `task.md` into an Obsidian vault → checkboxes are clickable, headings render

## Scenario 4 — Stage-tagged errors (FR-024)

Set an invalid `GEMINI_API_KEY`, POST any text:

```bash
curl -s -X POST http://localhost:8000/api/process/text \
  -H "Content-Type: application/json" -d '{"transcript": "preciso montar o relatório de vendas"}'
```

**Expect**: 500 with detail containing `[summarization]`. (Stage 2 failure is exercised in integration tests by mocking `decompose` — expect `[decomposition]` and `jobs.summary` still populated.)

## Scenario 5 — Download guards

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/jobs/00000000-0000-0000-0000-000000000000/download.md   # 404
# job in status=error (from scenario 4): expect 409
```

## Scenario 6 — 45-minute audio, async web flow (FR-023, SC-006)

```bash
# Long audio (> sync threshold) → 202 + job_id immediately, no long-lived HTTP request
curl -s -X POST http://localhost:8000/api/process/audio -F "file=@sample_45min.mp3"
# → {"job_id": "…", "status": "pending", "status_url": "/api/jobs/…"}

# Poll until done (dynamic timeout scales with duration — research R4):
curl -s http://localhost:8000/api/jobs/$JOB | python -m json.tool

# Over-limit audio → 400 upfront (metadata check, before Whisper runs):
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/process/audio -F "file=@sample_50min.mp3"   # 400
```

**Expect**: immediate 202 for the 45-min file; polling eventually returns `status: "done"` with untruncated output and `markdown_url`; the 50-min file is rejected with 400 before any transcription compute.

## Automated tests

```bash
cd backend && python -m pytest tests/ -v
```

- `tests/unit/test_markdown_service.py` — `- [ ]` rendering, slug edge cases (accents, symbols-only objective, 60-char truncation)
- `tests/unit/test_gemini_prompts.py` — two-stage chaining, stage-tagged errors (mocked Gemini client)
- `tests/integration/test_download_endpoint.py` — 200/404/409, headers, filename format
