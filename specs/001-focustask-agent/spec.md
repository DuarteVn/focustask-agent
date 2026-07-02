# Feature Specification: FocusTask Agent

**Feature Branch**: `001-focustask-agent`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "FocusTask Agent — ADHD-friendly audio-to-task pipeline for Hugging Face Spaces portfolio project."

## Architecture

Single cloud deployment. One API handles both the web interface and the desktop script.

**Core pipeline**: audio upload → async background job → transcription → noise filter → LLM structuring → persisted TaskRecord → structured output (Direct Objective + Micro-Tasks Checklist + Execution Flow).

**Why async**: audio files up to 45 minutes take significant processing time. The upload endpoint returns a job ID immediately (HTTP 202); the client polls for completion. No HTTP timeouts, no blocking the caller.

**Why persistent**: output is stored in a database so the owner can access any past checklist from any device via a unique URL, without re-processing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Audio Upload and Task Extraction (Priority: P1)

A user (manager, team lead, or knowledge worker with ADHD) has an audio recording describing a task or set of work instructions. They upload the audio file to the interface. The system transcribes it, filters out tangents and verbal noise, and delivers a clean structured task breakdown in three sections.

**Why this priority**: This is the core value proposition. The entire product exists to do this one thing. Nothing else is viable without it working end-to-end.

**Independent Test**: Upload a sample audio file containing tangents (e.g., "ah, vê lá com o fulano... não, espera, faz aquilo antes"). Verify that output panel displays all 3 sections and that noise phrases are absent from the output.

**Acceptance Scenarios**:

1. **Given** a user has a valid audio file, **When** they upload it and submit, **Then** the system processes it and displays the structured output panel with all 3 sections
2. **Given** the audio contains verbal noise and tangents, **When** the output is generated, **Then** filler phrases, self-corrections, and off-topic content do not appear in any output section
3. **Given** processing completes, **When** user views the output, **Then** the raw transcript is also visible for reference alongside the structured output

---

### User Story 2 - Live Microphone Recording (Priority: P2)

A user wants to capture a task on the fly without pre-recording. They click a record button, speak their instruction, stop recording, and immediately get structured output — no file management required.

**Why this priority**: Reduces friction for spontaneous task capture, which is critical for ADHD users who need to externalize thoughts immediately before they disappear.

**Independent Test**: Click record, speak a work instruction, stop recording. Verify the system processes it identically to a file upload and shows structured output.

**Acceptance Scenarios**:

1. **Given** user clicks the record button, **When** they finish speaking and stop, **Then** the recording is automatically submitted for processing
2. **Given** a live recording is submitted, **When** processing completes, **Then** output is identical in structure to a file-uploaded result

---

### User Story 3 - Structured Output Review (Priority: P2)

User reads the three-section output — direct objective, micro-task checklist, and execution flow — and immediately understands what they need to do without re-reading the original audio.

**Why this priority**: The structured output IS the product. If the presentation is cluttered, too long, or unclear, the ADHD-friendly goal fails entirely.

**Independent Test**: Given a known audio input, verify output sections are present, objective is one sentence, checklist has specific steps, and flow shows input/logic/output.

**Acceptance Scenarios**:

1. **Given** processing completes, **When** user reads the Direct Objective section, **Then** it contains exactly one sentence stating what must be delivered
2. **Given** processing completes, **When** user reads the Micro-Tasks Checklist, **Then** each item is a specific, independently actionable step (not a vague category)
3. **Given** processing completes, **When** user reads the Execution Flow section, **Then** it clearly labels what enters (input), what happens (logic), and what comes out (expected result)

---

### User Story 4 - Copy Structured Output (Priority: P3)

User copies the structured task breakdown to use in another tool (task manager, team chat, notes app).

**Why this priority**: The output needs to travel. Users won't manually retype; if they can't copy it easily, the workflow breaks.

**Independent Test**: Click copy button, paste into a text editor, verify all 3 sections appear with formatting intact.

**Acceptance Scenarios**:

1. **Given** structured output is displayed, **When** user clicks copy, **Then** formatted text is placed in clipboard with section labels and checklist items preserved
2. **Given** user pastes the copied content, **Then** checklist items appear as a list, not collapsed into a single block of text

---

### User Story 5 - Desktop Meeting Capture (Priority: P3)

During a live meeting on Meet, Discord, or any video call tool, the user runs a local Python script. They press F9 to start capturing system audio (other participants) and microphone audio (themselves) simultaneously. When the meeting ends or a task is discussed, they press F9 again to stop. The script mixes both channels and uploads the recording to the cloud API. Since processing is asynchronous, the script receives a job ID, polls for completion, and when done delivers the structured breakdown to clipboard automatically — no manual upload or browser interaction required.

**Why this priority**: Closes the loop for the most common real-world scenario (tasks assigned in meetings). The cloud async architecture means even a 45-minute recording is handled stably — the script just waits for the job to complete.

**Independent Test**: Run the desktop script, press F9, play a YouTube video while speaking into the mic for 2 minutes, press F9 again. Verify a .wav is created, uploaded to cloud API, job ID received, script polls, and structured output is copied to clipboard within 5 minutes.

**Acceptance Scenarios**:

1. **Given** the desktop script is running, **When** user presses F9, **Then** recording starts capturing both system audio and microphone simultaneously with a terminal indicator
2. **Given** recording is active, **When** user presses F9 again, **Then** recording stops, channels are mixed into a single audio file, uploaded to the cloud API, and a job ID is displayed in the terminal
3. **Given** the job is processing, **When** the script polls and job completes, **Then** the structured Markdown output is copied to the system clipboard automatically
4. **Given** the upload or processing fails, **When** the error occurs, **Then** the local audio file is preserved and the user is notified via terminal with the file path and job ID (if any) so they can retry

---

### User Story 6 - Processing Status Feedback (Priority: P2)

User submits a long audio file (e.g., 45 minutes) and needs to know the job is progressing, not silently broken. The web interface shows a live status indicator so the user is not left waiting on a blank screen.

**Why this priority**: Async processing without feedback is indistinguishable from a broken system, especially for ADHD users who lose trust and re-submit.

**Independent Test**: Upload a 2-minute file, verify status transitions from "Received" → "Transcribing" → "Analyzing" → "Done" are visible in the UI without a page reload.

**Acceptance Scenarios**:

1. **Given** audio is submitted, **When** upload completes, **Then** UI immediately shows "Processing — your checklist is being prepared" with a job ID
2. **Given** job is running, **When** status changes (transcribing / analyzing / done), **Then** UI updates to reflect current stage without requiring a page reload or manual refresh
3. **Given** job fails at any stage, **When** failure occurs, **Then** UI shows a plain-language error with the job ID so the user can report or retry

---

### User Story 7 - Task History (Priority: P3)

User wants to review a checklist from a meeting that happened two days ago. They open the web interface, see a list of their recent processed tasks, and click one to read the full output again.

**Why this priority**: Without history, every checklist is ephemeral — processed once and gone if the user closes the tab. Persistence makes the tool genuinely useful beyond the first session.

**Independent Test**: Process an audio file, close the browser, reopen the app, verify the task appears in history with its timestamp and objective summary.

**Acceptance Scenarios**:

1. **Given** a task has been successfully processed, **When** user opens the history view, **Then** the task appears with its creation timestamp and the Direct Objective as a preview
2. **Given** user clicks a task in history, **When** the task detail loads, **Then** all three output sections (Direct Objective, Checklist, Execution Flow) are displayed in full
3. **Given** the history contains multiple tasks, **When** user browses, **Then** tasks are ordered newest-first

---

### User Story 8 - Telegram Bot Audio Capture (Priority: P1)

A user sends or forwards a voice message or audio file to the FocusTask Telegram Bot from any device. The bot acknowledges receipt immediately, forwards the audio to the backend async pipeline, and replies in the same chat with the complete structured checklist when processing completes. A link to the Web Panel is included for users who want the full visual view.

**Why this priority**: Mobile-first, zero-friction capture. ADHD users need to externalize tasks instantly from wherever they are. Telegram is already installed; sending a voice memo is one tap — no file management, no browser, no upload UI. Closes the gap between spontaneous thought and structured task.

**Independent Test**: Send a 30-second voice message in PT-BR to the bot. Verify the bot replies within the processing window with all 3 output sections in formatted text and a valid clickable Web Panel link.

**Acceptance Scenarios**:

1. **Given** user sends a voice message or forwards an audio file to the bot, **When** the bot receives it, **Then** the bot replies within 5 seconds with an acknowledgement message containing the job ID
2. **Given** the processing job completes, **When** the system sends the Telegram reply, **Then** all 3 output sections (Direct Objective, Checklist, Execution Flow) appear as formatted MarkdownV2 text in the same chat
3. **Given** the reply is sent, **When** user reads it, **Then** a clickable URL pointing to the Web Panel task detail page is included at the end of the reply
4. **Given** audio arrives in .ogg/.opus format (Telegram default for voice messages), **When** the backend processes it, **Then** it is converted to WAV before passing to the transcription service
5. **Given** processing fails at any stage, **When** the failure occurs, **Then** the bot replies in the same chat with a plain-language error message and the job ID

---

### Edge Cases

- What happens when audio contains no actionable work content (e.g., casual chitchat, background noise only)?
- How does the Cloud version handle audio files longer than 3 minutes? (must reject with clear error, not silently truncate)
- How does the Local version handle very long audio files (45+ minutes)? (must complete without timeout)
- What if transcription produces garbled or nonsensical text?
- What if the user's microphone access is denied by the browser?
- What happens if the LLM processing step fails or times out?
- What if the audio is entirely in a language the system cannot transcribe?
- What if system audio capture is blocked by the OS (e.g., audio routed to Bluetooth device)?
- What if the mixed .wav file exceeds the API's size or duration limit?
- What happens if the user presses F9 to stop before any meaningful audio is captured?
- What if the cloud API is unreachable when the desktop script tries to upload?
- What if the async job is stuck in a processing state indefinitely (no completion, no failure)?
- What if two concurrent uploads of the same audio file create duplicate tasks in history?
- What if the database storage grows unbounded (no retention policy in v1)?
- What if a Telegram voice file exceeds 20 MB (Telegram Bot API download limit for bots)?
- What if the Telegram webhook endpoint is unreachable when Telegram tries to deliver an update (update is lost, not retried indefinitely)?
- What if OGG/OPUS conversion fails due to missing ffmpeg on the server?
- What if the PostgreSQL/Supabase connection is unavailable when a completed job tries to persist the TaskRecord?
- What if the same Telegram user sends multiple voice messages before the first job completes?
- What if the TELEGRAM_BOT_TOKEN is invalid or revoked mid-session?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept audio input via file upload supporting common formats (mp3, wav, ogg, m4a, webm)
- **FR-002**: System MUST accept audio input via live microphone recording directly in the interface
- **FR-003**: System MUST transcribe audio to raw text and display the raw transcript alongside the structured output
- **FR-004**: System MUST filter verbal noise, self-corrections, filler words, and off-topic tangents from the transcription before analysis
- **FR-005**: System MUST extract a single direct objective sentence stating what must be delivered
- **FR-006**: System MUST generate a micro-tasks checklist where each item is a specific, independently actionable step
- **FR-007**: System MUST generate an execution flow section with three labeled parts: what enters (input), what is processed (logic), and what the expected result is (output)
- **FR-008**: System MUST present the three output sections in a visually distinct, scannable panel — not a wall of text
- **FR-009**: System MUST provide a one-click copy action for the complete structured output
- **FR-010**: System MUST show a processing indicator while transcription and analysis are running
- **FR-011**: System MUST display a clear, plain-language error message when any processing step fails
- **FR-012**: System MUST support audio in Portuguese (PT-BR) as the primary language, with English as secondary
- **FR-013**: The API MUST accept audio file uploads via HTTP POST from external clients (desktop script) with no authentication required
- **FR-020**: The API MUST accept audio uploads up to 45 minutes in duration without HTTP timeout by returning a job ID immediately (HTTP 202) and processing in background
- **FR-021**: The API MUST expose a job status endpoint that returns the current processing stage (received / transcribing / analyzing / complete / failed) and the output when complete
- **FR-022**: *[SUPERSEDED by FR-030 — 2026-07-01]* The API MUST persist every successfully completed TaskOutput to a SQLite database, including creation timestamp and a unique shareable URL (UUID-based)
- **FR-023**: The API MUST expose a task history endpoint returning recent completed tasks ordered newest-first, with each entry showing the Direct Objective and creation timestamp
- **FR-024**: The API MUST expose a task detail endpoint that returns the full TaskOutput (all three sections) for a given task ID
- **FR-014**: The desktop script MUST capture system audio output (loopback) and microphone input simultaneously on the local machine
- **FR-015**: The desktop script MUST mix both captured audio channels into a single audio file before sending
- **FR-016**: The desktop script MUST use a configurable hotkey (default: F9) to toggle recording start/stop without requiring mouse interaction
- **FR-017**: The desktop script MUST upload the mixed audio file to the cloud production API, receive a job ID, poll the status endpoint until completion, and retrieve the structured Markdown response
- **FR-018**: The desktop script MUST deliver the structured output by copying it to the system clipboard by default; saving as a `.md` file or opening in the default browser are optional alternatives (user-configurable)
- **FR-019**: The desktop script MUST preserve the local .wav file on API failure and inform the user via terminal output
- **FR-025**: System MUST expose a Telegram Bot that accepts voice messages and forwarded audio files via the Telegram Bot API webhook at `POST /telegram/webhook`
- **FR-026**: System MUST convert incoming .ogg/.opus audio (Telegram's default voice format) to WAV before passing to the transcription service
- **FR-027**: Telegram Bot MUST acknowledge receipt of an audio message within 5 seconds by replying with a processing confirmation message containing the job ID
- **FR-028**: When a Telegram-originated job completes, the system MUST send the full structured output to the originating `chat_id` as a MarkdownV2-formatted Telegram message
- **FR-029**: Every Telegram reply containing structured output MUST include a clickable URL to the Web Panel task detail page for the completed TaskRecord
- **FR-030**: System MUST persist every successfully completed TaskOutput to an external PostgreSQL database (Supabase), including creation timestamp and a unique UUID-based shareable URL; connection configured via `DATABASE_URL` environment variable — supersedes FR-022

### Key Entities

- **AudioInput**: User-provided audio content (file, live browser recording, or mixed desktop capture), format, and approximate duration
- **ProcessingJob**: Background job tracking audio processing; states: received → transcribing → analyzing → complete | failed; holds job ID and current stage
- **Transcript**: Raw text output from speech-to-text, with detected language
- **TaskOutput**: Composed of DirectObjective (single sentence), MicroTaskChecklist (ordered list of steps), and ExecutionFlow (input / logic / output triple)
- **TaskRecord**: Persisted TaskOutput with unique UUID, creation timestamp, and shareable URL; stored in external PostgreSQL database via Supabase (see FR-030)
- **DesktopCapture**: Local recording session with system audio channel, microphone channel, mixed output file path, and recording duration
- **TelegramContext**: Telegram-specific metadata attached to a bot-originated job; holds `chat_id` (reply target), `message_id` (original message reference), `file_id` (Telegram file handle for download), and `user_id` (Telegram user identifier)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users complete the full audio-to-structured-output flow in under 60 seconds for a 1-minute audio recording
- **SC-002**: The Direct Objective section contains a single sentence of 30 words or fewer in 90% of processed inputs
- **SC-003**: The Micro-Tasks Checklist contains between 3 and 10 items for a typical 30–90 second work instruction recording
- **SC-004**: Verbal noise phrases ("vê lá", "espera", "ah", "não, volta lá") are absent from all output sections in 95% of cases where they appear in the transcript
- **SC-005**: A first-time user with no instructions can complete a full session (upload → output) without guidance, on first attempt
- **SC-006**: System processes audio recordings up to 45 minutes without failure or HTTP timeout; upload returns job ID within 5 seconds regardless of file size
- **SC-007**: Desktop script delivers the structured output to clipboard within 10 minutes of pressing F9 to stop a 45-minute meeting recording
- **SC-008**: Desktop script runs on Windows without requiring admin privileges or paid software
- **SC-009**: A user can retrieve any previously processed task by its unique URL without re-uploading the audio
- **SC-010**: Job status transitions (received → transcribing → analyzing → complete) are visible to the user within 5 seconds of each stage change

## Assumptions

- Primary audience is PT-BR speaking knowledge workers (managers, developers, team leads) who have or suspect ADHD
- Users access the system via web browser (desktop) or Telegram (mobile); mobile browser is nice-to-have
- The checklist output language matches the input audio language (PT-BR in → PT-BR out)
- Desktop script targets Windows as primary OS; macOS/Linux are stretch goals
- System audio loopback capture uses Windows WASAPI loopback — no paid virtual cable software required
- Desktop script is a standalone Python script, not a packaged executable, for v1
- Single cloud deployment — no local/cloud split; everything runs on one hosted backend
- Deployment target is a cloud platform capable of handling long-running background jobs (e.g., Hugging Face Spaces with a queue, or equivalent)
- Persistence layer uses external PostgreSQL via Supabase; connection configured via `DATABASE_URL` env var (supersedes SQLite assumption from 2026-06-22)
- Audio recordings range from short instructions (30 seconds) to full meetings (up to 45 minutes)
- No user accounts in v1 — tasks are accessible via unique URL; no authentication layer (Telegram `user_id` is stored in TelegramContext but not used for access control)
- Processed audio is not stored permanently — only the TaskRecord (transcript + structured output) is persisted
- Data privacy and LGPD/GDPR compliance are out of scope for v1 (no PII stored beyond task text)
- Desktop script targets the cloud production API endpoint; the target URL is configurable via a config file or environment variable
- Telegram Bot token is provisioned via @BotFather and configured in `TELEGRAM_BOT_TOKEN` env var
- Telegram webhook requires a public HTTPS URL; local dev falls back to polling mode automatically
- Telegram voice file download limit is 20 MB per Telegram Bot API constraints; files exceeding this must be rejected with a clear bot reply
- ffmpeg must be available in the server runtime PATH for OGG/OPUS → WAV conversion (installed in Docker image)

## Clarifications

### Session 2026-07-01

- Decision: Telegram Bot integration added as **User Story 8 (P1)**. Voice messages and forwarded audio files via Telegram join file upload and mic recording as a third input channel.
- Decision: SQLite (FR-022) **superseded by external PostgreSQL/Supabase (FR-030)**. Rationale: multi-device task access, production-grade persistence, Telegram user context storage.
- Architecture additions: Telegram webhook at `POST /telegram/webhook`; bot library `python-telegram-bot>=20.0`; audio conversion via `pydub` + `ffmpeg`; DB driver `asyncpg`.
- New env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_URL`, `DATABASE_URL`, `WEB_PANEL_BASE_URL`.
- DB pivot (2026-07-01): MySQL/aiomysql → PostgreSQL/asyncpg via Supabase. Free tier 500 MB, built-in connection pooler (Supavisor), better free tier than MySQL alternatives.

### Session 2026-06-22

- Q: What database backs TaskRecord persistence (FR-022)? → A: SQLite — file-based, zero-config, suitable for HF Spaces free tier; task IDs are UUIDs

### Session 2026-06-20

- Q: Does the HF Spaces API endpoint require authentication for desktop client POSTs? → A: No auth — public endpoint, acceptable for portfolio demo with no data persistence
- Q: Desktop script API target — local FastAPI (`localhost:8000`) or remote HF Spaces? → A: Local FastAPI; desktop script always targets the locally running backend
- Architectural clarification (superseded): dual-mode (Cloud/Local) replaced by single cloud architecture with async processing and persistent task history
- Strategy pivot: single "Master" cloud deployment — async background jobs, 45-minute audio support, database persistence, desktop script targets cloud API
