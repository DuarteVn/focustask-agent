<!--
Sync Impact Report — 2026-07-02
Version change: 1.0.0 → 1.0.1
Modified principles:
  - VI. Free-Tier Deployability — clarified persistence wording: "no
    disk-persisted state" → "no state persisted to the Space's local
    filesystem"; external managed PostgreSQL job history (per Stack &
    Platform Constraints) is explicitly compatible, resolving the internal
    tension with that section.
Modified sections:
  - Stack & Platform Constraints — clarified "single request/queue pass"
    wording: reading a job's OWN persisted artifacts by job id (async
    polling/download) is allowed; the prohibition targets accounts,
    sessions, and cross-job/user state.
Added sections: none
Removed sections: none
Templates status:
  ✅ .specify/templates/plan-template.md — generic "Constitution Check" gate
     resolves against this file; no edit needed
  ✅ .specify/templates/spec-template.md — no constitution-mandated section
     changes; no edit needed
  ✅ .specify/templates/tasks-template.md — test tasks now REQUIRED with
     no-live-dependencies discipline, aligned with Principle V
  ✅ specs/001-focustask-agent/plan.md — Constitution Check now evaluated
     against filled v1.0.0 (plan.md:40); prior ⚠ resolved
Known open violations: none — all remediated in the same PR as this
amendment:
  - P-I: ollama_service.py rewritten as viable dormant fallback (PT-BR
    prompt, 3-section schema parity with gemini_service, settings keys
    ollama_base_url/ollama_model added to config.py)
  - P-III: numeric limits enforced in schemas.py (clamp maxima + warn on
    minima; covered by tests)
  - P-IV: root CLAUDE.md updated to Gemini-primary + PostgreSQL reality
    (tasks.md T021 done); spec.md Assumptions corrected (persistence and
    LGPD wording)
  - P-V: pytest suite added under backend/tests/ — mocked service
    boundaries, PT-BR fixtures, no live dependencies
Deferred TODOs: none
-->

# FocusTask Agent Constitution

## Core Principles

### I. Local-First, Zero-Cost Core

The core pipeline (audio → transcription → structured tasks) MUST be runnable without any
paid software, paid API tier, or mandatory API key. Transcription MUST remain local
(faster-whisper). A hosted LLM MAY serve as the primary structuring engine only while its
free tier suffices, and a local LLM path (Ollama) MUST remain architecturally viable — no
design decision may make the local fallback impossible.

*Rationale: portfolio project with zero budget; users must be able to self-host everything.*

### II. PT-BR First

Portuguese (PT-BR) is the primary language; English is secondary. Output language MUST
match the input audio language. Prompts, error messages shown to end users, and Telegram
copy MUST be written PT-BR-first. Test fixtures MUST include PT-BR audio/transcripts with
accents and colloquial speech ("vê lá", "não, espera").

*Rationale: the target user speaks PT-BR; ADHD-friendly output in the wrong language is noise.*

### III. ADHD-Friendly Output (NON-NEGOTIABLE)

Every user-facing result MUST keep the three-section structure: Direct Objective (ONE
sentence, ≤30 words), Micro-Task Checklist (3–10 atomic, action-verb-first items for
typical inputs), Execution Flow (3–6 stages, first = input, last = expected result). No
feature may add walls of text, nested hierarchies, or unbounded lists to the primary
output. Any change to output shape MUST be validated against these numeric limits.

*Rationale: scannability IS the product; violating it silently destroys the core value.*

### IV. Spec-Driven Development

No feature work without artifacts: spec.md (WHAT/WHY) → plan.md (HOW) → tasks.md (steps)
under `specs/<feature>/`. Code changes MUST trace to a functional requirement (FR-###).
Architecture changes MUST be recorded as spec refinements plus research decisions before
implementation. `CLAUDE.md` and contracts MUST be updated in the same change that makes
them stale.

*Rationale: solo project with AI agents as implementers — artifacts are the shared memory.*

### V. Tests Without Live Dependencies

Automated tests (pytest) MUST NOT require a live LLM key, a running PostgreSQL, network
access, or real audio processing. External services MUST be mocked at the service boundary
(LLM client, repository functions, whisper). End-to-end validation with live services
belongs in `quickstart.md` scenarios, executed manually or in opt-in CI. A red test suite
blocks merge.

*Rationale: deterministic, free, fast CI; live-service tests are flaky and cost quota.*

### VI. Free-Tier Deployability

The web app MUST run on Hugging Face Spaces free tier: CPU-only, limited RAM, ephemeral
filesystem, cold starts. Therefore: no state persisted to the Space's local filesystem
(render/export on the fly; job history lives in the external managed PostgreSQL permitted
by Stack & Platform Constraints), no GPU-dependent code paths, graceful behavior on slow
CPU transcription (progress feedback, duration-scaled timeouts). The desktop companion script MUST run on Windows without admin
privileges.

*Rationale: deployment target is fixed and free; anything that breaks there doesn't ship.*

## Stack & Platform Constraints

- Python 3.11+, FastAPI + Uvicorn backend under `backend/app/` (api/core/db/models/services/telegram layout)
- Transcription: faster-whisper local; LLM: Gemini free tier primary, Ollama dormant fallback (Principle I)
- Persistence: PostgreSQL for job history only — jobs MUST remain processable end-to-end in a single request/queue pass without reading prior user state (no accounts, no sessions, no cross-job reads); reading a job's OWN persisted artifacts by job id (async status polling, result download) is allowed
- Public unauthenticated demo endpoint is acceptable (portfolio scope); LGPD/GDPR compliance out of scope while no personal data is stored beyond job artifacts
- Windows-first for local dev and the desktop capture script (WASAPI loopback, no virtual cable)

## Development Workflow

- Spec Kit flow per feature: `/speckit-specify` → `/speckit-clarify` (if needed) → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`
- One branch per feature/refinement; merge to `main` via PR
- Quality gates before merge: pytest suite green (Principle V), relevant quickstart scenarios executed, artifacts (spec/plan/contracts/CLAUDE.md) consistent with the code being merged (Principle IV)
- Every plan.md MUST contain a Constitution Check gate evaluated against this file, re-checked after design (Phase 1)

## Governance

This constitution supersedes ad-hoc practices. Amendments require: a PR touching this file
with a Sync Impact Report, a semantic version bump (MAJOR = principle removal/redefinition,
MINOR = new principle or materially expanded guidance, PATCH = clarification/wording), and
propagation of affected guidance to templates and `CLAUDE.md` in the same PR. Compliance is
reviewed at every `/speckit-plan` Constitution Check and re-verified by `/speckit-analyze`;
violations MUST be either fixed or explicitly justified in the plan's Complexity Tracking
table — never silently ignored.

**Version**: 1.0.1 | **Ratified**: 2026-07-02 | **Last Amended**: 2026-07-02
