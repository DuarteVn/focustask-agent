import json

import httpx
import pytest

from app.services import ollama_service as ollama_module
from app.services.ollama_service import OllamaService, _extract_json


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"message": {"content": self._content}}


class _FakeClient:
    """Stands in for httpx.Client — no network (Constitution Principle V)."""

    last_payload: dict | None = None
    response_content: str = ""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url: str, json: dict) -> _FakeResponse:
        _FakeClient.last_payload = json
        return _FakeResponse(_FakeClient.response_content)


def test_structure_returns_three_section_dict(monkeypatch, ptbr_transcript, structured_dict):
    _FakeClient.response_content = json.dumps(structured_dict, ensure_ascii=False)
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    result = OllamaService().structure(ptbr_transcript)

    assert set(result) == {"objetivo", "checklist", "fluxo"}
    assert result == structured_dict


def test_structure_sends_ptbr_prompt_and_transcript(monkeypatch, ptbr_transcript, structured_dict):
    _FakeClient.response_content = json.dumps(structured_dict, ensure_ascii=False)
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    OllamaService().structure(ptbr_transcript)

    payload = _FakeClient.last_payload
    system_msg = payload["messages"][0]["content"]
    user_msg = payload["messages"][1]["content"]
    assert "assistente cognitivo" in system_msg  # PT-BR prompt (Principle II)
    assert '"objetivo"' in system_msg and '"checklist"' in system_msg and '"fluxo"' in system_msg
    assert ptbr_transcript in user_msg


def test_prompt_matches_gemini_output_contract():
    # Dormant fallback must stay interface-compatible with the primary LLM
    # (Constitution Principle I) — same 3-section schema as Gemini's Stage 2.
    # Ollama two-stage parity is explicitly deferred (research R9).
    from app.services.gemini_service import DECOMPOSE_PROMPT as GEMINI_PROMPT

    for section in ('"objetivo"', '"checklist"', '"fluxo"'):
        assert section in ollama_module.SYSTEM_PROMPT
        assert section in GEMINI_PROMPT


def test_extract_json_strips_markdown_fences(structured_dict):
    raw = "```json\n" + json.dumps(structured_dict, ensure_ascii=False) + "\n```"
    assert _extract_json(raw) == structured_dict


def test_extract_json_raises_without_json():
    with pytest.raises(ValueError):
        _extract_json("nenhum json aqui")
