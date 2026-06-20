# Feature Specification: FocusTask Agent

**Feature Branch**: `001-focustask-agent`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "FocusTask Agent — ADHD-friendly audio-to-task pipeline for Hugging Face Spaces portfolio project."

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

---

### User Story 5 - Desktop Meeting Capture (Priority: P3)

During a live meeting on Meet, Discord, or any video call tool, the user runs a local Python script. They press F9 to start capturing system audio (other participants) and microphone audio (themselves) simultaneously. When the meeting ends or a task is discussed, they press F9 again to stop. The script mixes both channels, sends the recording to the FocusTask Agent API, and the structured task breakdown appears in the browser or is copied to clipboard automatically — no manual upload needed.

**Why this priority**: Closes the loop for the most common real-world scenario (tasks assigned in meetings) without requiring the user to remember to record separately. P3 because it requires a companion local script and is a separate distribution artifact from the web app.

**Independent Test**: Run the desktop script, press F9, play a YouTube video while speaking into the mic, press F9 again. Verify a .wav file is created with both audio channels mixed, the API call succeeds, and the result opens in the browser.

**Acceptance Scenarios**:

1. **Given** the desktop script is running, **When** user presses F9, **Then** recording starts capturing both system audio and microphone simultaneously with a visual/terminal indicator
2. **Given** recording is active, **When** user presses F9 again, **Then** recording stops, channels are mixed into a single .wav file, and it is automatically sent to the FocusTask Agent API
3. **Given** the API processes the mixed audio, **When** response arrives, **Then** the structured Markdown output is either opened in the default browser or copied to clipboard (configurable)
4. **Given** the API call fails or times out, **When** the error occurs, **Then** the local .wav file is preserved and the user is notified via terminal with the file path so they can retry manually

---

### Edge Cases

- What happens when audio contains no actionable work content (e.g., casual chitchat, background noise only)?
- How does the system handle audio files longer than 3 minutes?
- What if transcription produces garbled or nonsensical text?
- What if the user's microphone access is denied by the browser?
- What happens if the LLM processing step fails or times out?
- What if the audio is entirely in a language the system cannot transcribe?
- What if system audio capture is blocked by the OS (e.g., audio routed to Bluetooth device)?
- What if the mixed .wav file exceeds the API's size or duration limit?
- What happens if the user presses F9 to stop before any meaningful audio is captured?

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
- **FR-013**: The FocusTask Agent API endpoint MUST accept audio file uploads via HTTP POST from external clients (not just the Gradio web UI) with no authentication required
- **FR-014**: The desktop script MUST capture system audio output (loopback) and microphone input simultaneously on the local machine
- **FR-015**: The desktop script MUST mix both captured audio channels into a single audio file before sending
- **FR-016**: The desktop script MUST use a configurable hotkey (default: F9) to toggle recording start/stop without requiring mouse interaction
- **FR-017**: The desktop script MUST send the mixed audio file to the FocusTask Agent API and receive the structured Markdown response
- **FR-018**: The desktop script MUST deliver the structured output by either opening it in the default browser or copying it to the system clipboard (user-configurable)
- **FR-019**: The desktop script MUST preserve the local .wav file on API failure and inform the user via terminal output

### Key Entities

- **AudioInput**: User-provided audio content (file, live browser recording, or mixed desktop capture), format, and approximate duration
- **Transcript**: Raw text output from speech-to-text, with detected language
- **TaskOutput**: Composed of DirectObjective (single sentence), MicroTaskChecklist (ordered list of steps), and ExecutionFlow (input / logic / output triple)
- **DesktopCapture**: Local recording session with system audio channel, microphone channel, mixed output file path, and recording duration

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users complete the full audio-to-structured-output flow in under 60 seconds for a 1-minute audio recording
- **SC-002**: The Direct Objective section contains a single sentence of 30 words or fewer in 90% of processed inputs
- **SC-003**: The Micro-Tasks Checklist contains between 3 and 10 items for a typical 30–90 second work instruction recording
- **SC-004**: Verbal noise phrases ("vê lá", "espera", "ah", "não, volta lá") are absent from all output sections in 95% of cases where they appear in the transcript
- **SC-005**: A first-time user with no instructions can complete a full session (upload → output) without guidance, on first attempt
- **SC-006**: System processes audio files up to 3 minutes in length without failure or timeout
- **SC-007**: Desktop script delivers the structured output to browser or clipboard within 90 seconds of pressing F9 to stop recording (for a 2-minute meeting segment)
- **SC-008**: Desktop script runs on Windows without requiring admin privileges or paid software

## Assumptions

- Primary audience is PT-BR speaking knowledge workers (managers, developers, team leads) who have or suspect ADHD
- Users have access to a modern desktop browser; mobile is nice-to-have but not required for v1
- Audio recordings are typically 30 seconds to 3 minutes in length
- Each session is stateless — no user accounts, no history, no persistence in v1
- Deployment target is Hugging Face Spaces free tier; expected load is low (portfolio demo traffic)
- Data privacy and LGPD/GDPR compliance are out of scope for v1 (no data is stored)
- The checklist output language matches the input audio language (PT-BR in → PT-BR out)
- Desktop script targets Windows as primary OS (user's platform); macOS/Linux are stretch goals
- System audio loopback capture requires a virtual audio device or OS-level loopback support (e.g., Windows WASAPI loopback) — no paid virtual cable software required
- The HF Spaces API endpoint is publicly accessible (no auth token required for portfolio demo)
- Desktop script is a standalone Python script, not a packaged executable, for v1
- The HF Spaces API endpoint is unauthenticated (public); no API token or secret is needed in the desktop script

## Clarifications

### Session 2026-06-20

- Q: Does the HF Spaces API endpoint require authentication for desktop client POSTs? → A: No auth — public endpoint, acceptable for portfolio demo with no data persistence
