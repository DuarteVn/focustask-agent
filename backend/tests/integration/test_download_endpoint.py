import re


def _install_get_job(monkeypatch, job):
    async def _fake_get_job(job_id):
        return job

    monkeypatch.setattr("app.api.routes.jobs.get_job", _fake_get_job)


async def test_done_job_downloads_markdown(api_client, monkeypatch, structured_dict):
    _install_get_job(
        monkeypatch,
        {
            "status": "done",
            "objetivo": structured_dict["objetivo"],
            "checklist": structured_dict["checklist"],
            "fluxo": structured_dict["fluxo"],
        },
    )

    resp = await api_client.get("/api/jobs/abc-123/download.md")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    match = re.search(r'filename="([a-z0-9-]+\.md)"', disposition)
    assert match, f"invalid filename in {disposition!r}"
    task_lines = [l for l in resp.text.splitlines() if l.startswith("- [ ] ")]
    assert len(task_lines) == len(structured_dict["checklist"])


async def test_unknown_job_returns_404(api_client, monkeypatch):
    _install_get_job(monkeypatch, None)

    resp = await api_client.get("/api/jobs/nope/download.md")
    assert resp.status_code == 404


async def test_not_done_job_returns_409_with_status(api_client, monkeypatch):
    _install_get_job(monkeypatch, {"status": "processing"})

    resp = await api_client.get("/api/jobs/abc-123/download.md")
    assert resp.status_code == 409
    assert "processing" in resp.json()["detail"]


async def test_status_route_reports_done_job_with_markdown_url(
    api_client, monkeypatch, structured_dict
):
    _install_get_job(
        monkeypatch,
        {
            "status": "done",
            "objetivo": structured_dict["objetivo"],
            "checklist": structured_dict["checklist"],
            "fluxo": structured_dict["fluxo"],
            "transcript": "texto",
            "error_msg": None,
        },
    )

    resp = await api_client.get("/api/jobs/abc-123")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["structured"]["objetivo"] == structured_dict["objetivo"]
    assert body["markdown_url"] == "/api/jobs/abc-123/download.md"


async def test_status_route_stage_tagged_error_passthrough(api_client, monkeypatch):
    _install_get_job(
        monkeypatch,
        {"status": "error", "error_msg": "[decomposition] model exploded"},
    )

    resp = await api_client.get("/api/jobs/abc-123")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["error"] == "[decomposition] model exploded"
    assert body["markdown_url"] is None
