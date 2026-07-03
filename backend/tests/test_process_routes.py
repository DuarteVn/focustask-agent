import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.gemini_service import gemini_service
from app.services.whisper_service import whisper_service

# TestClient used without a context manager on purpose: lifespan (DB init,
# Whisper load, Telegram bot) must NOT run — tests need no live dependencies
# (Constitution Principle V).
client = TestClient(app)


async def _fake_create_job(job_id: str, source: str = "web") -> None:
    pass


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    monkeypatch.setattr("app.api.routes.process.create_job", _fake_create_job)


def test_process_text_returns_structured_output(monkeypatch, ptbr_transcript, structured_dict):
    monkeypatch.setattr(gemini_service, "structure", lambda transcript, language="pt": structured_dict)

    resp = client.post("/api/process/text", json={"transcript": ptbr_transcript})

    assert resp.status_code == 200
    body = resp.json()
    assert body["raw_transcript"] == ptbr_transcript
    assert body["structured"]["objetivo"] == structured_dict["objetivo"]
    assert body["structured"]["checklist"] == structured_dict["checklist"]
    assert body["structured"]["fluxo"] == structured_dict["fluxo"]
    assert body["job_id"]


def test_process_text_rejects_empty_transcript():
    resp = client.post("/api/process/text", json={"transcript": "   "})
    assert resp.status_code == 400


def test_process_text_llm_failure_returns_500(monkeypatch, ptbr_transcript):
    def _boom(transcript, language="pt"):
        raise RuntimeError("All Gemini keys failed")

    monkeypatch.setattr(gemini_service, "structure", _boom)

    resp = client.post("/api/process/text", json={"transcript": ptbr_transcript})
    assert resp.status_code == 500
    assert "LLM processing failed" in resp.json()["detail"]


def test_process_audio_full_pipeline_mocked(monkeypatch, ptbr_transcript, structured_dict):
    monkeypatch.setattr(
        whisper_service,
        "transcribe",
        lambda audio_bytes, filename, **kwargs: {
            "raw_transcript": ptbr_transcript,
            "language": "pt",
            "duration_seconds": 12.5,
        },
    )
    monkeypatch.setattr(gemini_service, "structure", lambda transcript, language="pt": structured_dict)

    resp = client.post(
        "/api/process/audio",
        files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["raw_transcript"] == ptbr_transcript
    assert body["structured"] == structured_dict


def test_process_audio_rejects_empty_file():
    resp = client.post(
        "/api/process/audio",
        files={"file": ("audio.webm", b"", "audio/webm")},
    )
    assert resp.status_code == 400


def test_output_limits_enforced_at_route_level(monkeypatch, ptbr_transcript, structured_dict):
    # LLM returns out-of-bounds output → route response must be clamped
    # (Constitution Principle III).
    structured_dict["checklist"] = [f"Fazer passo {i}" for i in range(20)]
    structured_dict["fluxo"] = [f"Estágio {i}" for i in range(10)]
    monkeypatch.setattr(gemini_service, "structure", lambda transcript, language="pt": structured_dict)

    resp = client.post("/api/process/text", json={"transcript": ptbr_transcript})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["structured"]["checklist"]) == 10
    assert len(body["structured"]["fluxo"]) == 6
