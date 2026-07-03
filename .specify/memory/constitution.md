<!--
Sync Impact Report — 2026-07-02
Version change: (template, unratified) → 1.0.0
Modified principles: n/a (initial adoption — all 6 principles new)
Added sections: Core Principles (I–VI), Stack & Platform Constraints,
  Development Workflow, Governance
Removed sections: none (template placeholders replaced)
Templates status:
  ✅ .specify/templates/plan-template.md — generic "Constitution Check" gate
     resolves against this file; no edit needed
  ✅ .specify/templates/spec-template.md — no constitution-mandated section
     changes; no edit needed
  ✅ .specify/templates/tasks-template.md — test-task guidance compatible with
     Principle V; no edit needed
  ⚠ specs/001-focustask-agent/plan.md — Constitution Check section written
     against "unfilled template" baseline; re-evaluated in remediation pass
     on branch chore/spec-remediation-constitution
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
filesystem, cold starts. Therefore: no disk-persisted state (render/export on the fly), no
GPU-dependent code paths, graceful behavior on slow CPU transcription (progress feedback,
duration-scaled timeouts). The desktop companion script MUST run on Windows without admin
privileges.

*Rationale: deployment target is fixed and free; anything that breaks there doesn't ship.*

## Stack & Platform Constraints

- Python 3.11+, FastAPI + Uvicorn backend under `backend/app/` (api/core/db/models/services/telegram layout)
- Transcription: faster-whisper local; LLM: Gemini free tier primary, Ollama dormant fallback (Principle I)
- Persistence: PostgreSQL for job history only — jobs MUST remain processable end-to-end in a single request/queue pass without reading prior user state (no accounts, no sessions)
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

**Version**: 1.0.0 | **Ratified**: 2026-07-02 | **Last Amended**: 2026-07-02
