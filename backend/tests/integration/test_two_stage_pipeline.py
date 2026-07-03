import asyncio

from app.core.config import settings
from app.services import job_runner
from app.services.gemini_service import PipelineStageError, gemini_service


def _install_two_stage_mocks(monkeypatch, ptbr_summary, structured_dict, order):
    def _summarize(transcript, language="pt"):
        order.append("summarize")
        return ptbr_summary

    def _decompose(summary, language="pt"):
        order.append("decompose")
        assert summary == ptbr_summary  # Stage 2 sees ONLY the summary
        return structured_dict

    monkeypatch.setattr(gemini_service, "summarize", _summarize)
    monkeypatch.setattr(gemini_service, "decompose", _decompose)


async def test_process_text_runs_both_stages_in_order(
    api_client, mock_db, monkeypatch, ptbr_transcript, ptbr_summary, structured_dict
):
    order = []
    _install_two_stage_mocks(monkeypatch, ptbr_summary, structured_dict, order)

    resp = await api_client.post("/api/process/text", json={"transcript": ptbr_transcript})

    assert resp.status_code == 200
    assert order == ["summarize", "decompose"]
    body = resp.json()
    assert body["structured"]["objetivo"] == structured_dict["objetivo"]
    assert body["markdown"].startswith("# ")
    assert body["markdown_url"] == f"/api/jobs/{body['job_id']}/download.md"
    assert mock_db["set_summary"], "summary must be persisted between stages"
    assert mock_db["set_done"], "result must be persisted"


async def test_stage2_failure_returns_tagged_500_and_preserves_summary(
    api_client, mock_db, monkeypatch, ptbr_transcript, ptbr_summary
):
    monkeypatch.setattr(gemini_service, "summarize", lambda t, language="pt": ptbr_summary)

    def _boom(summary, language="pt"):
        raise PipelineStageError("decomposition", "model exploded")

    monkeypatch.setattr(gemini_service, "decompose", _boom)

    resp = await api_client.post("/api/process/text", json={"transcript": ptbr_transcript})

    assert resp.status_code == 500
    assert "[decomposition]" in resp.json()["detail"]
    assert mock_db["set_summary"], "Stage-1 summary must survive Stage-2 failure (R8)"


async def test_audio_over_45_minutes_rejected_upfront(api_client, mock_db, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.process.audio_converter.get_duration_seconds",
        lambda audio_bytes, filename: 46 * 60.0,
    )

    resp = await api_client.post(
        "/api/process/audio",
        files={"file": ("longo.mp3", b"fake", "audio/mpeg")},
    )

    assert resp.status_code == 400
    assert "45 minutos" in resp.json()["detail"]
    assert not mock_db["create_job"], "must reject BEFORE any processing starts"


async def test_long_audio_returns_202_and_dispatches_background(
    api_client, mock_db, monkeypatch
):
    monkeypatch.setattr(
        "app.api.routes.process.audio_converter.get_duration_seconds",
        lambda audio_bytes, filename: settings.sync_processing_max_seconds + 100.0,
    )
    dispatched = []

    async def _fake_run_job(job_id, audio_bytes, filename="audio.ogg", progress=None):
        dispatched.append(job_id)

    monkeypatch.setattr(job_runner, "run_job", _fake_run_job)

    resp = await api_client.post(
        "/api/process/audio",
        files={"file": ("medio.mp3", b"fake", "audio/mpeg")},
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert body["status_url"] == f"/api/jobs/{body['job_id']}"
    await asyncio.sleep(0)  # let the background task run
    assert dispatched == [body["job_id"]]
