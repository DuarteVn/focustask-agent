import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.gemini_service import PipelineStageError, gemini_service
from app.services.whisper_service import whisper_service

# TestClient used without a context manager on purpose: lifespan (DB init,
# Whisper load, Telegram bot) must NOT run — tests need no live dependencies
# (Constitution Principle V).
client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_db(mock_db):
    pass


@pytest.fixture
def _two_stage_ok(monkeypatch, ptbr_summary, structured_dict):
    monkeypatch.setattr(gemini_service, "summarize", lambda t, language="pt": ptbr_summary)
    monkeypatch.setattr(gemini_service, "decompose", lambda s, language="pt": structured_dict)


def test_process_text_returns_structured_output(_two_stage_ok, ptbr_transcript, structured_dict):
    resp = client.post("/api/process/text", json={"transcript": ptbr_transcript})

    assert resp.status_code == 200
    body = resp.json()
    assert body["raw_transcript"] == ptbr_transcript
    assert body["structured"]["objetivo"] == structured_dict["objetivo"]
    assert body["structured"]["checklist"] == structured_dict["checklist"]
    assert body["structured"]["fluxo"] == structured_dict["fluxo"]
    assert body["markdown"].startswith("# ")
    assert body["job_id"]


def test_process_text_rejects_empty_transcript():
    resp = client.post("/api/process/text", json={"transcript": "   "})
    assert resp.status_code == 400


def test_process_text_llm_failure_returns_tagged_500(monkeypatch, ptbr_transcript):
    def _boom(transcript, language="pt"):
        raise PipelineStageError("summarization", "All Gemini keys failed")

    monkeypatch.setattr(gemini_service, "summarize", _boom)

    resp = client.post("/api/process/text", json={"transcript": ptbr_transcript})
    assert resp.status_code == 500
    assert "LLM processing failed: [summarization]" in resp.json()["detail"]


def test_process_audio_full_pipeline_mocked(
    monkeypatch, _two_stage_ok, ptbr_transcript, structured_dict
):
    monkeypatch.setattr(
        "app.api.routes.process.audio_converter.get_duration_seconds",
        lambda audio_bytes, filename: 30.0,
    )
    monkeypatch.setattr(
        whisper_service,
        "transcribe",
        lambda audio_bytes, filename, **kwargs: {
            "raw_transcript": ptbr_transcript,
            "language": "pt",
            "duration_seconds": 30.0,
        },
    )

    resp = client.post(
        "/api/process/audio",
        files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["raw_transcript"] == ptbr_transcript
    assert body["structured"] == structured_dict
    assert body["markdown_url"].endswith("/download.md")


def test_process_audio_rejects_empty_file():
    resp = client.post(
        "/api/process/audio",
        files={"file": ("audio.webm", b"", "audio/webm")},
    )
    assert resp.status_code == 400


def test_output_limits_enforced_at_route_level(
    monkeypatch, ptbr_transcript, ptbr_summary, structured_dict
):
    # LLM returns out-of-bounds output → route response must be clamped
    # (Constitution Principle III).
    structured_dict["checklist"] = [f"Fazer passo {i}" for i in range(20)]
    structured_dict["fluxo"] = [f"Estágio {i}" for i in range(10)]
    monkeypatch.setattr(gemini_service, "summarize", lambda t, language="pt": ptbr_summary)
    monkeypatch.setattr(gemini_service, "decompose", lambda s, language="pt": structured_dict)

    resp = client.post("/api/process/text", json={"transcript": ptbr_transcript})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["structured"]["checklist"]) == 10
    assert len(body["structured"]["fluxo"]) == 6
