import asyncio

from app.core.config import settings
from app.services import job_runner
from app.services.whisper_service import whisper_service

# Gemini retry/failover coverage lives in tests/unit/test_gemini_service.py.

# ---------------------------------------------------------------------------
# Job runner: dynamic timeout + heartbeat (Telegram path)
# ---------------------------------------------------------------------------


def test_telegram_job_timeout_sets_error_and_notifies_ptbr(monkeypatch):
    sent, errors = [], []

    async def _fake_create_job(job_id, source="web"):
        pass

    async def _fake_set_error(job_id, error):
        errors.append(error)

    async def _fake_send(chat_id, text, parse_mode=""):
        sent.append(text)

    async def _never_finishes(job_id, audio_bytes, filename="audio.ogg", progress=None):
        await asyncio.sleep(3600)

    monkeypatch.setattr(job_runner, "create_job", _fake_create_job)
    monkeypatch.setattr(job_runner, "set_error", _fake_set_error)
    monkeypatch.setattr(job_runner, "_send", _fake_send)
    monkeypatch.setattr(job_runner, "run_job", _never_finishes)
    monkeypatch.setattr(job_runner, "_TIMEOUT_POLL_SECONDS", 0.01)
    monkeypatch.setattr(settings, "job_timeout_seconds", 0)

    asyncio.run(job_runner.run_job_telegram("job-1", b"x", chat_id=42))

    assert errors and "timeout" in errors[0]
    assert sent and "demorou demais" in sent[-1]  # PT-BR user-facing copy


def test_dynamic_timeout_extends_for_long_audio(monkeypatch):
    """45-min audio must NOT die at the base timeout (research R4)."""
    finished = []

    async def _long_job(job_id, audio_bytes, filename="audio.ogg", progress=None):
        # Whisper "reported" a long duration; job outlives the base timeout.
        progress["duration_seconds"] = 2700.0
        await asyncio.sleep(0.05)
        finished.append(job_id)
        return {"objetivo": "ok", "checklist": [], "fluxo": [], "transcript": "t"}

    monkeypatch.setattr(job_runner, "_TIMEOUT_POLL_SECONDS", 0.01)
    monkeypatch.setattr(settings, "job_timeout_seconds", 0)  # base would kill it
    monkeypatch.setattr(settings, "job_timeout_factor", 1.5)

    async def _run():
        progress = {"stage": "transcrevendo", "pct": 0}
        task = asyncio.create_task(_long_job("job-1", b"x", progress=progress))
        import time

        return await job_runner._wait_with_dynamic_timeout(task, progress, time.perf_counter())

    result = asyncio.run(_run())

    assert finished == ["job-1"]
    assert result["objetivo"] == "ok"


def test_heartbeat_reports_stage_and_progress(monkeypatch):
    sent = []

    async def _fake_send(chat_id, text, parse_mode=""):
        sent.append(text)

    monkeypatch.setattr(job_runner, "_send", _fake_send)
    monkeypatch.setattr(settings, "job_heartbeat_seconds", 0)

    async def _run():
        progress = {"stage": "transcrevendo", "pct": 40}
        task = asyncio.create_task(job_runner._heartbeat("job-1", 42, progress))
        while not sent:
            await asyncio.sleep(0)
        progress["stage"] = "sumarizando"
        count = len(sent)
        while len(sent) == count:
            await asyncio.sleep(0)
        progress["stage"] = "estruturando"
        count = len(sent)
        while len(sent) == count:
            await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(_run())

    assert any("40%" in m for m in sent)
    assert any("consolidando o contexto" in m for m in sent)  # sumarizando stage
    assert any("estruturando tarefas" in m for m in sent)


def test_format_result_escapes_html_and_links_panel_and_download():
    result = {
        "objetivo": "Lançar <v2> & validar",
        "checklist": ["Testar <script>"],
        "fluxo": ["Entrada", "Meio", "Saída"],
    }
    msg = job_runner._format_result(result, "abc-123")

    assert "&lt;v2&gt; &amp; validar" in msg
    assert "&lt;script&gt;" in msg
    assert f"{settings.web_panel_base_url}/jobs/abc-123" in msg
    assert f"{settings.web_panel_base_url}/jobs/abc-123/download.md" in msg


# ---------------------------------------------------------------------------
# Whisper: progress callback in ~10% steps
# ---------------------------------------------------------------------------


class _FakeSegment:
    def __init__(self, text: str, end: float):
        self.text = text
        self.end = end


class _FakeInfo:
    def __init__(self, duration: float, language: str = "pt"):
        self.duration = duration
        self.language = language


class _FakeWhisperModel:
    def __init__(self, segments, info):
        self._segments = segments
        self._info = info

    def transcribe(self, *args, **kwargs):
        return iter(self._segments), self._info


def test_whisper_progress_callback_fires_in_10pct_steps(monkeypatch, tmp_path):
    segments = [_FakeSegment(f"parte {i}", end=float(i * 10)) for i in range(1, 11)]
    fake_model = _FakeWhisperModel(segments, _FakeInfo(duration=100.0))

    monkeypatch.setattr(settings, "temp_audio_dir", str(tmp_path))
    monkeypatch.setattr(whisper_service, "_normalize_audio", lambda p: p)
    monkeypatch.setattr(type(whisper_service), "_model", fake_model)

    pcts = []
    result = whisper_service.transcribe(b"fake", "audio.ogg", progress_cb=pcts.append)

    assert result["raw_transcript"].startswith("parte 1")
    assert result["language"] == "pt"
    assert pcts == sorted(pcts)  # monotonic
    assert all(b - a >= 10 for a, b in zip(pcts, pcts[1:]))  # >=10%% steps
    assert pcts and pcts[-1] <= 99
