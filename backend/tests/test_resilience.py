import asyncio
import json

import pytest

from app.core.config import settings
from app.services import gemini_service as gemini_module
from app.services import job_runner
from app.services.gemini_service import GeminiService
from app.services.whisper_service import whisper_service

# ---------------------------------------------------------------------------
# Gemini retry / key failover
# ---------------------------------------------------------------------------


class _TransientError(Exception):
    code = 503


class _FatalError(Exception):
    code = 400


class _FakeResponse:
    def __init__(self, payload: dict):
        self.text = json.dumps(payload, ensure_ascii=False)


class _FakeModels:
    def __init__(self, script: list, calls: list):
        self._script = script
        self._calls = calls

    def generate_content(self, **kwargs):
        self._calls.append(kwargs)
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeResponse(outcome)


def _fake_client_factory(script: list, calls: list, keys_used: list):
    class _FakeClient:
        def __init__(self, api_key: str, http_options=None):
            keys_used.append(api_key)
            self.models = _FakeModels(script, calls)

    return _FakeClient


@pytest.fixture
def _gemini_keys(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "key-primary")
    monkeypatch.setattr(settings, "gemini_api_key_fallback", "key-fallback")
    monkeypatch.setattr(gemini_module.time, "sleep", lambda s: None)


def test_gemini_retries_transient_error_then_succeeds(monkeypatch, _gemini_keys, structured_dict, ptbr_transcript):
    calls, keys_used = [], []
    script = [_TransientError(), _TransientError(), structured_dict]
    monkeypatch.setattr(
        gemini_module.genai, "Client", _fake_client_factory(script, calls, keys_used)
    )

    result = GeminiService().structure(ptbr_transcript)

    assert result == structured_dict
    assert len(calls) == 3  # 2 transient failures + 1 success, same key
    assert keys_used == ["key-primary"]


def test_gemini_fatal_error_fails_over_to_fallback_key(monkeypatch, _gemini_keys, structured_dict, ptbr_transcript):
    calls, keys_used = [], []
    script = [_FatalError(), structured_dict]
    monkeypatch.setattr(
        gemini_module.genai, "Client", _fake_client_factory(script, calls, keys_used)
    )

    result = GeminiService().structure(ptbr_transcript)

    assert result == structured_dict
    assert keys_used == ["key-primary", "key-fallback"]


def test_gemini_all_keys_exhausted_raises(monkeypatch, _gemini_keys, ptbr_transcript):
    calls, keys_used = [], []
    script = [_FatalError(), _FatalError()]
    monkeypatch.setattr(
        gemini_module.genai, "Client", _fake_client_factory(script, calls, keys_used)
    )

    with pytest.raises(RuntimeError, match="All Gemini keys failed"):
        GeminiService().structure(ptbr_transcript)


def test_gemini_no_key_configured_raises(monkeypatch, ptbr_transcript):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key_fallback", "")

    with pytest.raises(RuntimeError, match="No Gemini API key configured"):
        GeminiService().structure(ptbr_transcript)


# ---------------------------------------------------------------------------
# Job runner: timeout + heartbeat (Telegram path)
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
    monkeypatch.setattr(settings, "job_timeout_seconds", 0)

    asyncio.run(job_runner.run_job_telegram("job-1", b"x", chat_id=42))

    assert errors and "timeout" in errors[0]
    assert sent and "demorou demais" in sent[-1]  # PT-BR user-facing copy


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
        progress["stage"] = "estruturando"
        first_count = len(sent)
        while len(sent) == first_count:
            await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(_run())

    assert any("40%" in m for m in sent)
    assert any("estruturando" in m for m in sent)


def test_format_result_escapes_html_and_links_panel():
    result = {
        "objetivo": "Lançar <v2> & validar",
        "checklist": ["Testar <script>"],
        "fluxo": ["Entrada", "Meio", "Saída"],
    }
    msg = job_runner._format_result(result, "abc-123")

    assert "&lt;v2&gt; &amp; validar" in msg
    assert "&lt;script&gt;" in msg
    assert f"{settings.web_panel_base_url}/jobs/abc-123" in msg


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
