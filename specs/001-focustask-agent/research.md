# Research: Two-Stage Pipeline + Obsidian Export

**Feature**: 001-focustask-agent (refinement 2026-07-02) | **Plan**: [plan.md](./plan.md)

All Technical Context unknowns resolved below. No NEEDS CLARIFICATION remain.

## R1 — Stage 1 output format: prose vs. JSON

**Decision**: Structured prose with three fixed section headers (`Entendimento Geral`, `Escopo`, `Regras de Negócio`), plain text, no JSON.

**Rationale**:
- Stage 2's job is decomposition of *meaning*; prose preserves nuance and conditional rules ("se o cliente for PJ, então...") that flatten badly into JSON fields.
- A JSON schema for "understanding" invites premature structure — the model spends capacity on schema compliance instead of consolidation.
- Prose stores directly in a `TEXT` column and is human-readable for debugging (spec assumption: summary is an internal artifact, optionally exposed).
- Fixed section headers make the summary predictable enough for Stage 2's prompt to reference sections explicitly, and testable (assert all three headers present).

**Alternatives considered**:
- *JSON summary schema* — rejected: lossy for business rules, doubles schema-compliance failure surface (two JSON parses per job instead of one).
- *Free-form summary (no sections)* — rejected: untestable, Stage 2 prompt can't anchor on structure.

## R2 — Where the stage orchestration lives

**Decision**: Both stage methods on `GeminiService` (`summarize`, `decompose`), plus a `structure_two_stage()` convenience that chains them and raises `PipelineStageError(stage=...)` on failure. `job_runner.run_job` and `process.py` routes call the two-stage path; the old single-pass `structure()` is deleted (spec FR-020 bans single-pass).

**Rationale**:
- Keeps retry/key-fallback logic (already in `GeminiService`) wrapping *each* stage independently — a transient 503 in Stage 2 retries Stage 2 only, not the whole pipeline.
- Stage-tagged exception satisfies FR-024 (error identifies failing stage) in one place; callers just surface `exc.stage`.
- Function signature `decompose(summary: str)` structurally enforces FR-022 (Stage 2 never sees the transcript).

**Alternatives considered**:
- *Orchestration in job_runner only* — rejected: `process.py` sync route would duplicate the chain + error tagging.
- *Separate SummarizerService/DecomposerService classes* — rejected: overkill; both stages share client construction, retry, and key-fallback code.

## R3 — Prompt design for the two stages

**Decision**:
- **Stage 1 (summarization) system prompt**: role = "consolidador de contexto"; input = raw transcript; output = the three prose sections; explicitly instructed to (a) capture ALL business rules/constraints even if mentioned once, (b) drop fillers, tangents, self-corrections (noise filtering moves here per FR-004), (c) answer in the transcript's language, (d) no tasks, no checklists — understanding only.
- **Stage 2 (decomposition) system prompt**: current production prompt adapted — input changes from "Transcrição" to "Resumo Consolidado"; keeps the strict JSON schema (`objetivo`, `checklist`, `fluxo`), 3–10 atomic checklist items, 3–6 flow stages, `response_mime_type="application/json"`, temperature 0.1.

**Rationale**: Stage 2's existing JSON contract is proven in production (feature 002); only its input source changes. Splitting noise-filtering into Stage 1 gives each prompt a single responsibility — measured by SC-004 (noise absent) and SC-009 (early business rules survive).

**Alternatives considered**:
- *Map-reduce chunked summarization (chunk transcript → summarize chunks → merge)* — deferred: Gemini 2.5 Flash's context window (1M tokens) comfortably holds a 45-min transcript (~9k words); chunking adds complexity with no benefit at this scale. Revisit only if a local Ollama model (8k–32k context) becomes primary.
- *Single call with chain-of-thought ("first summarize, then decompose in one response")* — rejected: this is exactly the single-pass approach the spec now bans; empirically loses early-transcript details on long inputs.

## R4 — Job timeout for 45-minute audio

**Decision**: Scale timeout with measured audio duration: `effective_timeout = max(settings.job_timeout_seconds, duration_seconds * settings.job_timeout_factor)` with `job_timeout_factor: float = 1.5` (new setting). Whisper reports duration before transcription starts.

**Rationale**: Fixed `job_timeout_seconds=600` kills any 45-min job — Whisper `medium/int8` on CPU runs at roughly 0.5–1× real-time, so 45-min audio needs ~45–90 min wall time (SC-006 would be unmeetable). Factor 1.5 gives headroom for both stages' LLM calls (seconds, not minutes). Existing 600 s floor keeps short-audio behavior identical.

**Alternatives considered**:
- *Raise fixed timeout to 5400 s* — rejected: a stuck 30-second job would then hang 90 min before erroring.
- *Smaller/faster Whisper model for long audio* — rejected for now: quality tradeoff on PT-BR; note as future option in HF Spaces (free tier CPU is slow).

## R5 — Markdown generation approach

**Decision**: Deterministic Python renderer (`markdown_service.render`) building the document from validated structured data. Template:

```markdown
# {objetivo — first line as title}

## 🎯 Objetivo Direto

{objetivo}

## ✅ Micro-Tasks

- [ ] {item 1}
- [ ] {item 2}

## 🔁 Fluxo de Execução

1. **Input** — {fluxo[0]}
2. {fluxo[1..n-2]}
3. **Output** — {fluxo[-1]}
```

**Rationale**: FR-025 demands `- [ ]` on *every* checklist item with no HTML — only deterministic code guarantees 100% compliance (SC-010 zero-reformatting). LLM already produced the structured data; rendering is serialization, not intelligence. Pure function → trivial unit tests.

**Alternatives considered**:
- *Ask Stage 2 to emit Markdown directly* — rejected: no format guarantee, breaks the existing JSON contract consumed by Telegram formatter and jobs table.
- *Jinja2 template* — rejected: one f-string function; a template engine adds a dependency for nothing.

## R6 — Download endpoint design

**Decision**: `GET /api/jobs/{job_id}/download.md` — fetches job from PostgreSQL, 404 if missing, 409 if job not `done`, renders Markdown on the fly, returns `Response(content=md, media_type="text/markdown; charset=utf-8")` with `Content-Disposition: attachment; filename="{slug}.md"` (plus RFC 5987 `filename*` for accented objectives). Nothing written to disk.

**Rationale**: Jobs are already persisted (feature 002), so download works for any past job, from any client (web panel link, Telegram panel URL) — not just the request that created it. Stateless rendering keeps HF Spaces' ephemeral filesystem out of the picture. `ProcessResponse` additionally carries `markdown` (inline string) and `markdown_url` so the immediate caller needs no second round-trip.

**Alternatives considered**:
- *Return file from POST /process/audio directly* — rejected: forces clients to choose JSON or file; breaks existing consumers.
- *Write .md to temp dir + FileResponse* — rejected: disk churn, cleanup burden, breaks on read-only/ephemeral deploys.

## R7 — Filename sanitization (FR-027)

**Decision**: `slugify(objetivo)`: Unicode NFKD normalize → strip combining marks (ç→c, ã→a) → lowercase → replace any run of non `[a-z0-9]` with single `-` → strip leading/trailing `-` → truncate 60 chars at word boundary → append `-YYYY-MM-DD`. Empty result → fallback `focustask-{job_id[:8]}-YYYY-MM-DD`. Stdlib only (`unicodedata`, `re`).

**Rationale**: Handles PT-BR accents, Windows-forbidden characters (`<>:"/\|?*`), and the spec edge case "objective contains characters invalid in filenames". Date suffix per FR-027.

**Alternatives considered**: `python-slugify` package — rejected: 15 lines of stdlib beat a new dependency.

## R8 — Persisting the Stage 1 summary

**Decision**: Add nullable `summary TEXT` column to `jobs`; `job_runner` saves it between stages (new `set_summary(job_id, summary)` repository call, or fold into `set_processing`). Not exposed in API responses for v1.

**Rationale**: Costs one column; buys (a) debugging visibility into Stage 1 quality (directly measurable against SC-009), (b) the spec's edge case "Stage 1 succeeds, Stage 2 fails — is the summary still usable?" → yes, it's in the DB and a retry could resume from it later, (c) future "show me the summary" UI without a schema migration.

**Alternatives considered**: Don't persist (memory only) — rejected: loses debuggability and the Stage-2-retry option for free.

## R9 — Ollama service parity

**Decision**: Out of scope for this refinement. `ollama_service.py` stays as-is (single-pass, unused in the active path). A follow-up task may mirror the two-stage interface when local-LLM mode returns.

**Rationale**: Active production path is Gemini (feature 002). Spec FR-020 governs the system's behavior, and the system's LLM path is Gemini. Duplicating prompt work on a dormant service now is waste; the two-stage method signatures establish the interface to mirror later.
