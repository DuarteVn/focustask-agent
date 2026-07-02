# Tasks: FocusTask Agent

**Input**: Design documents from `/specs/001-focustask-agent/`

**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/api.md ✅ quickstart.md ✅

**Tests**: Not requested in spec — no test tasks included.

**Organization**: Grouped by user story. Each story is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable — different files, no incomplete-task dependencies
- **[Story]**: Owning user story (US1–US7 from spec.md)

---

## Phase 1: Setup

**Purpose**: Project initialization — directories, dependencies, env config.

- [x] T001 Create all missing `backend/app/` subdirectories and `__init__.py` files: `api/`, `api/routes/`, `core/`, `db/`, `models/`, `services/`, `ui/`
- [x] T002 Create `backend/requirements.txt` with pinned versions: fastapi, uvicorn[standard], faster-whisper, ollama, gradio, aiosqlite, python-multipart, pydantic-settings, mutagen
- [x] T003 [P] Create `backend/.env.example` documenting all env vars: WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, OLLAMA_BASE_URL, OLLAMA_MODEL, TEMP_AUDIO_DIR, DB_PATH, LOG_LEVEL, MAX_UPLOAD_BYTES, MAX_AUDIO_DURATION_SECONDS
- [x] T004 [P] Create `desktop/` directory with empty `desktop/capture.py` and `desktop/requirements.txt` (sounddevice, numpy, scipy, pyperclip, keyboard, requests)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST complete before any user story begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 Implement `backend/app/core/config.py`: pydantic-settings `Settings` class loading all env vars from `.env`; expose singleton `get_settings()`
- [x] T006 Implement `backend/app/db/database.py`: aiosqlite connection context manager, `init_db()` coroutine that creates `task_records` table and `idx_task_records_created_at` index on startup (schema from data-model.md)
- [x] T007 Implement `backend/app/db/repository.py`: `TaskRecord` dataclass matching SQLite schema; `insert_task_record()`, `get_task_record()`, `list_task_records()` async functions using raw SQL
- [x] T008 [P] Define all Pydantic schemas in `backend/app/models/schemas.py`: `JobCreatedResponse`, `JobStatusResponse`, `TaskSummaryItem`, `TaskListResponse`, `TaskDetailResponse`, `ExecutionFlow`, `HealthResponse`
- [x] T009 [P] Implement `backend/app/api/routes/health.py`: `GET /api/health` route; ping Ollama via HTTP to check availability; return `{"status": "ok", "whisper": "ready", "ollama": "ready"|"unavailable"}`
- [x] T010 Implement `backend/app/services/job_runner.py`: `ProcessingJob` dataclass (fields: job_id, status, created_at, updated_at, error_message, task_id, expires_at); module-level `jobs: dict[str, ProcessingJob]` with `asyncio.Lock`; `create_job()` and `get_job()` helpers; `start_ttl_loop()` coroutine that runs every 300s and marks jobs past `expires_at` as `failed` with `error_message="Processing timeout after 30 minutes"`
- [x] T011 Implement `backend/app/main.py`: FastAPI app creation; `RequestSizeLimitMiddleware` at 500MB; lifespan async context manager calling `init_db()` and `asyncio.create_task(start_ttl_loop())`; include health router at `/api`; configure CORS

**Checkpoint**: Foundation complete — database initializes, health endpoint responds, job store ready.

---

## Phase 3: User Story 1 — Audio Upload and Task Extraction (Priority: P1) 🎯 MVP

**Goal**: User uploads an audio file via REST API; system transcribes, filters noise, extracts 3-section structured output; user retrieves result by job ID.

**Independent Test** (quickstart V-002): `curl -X POST /api/jobs -F "file=@sample.mp3"` → poll `GET /api/jobs/{id}` until complete → `GET /api/tasks/{task_id}` returns non-empty `objective`, `checklist` (3–10 items), and `flow` with all 3 parts. No curl test requires a browser.

- [x] T012 [P] [US1] Implement `backend/app/services/whisper_service.py`: `WhisperService` class; load `faster_whisper.WhisperModel` on init using WHISPER_MODEL/DEVICE/COMPUTE_TYPE from config; `transcribe(file_path: str) -> tuple[str, str]` returning (raw_text, detected_language); runs in ThreadPoolExecutor to avoid blocking event loop
- [x] T013 [P] [US1] Implement `backend/app/services/ollama_service.py`: `OllamaService` class; `structure(transcript: str, language: str) -> dict` calling Ollama with `format="json"`, system prompt specifying keys `objective`/`checklist`/`flow` with types; strip ` ```json ``` ` markdown wrappers before `json.loads()`; retry up to 2 times on `JSONDecodeError`; validate: objective non-empty, checklist 1–20 non-empty strings, flow has input/logic/output keys; raise `ValueError` on 3rd failure
- [x] T014 [US1] Implement background job pipeline in `backend/app/services/job_runner.py`: `run_job(job_id, temp_file_path)` coroutine; status transitions: received→transcribing (call whisper_service)→analyzing (call ollama_service)→complete (insert TaskRecord to DB, set task_id) | failed (set error_message); check audio duration via `mutagen` before transcribing and fail if >MAX_AUDIO_DURATION_SECONDS; delete temp file on both complete and failed; update `job.updated_at` on each status change
- [x] T015 [US1] Implement `POST /api/jobs` in `backend/app/api/routes/jobs.py`: accept `multipart/form-data` with `file` field; validate MIME type (mp3/wav/ogg/m4a/webm) — return 422 if invalid; save to temp file in TEMP_AUDIO_DIR; call `create_job()` + `asyncio.create_task(run_job(...))` in ThreadPoolExecutor; return 202 `JobCreatedResponse`
- [x] T016 [US1] Implement `GET /api/jobs/{job_id}` in `backend/app/api/routes/jobs.py`: call `get_job(job_id)`; return 404 if not found; return `JobStatusResponse` with all fields; include `task_id` when status is `complete`
- [x] T017 [US1] Implement `GET /api/tasks/{task_id}` in `backend/app/api/routes/tasks.py`: call `get_task_record(task_id)`; return 404 if not found; assemble `TaskDetailResponse` deserializing `checklist` JSON field
- [x] T018 [US1] Register job and task routers on FastAPI app at `/api` prefix in `backend/app/main.py`; run quickstart V-001 (health) and V-002 (full upload→poll→retrieve) manually to confirm end-to-end works

**Checkpoint**: Core pipeline fully functional via curl/httpx. US1 independently verified.

---

## Phase 4: User Story 3 — Structured Output Review (Priority: P2)

**Goal**: User sees all 3 output sections (Direct Objective, Micro-Tasks Checklist, Execution Flow) plus raw transcript in a scannable Gradio panel after uploading a file.

**Independent Test** (quickstart V-005): Upload `sample.mp3` via Gradio UI at `http://localhost:8000/ui` → output panel shows 3 labeled sections with non-empty content; raw transcript visible alongside.

- [x] T019 [US3] Implement Gradio Blocks UI in `backend/app/ui/gradio_app.py`: file upload input (accepted types: audio); output panel with 3 `gr.Markdown` sections labeled "🎯 Objetivo Direto", "✅ Checklist de Tarefas", "⚙️ Fluxo de Execução"; `gr.Textbox` for raw transcript; submit handler that calls `POST /api/jobs`, polls `GET /api/jobs/{id}` every 3s until complete or failed, then calls `GET /api/tasks/{task_id}` and populates all output components
- [x] T020 [US3] Mount Gradio app on FastAPI in `backend/app/main.py` using `gr.mount_gradio_app(app, demo, path="/ui")`; ensure `/api` routes still resolve correctly

**Checkpoint**: Gradio UI displays full 3-section output from a file upload.

---

## Phase 5: User Story 6 — Processing Status Feedback (Priority: P2)

**Goal**: User submits a long audio file and sees live status transitions (Received → Transcribing → Analyzing → Done) without a page reload.

**Independent Test** (quickstart V-005 step 3): Upload a 2-min file; observe `gr.Label` or `gr.Textbox` status field updating from "Recebido" → "Transcrevendo..." → "Analisando..." → "Pronto!" without manual page refresh.

- [x] T022 [US6] Add status display component (`gr.Label` or styled `gr.Textbox`) to Gradio Blocks in `backend/app/ui/gradio_app.py`; update submit handler to set status text on each poll iteration before final result population; show plain-language PT-BR stage labels; show error message text on job failure

**Checkpoint**: Status transitions visible in UI during processing. Users not left on blank screen.

---

## Phase 6: User Story 2 — Live Microphone Recording (Priority: P2)

**Goal**: User clicks record, speaks, stops, and gets structured output — identical to file upload flow but using browser mic.

**Independent Test**: Click record button in Gradio → speak a 30s work instruction → stop → verify structured output appears (same pass criteria as V-002).

- [x] T023 [US2] Add microphone recording tab to Gradio Blocks in `backend/app/ui/gradio_app.py` using `gr.Audio(sources=["microphone"])` component; wire to same upload-poll-display pipeline as file upload (T019 handler); both tabs share output panel components

**Checkpoint**: Mic recording produces identical output to file upload.

---

## Phase 7: User Story 4 — Copy Structured Output (Priority: P3)

**Goal**: User clicks one button to copy all 3 sections with formatting to clipboard for use in other tools.

**Independent Test** (quickstart V-005 step 6): After output renders, click copy button → paste into Notepad → all 3 section labels and content present; checklist items appear as a list, not collapsed.

- [x] T024 [US4] Add `gr.Button("📋 Copiar tudo")` to output panel in `backend/app/ui/gradio_app.py`; click handler formats all 3 sections into labeled Markdown string (`## Objetivo Direto\n...\n## Checklist\n- item1\n...\n## Fluxo\n...`) and uses `gr.ClipboardButton` or `pyperclip.copy()` via a hidden textbox; verify checklist items are newline-separated

**Checkpoint**: Clipboard contains fully formatted 3-section Markdown.

---

## Phase 8: User Story 7 — Task History (Priority: P3)

**Goal**: User opens history view, sees recent processed tasks newest-first, clicks one to read full output again.

**Independent Test** (quickstart V-004 + V-008): Process a file, open history tab → task appears with objective preview and timestamp; click it → full 3-section output loads.

- [x] T025 [US7] Implement `GET /api/tasks` in `backend/app/api/routes/tasks.py`: call `list_task_records(limit)` with default 20, max 100; return `TaskListResponse` with `tasks: list[TaskSummaryItem]` and `total`
- [x] T026 [US7] Add history tab to Gradio Blocks in `backend/app/ui/gradio_app.py`: `gr.Button("Atualizar histórico")` calls `GET /api/tasks`; display results in `gr.Dataframe` with columns (timestamp, objective preview, language); clicking a row calls `GET /api/tasks/{task_id}` and populates the output panel

**Checkpoint**: Task history browseable; previously processed tasks retrievable by URL (SC-009 verified via V-008).

---

## Phase 9: User Story 5 — Desktop Meeting Capture (Priority: P3)

**Goal**: User presses F9 to start capturing system audio + mic; presses F9 again to stop; script uploads, polls, and delivers structured output to clipboard — no browser required.

**Independent Test** (quickstart V-009): Run `python desktop/capture.py`; press F9; play audio for 30s; press F9 again; verify `recording_<ts>.wav` created, job ID displayed, output copied to clipboard, local file preserved.

- [x] T027 [US5] Implement WASAPI loopback device enumeration in `desktop/capture.py`: scan `sounddevice.query_devices()` for device with "stereo mix" or "what u hear" in name (case-insensitive); if not found, print actionable message instructing user to enable "Stereo Mix" in Windows Sound Settings → Recording tab → Show Disabled Devices; fall back to recording mic-only with a warning
- [x] T028 [US5] Implement F9 hotkey toggle in `desktop/capture.py` using `keyboard.add_hotkey("F9", toggle_recording)`; global `is_recording` flag; print "🎙 Gravação iniciada..." on start, "⏹ Gravação encerrada." on stop; handle KeyboardInterrupt for clean exit
- [x] T029 [US5] Implement dual-channel simultaneous capture in `desktop/capture.py`: use two `sounddevice.InputStream` callbacks (loopback + mic) running in separate threads; mix to mono 16kHz using `numpy` averaging; write to `recording_<timestamp>.wav` using `scipy.io.wavfile.write`; target 16000 Hz sample rate throughout (Whisper-optimal)
- [x] T030 [US5] Implement cloud API integration in `desktop/capture.py`: on stop, POST `.wav` to `API_BASE_URL + /api/jobs` (configurable via env var or `config.ini`); print received `job_id`; poll `GET /api/jobs/{job_id}` every 5s until `status == "complete"` or `"failed"`; on complete, GET `/api/tasks/{task_id}` to retrieve full output; format output as Markdown string
- [x] T031 [US5] Implement output delivery and failure handling in `desktop/capture.py`: on success, copy Markdown to clipboard via `pyperclip.copy()`; print "✅ Copiado para a área de transferência"; on any HTTP error or `status == "failed"`, preserve local `.wav` file and print error message with file path and job_id (FR-019)

**Checkpoint**: Full desktop capture flow works end-to-end on Windows without admin privileges (SC-008).

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Hardening that affects multiple user stories.

- [x] T032 [P] Add structured logging using Python `logging` module at all service layer entry/exit points in `backend/app/services/`; log level from `Settings.LOG_LEVEL`; include `job_id` in all log messages
- [x] T033 [P] Audit all route handlers in `backend/app/api/routes/` for FR-011 compliance: every failure path returns a plain-language error message in `{"error": "..."}` format; no raw tracebacks exposed
- [x] T034 Run all quickstart.md validation scenarios V-001 through V-010; fix any failures; confirm SC-001 (60s for 1-min audio), SC-004 (no filler phrases in output), SC-006 (job ID in <5s), SC-008 (desktop, no admin), SC-009 (task by URL)
- [x] T035 [P] Update `CLAUDE.md` Stack section and Common Commands to reflect final project structure; add `desktop/capture.py` run instructions; correct "Stateless — no DB" to reflect SQLite persistence

---

## Phase 11: MySQL Migration (Blocking for US8) — *Added 2026-07-01*

**Purpose**: Replace SQLite/aiosqlite with external MySQL/aiomysql. FR-022 superseded by FR-030. Must complete before any Telegram work.

**⚠️ BLOCKING**: Phase 12 cannot start until T036–T039 complete.

- [x] T036 Update `backend/requirements.txt`: remove `aiosqlite`; remove `aiomysql` (if present); add `asyncpg>=0.29`, `python-telegram-bot>=20.0`, `pydub>=0.25`; add comment `# ffmpeg must be installed as system dep (not pip)`
- [x] T037 Rewrite `backend/app/db/database.py`: replace aiosqlite with `asyncpg.create_pool(dsn=Settings.DATABASE_URL)`; expose `get_pool()` accessor; `init_db()` creates pool and executes `CREATE TABLE IF NOT EXISTS task_records` with PostgreSQL syntax (TEXT PRIMARY KEY, TIMESTAMPTZ, etc.); `close_db()` awaits `pool.close()` in lifespan shutdown
- [x] T038 Rewrite `backend/app/db/repository.py`: replace aiosqlite cursor pattern with asyncpg pool (`async with pool.acquire() as conn`; use `conn.fetch`, `conn.fetchrow`, `conn.execute`); change all SQL placeholders from `?` to `$1/$2/...` (PostgreSQL positional params); `TaskRecord` dataclass unchanged; all 3 CRUD functions updated
- [x] T039 [P] Update `backend/app/core/config.py`: remove `DB_PATH`; add `DATABASE_URL: str` (Supabase Transaction pooler URL); add `TELEGRAM_BOT_TOKEN: str = ""`, `TELEGRAM_WEBHOOK_URL: str = ""` (empty = polling mode), `WEB_PANEL_BASE_URL: str = "http://localhost:8000"`

**Checkpoint**: API starts, health endpoint responds, task CRUD works against Supabase PostgreSQL.

---

## Phase 12: User Story 8 — Telegram Bot (Priority: P1) — *Added 2026-07-01*

**Goal**: User sends voice message to bot → bot ACKs within 5s → bot replies with 3-section MarkdownV2 output + Web Panel link when job completes.

**Independent Test**: Provision bot via @BotFather; set `TELEGRAM_BOT_TOKEN`; run in polling mode (`TELEGRAM_WEBHOOK_URL` empty); send 30s PT-BR voice message; verify ACK reply with job_id within 5s; verify final reply has all 3 sections + clickable URL; verify TaskRecord in Supabase PostgreSQL.

- [x] T040 [P] [US8] Implement `backend/app/services/audio_converter.py`: `convert_to_wav(input_path: str, output_path: str) -> None` using `pydub.AudioSegment.from_file()`; export as WAV 16000 Hz mono (Whisper-optimal); raise `RuntimeError("ffmpeg not found in PATH — install ffmpeg")` if pydub cannot locate ffmpeg
- [x] T041 [US8] Implement `backend/app/telegram/handlers.py`: `voice_or_audio_handler(update, context)` async; check file size ≤20 MB — reply `"❌ Arquivo muito grande (max 20 MB)"` and return if exceeded; download to temp file in `TEMP_AUDIO_DIR`; call `audio_converter.convert_to_wav()` if extension is `.ogg`/`.oga`/`.opus`; call `create_job()` + `asyncio.create_task(run_job_telegram(job_id, wav_path, TelegramContext(...)))`; reply `"⏳ Processando seu áudio… Job ID: {job_id}"`
- [x] T042 [US8] Implement `backend/app/telegram/bot.py`: build `Application` via `ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()`; register `MessageHandler(filters.VOICE | filters.AUDIO, voice_or_audio_handler)`; `setup_bot() -> Application`; if `TELEGRAM_WEBHOOK_URL` non-empty call `await app.bot.set_webhook(url)`; expose module-level `application` instance for use in `run_job_telegram`
- [x] T043 [US8] Extend `backend/app/services/job_runner.py`: add `TelegramContext` dataclass (`chat_id: int`, `message_id: int`, `user_id: int`); add `telegram_ctx: TelegramContext | None = None` to `ProcessingJob`; implement `run_job_telegram(job_id, file_path, ctx)` — calls `run_job(job_id, file_path)`; on complete, formats MarkdownV2 reply (all 3 sections + `WEB_PANEL_BASE_URL/ui?task_id={task_id}` link) and calls `application.bot.send_message(chat_id=ctx.chat_id, text=..., parse_mode="MarkdownV2")`; on failure, sends plain error text + job_id to same `chat_id`
- [x] T044 [US8] Wire Telegram in `backend/app/main.py`: call `setup_bot()` in lifespan startup; if webhook mode add `POST /telegram/webhook` route that calls `application.update_queue.put(Update.de_json(body, bot))`; call `application.shutdown()` in lifespan shutdown; run `application.start()` before entering webhook mode or call `application.run_polling()` in background thread for polling mode
- [x] T045 [P] [US8] Update `backend/.env.example`: add `DATABASE_URL=postgresql+asyncpg://user:pass@host:6543/postgres` (Supabase Transaction pooler); add `TELEGRAM_BOT_TOKEN=` (empty), `TELEGRAM_WEBHOOK_URL=` (empty for polling), `WEB_PANEL_BASE_URL=http://localhost:8000`; remove `DB_PATH`

**Checkpoint**: Bot receives voice → ACKs → replies with checklist + link. TaskRecord persists in Supabase PostgreSQL (SC-009 valid via Telegram).

---

## Phase 13: Re-Polish — *Added 2026-07-01*

**Purpose**: Re-validate all SCs after MySQL migration + Telegram addition. T034/T035 outdated by stack changes.

- [ ] T046 Manual end-to-end re-validation: run quickstart V-001 through V-010 against MySQL backend; run Telegram manual test (voice msg → ACK → reply → MySQL record); confirm SC-001, SC-004, SC-006, SC-009, SC-010; fix any regressions from MySQL migration
- [ ] T047 [P] Update `CLAUDE.md`: replace SQLite notes with Supabase PostgreSQL (`DATABASE_URL` env var); add `ffmpeg` system requirement note; add Telegram polling startup instructions; update Stack section (remove aiosqlite, add asyncpg/python-telegram-bot/pydub)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Requires Phase 1 — **blocks all user stories**
- **Phase 3 (US1)**: Requires Phase 2 — MVP deliverable; unblocks all later phases
- **Phase 4 (US3)**: Requires Phase 3 (US1 API must work)
- **Phase 5 (US6)**: Requires Phase 4 (must have status display target in UI)
- **Phase 6 (US2)**: Requires Phase 4 (shares Gradio pipeline)
- **Phase 7 (US4)**: Requires Phase 4 (output panel must exist to add copy button)
- **Phase 8 (US7)**: Requires Phase 3 (needs `/api/tasks` history endpoint) + Phase 4 (Gradio)
- **Phase 9 (US5)**: Requires Phase 3 (desktop calls `/api/jobs` and `/api/tasks/{id}`)
- **Phase 10 (Polish)**: Requires all Phase 1–9 complete *(completed pre-2026-07-01)*
- **Phase 11 (MySQL Migration)**: Requires Phase 10 — **blocks Phase 12**
- **Phase 12 (US8 Telegram)**: Requires Phase 11 (MySQL + new config must exist)
- **Phase 13 (Re-polish)**: Requires Phase 12 complete

### User Story Dependencies (after Foundational)

- **US1 (P1)**: No user story dependencies — start immediately
- **US3 (P2)**: Depends on US1 API
- **US6 (P2)**: Depends on US3 UI
- **US2 (P2)**: Depends on US3 UI (shares components)
- **US4 (P3)**: Depends on US3 UI
- **US7 (P3)**: Depends on US1 API + US3 UI
- **US5 (P3)**: Depends on US1 API only (no Gradio dependency)
- **US8 (P1)**: Depends on Phase 11 (MySQL) + US1 job pipeline (reuses `job_runner.py`)

### Within Each User Story

- Services before routes before integration
- T012, T013 (services) before T014 (orchestrator) before T015–T017 (routes)

---

## Parallel Opportunities

### Phase 2 — Foundational

```
T006 (database.py) ──────────┐
T007 (repository.py) ←T006  │
T008 (schemas.py) ───────────┼── all in parallel except T007↑T006, T011↑T008
T009 (health.py)  ───────────┤
T010 (main.py)    ───────────┘
T011 (job_runner.py) ←T008
```

### Phase 3 — US1

```
T012 (whisper_service.py) ──┐
T013 (ollama_service.py) ───┼── parallel; T014 needs both done
                            ↓
T014 (job_runner pipeline) → T015 → T016 → T017 → T018
```

### Phase 9 — US5

```
T027 (device enum) → T028 (hotkey) → T029 (capture) → T030 (upload/poll) → T031 (deliver)
(sequential: each task extends capture.py, building on the previous)
```

### Phase 11 — MySQL Migration

```
T036 (requirements.txt) ─────────────────────┐
T037 (database.py) ← T036                    │ T039 parallel with T037/T038
T038 (repository.py) ← T037                 ├── all done before Phase 12
T039 [P] (config.py) ────────────────────────┘
```

### Phase 12 — US8 Telegram

```
T040 [P] (audio_converter.py) ─────────────────────────────┐
T043 (job_runner extensions) ──────────────────────────────┤
                                                           ↓
T041 (handlers.py) ← T040, T043 ──┐
T042 (bot.py) ← T041 ─────────────┼──→ T044 (main.py wire) → T045 [P] (env.example)
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (T012–T018)
4. **STOP and validate**: Run quickstart V-001, V-002, V-003, V-007, V-008
5. REST API is shippable; desktop script usable via curl

### Incremental Delivery

1. Phase 1+2 → Foundation *(done)*
2. Phase 3 (US1) → curl-testable pipeline; demo via REST (MVP) *(done)*
3. Phase 4 (US3) → Gradio UI; visually shareable demo *(done)*
4. Phase 5+6 (US6+US2) → full Gradio experience *(done)*
5. Phase 7 (US4) → copy-to-clipboard *(done)*
6. Phase 8 (US7) → history persistence *(done)*
7. Phase 9 (US5) → desktop companion *(done)*
8. Phase 10 → polish + validate all SCs *(done)*
9. **Phase 11 → MySQL migration** (unblocks Telegram)
10. **Phase 12 (US8) → Telegram Bot** — mobile-first P1 input channel
11. **Phase 13 → re-validate all SCs against new stack**

---

## Notes

- `[P]` = different files with no dependency on incomplete tasks in same phase
- `[USx]` maps task to user story for traceability
- Each user story phase is independently testable — verified by its **Independent Test**
- No test tasks generated (not requested in spec)
- All tasks reference exact file paths per plan.md project structure
