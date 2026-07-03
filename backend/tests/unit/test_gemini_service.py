import json

import pytest

from app.core.config import settings
from app.services import gemini_service as gemini_module
from app.services.gemini_service import (
    DECOMPOSE_PROMPT,
    SUMMARIZE_PROMPT,
    GeminiService,
    PipelineStageError,
)

_SECTIONS = ("Entendimento Geral", "Escopo", "Regras de Negócio")


class _TransientError(Exception):
    code = 503


class _FatalError(Exception):
    code = 400


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


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


def _install_fake_client(monkeypatch, script: list):
    calls, keys_used = [], []

    class _FakeClient:
        def __init__(self, api_key: str, http_options=None):
            keys_used.append(api_key)
            self.models = _FakeModels(script, calls)

    monkeypatch.setattr(gemini_module.genai, "Client", _FakeClient)
    return calls, keys_used


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "key-primary")
    monkeypatch.setattr(settings, "gemini_api_key_fallback", "key-fallback")
    monkeypatch.setattr(gemini_module.time, "sleep", lambda s: None)


def _prose(ptbr_summary: str) -> str:
    return ptbr_summary


def test_summarize_returns_prose_with_three_sections(monkeypatch, ptbr_transcript, ptbr_summary):
    calls, _ = _install_fake_client(monkeypatch, [ptbr_summary])

    result = GeminiService().summarize(ptbr_transcript)

    for section in _SECTIONS:
        assert section in result
    cfg = calls[0]["config"]
    assert cfg.system_instruction == SUMMARIZE_PROMPT
    assert cfg.response_mime_type is None  # prose, not JSON (research R1)
    assert ptbr_transcript in calls[0]["contents"]


def test_decompose_takes_summary_only_and_returns_dict(monkeypatch, ptbr_summary, structured_dict):
    calls, _ = _install_fake_client(monkeypatch, [json.dumps(structured_dict, ensure_ascii=False)])

    result = GeminiService().decompose(ptbr_summary)

    assert set(result) == {"objetivo", "checklist", "fluxo"}
    cfg = calls[0]["config"]
    assert cfg.system_instruction == DECOMPOSE_PROMPT
    assert cfg.response_mime_type == "application/json"
    assert calls[0]["contents"].startswith("Resumo Consolidado:")  # FR-022


def test_structure_two_stage_chains_stages_in_order(monkeypatch, ptbr_transcript, ptbr_summary, structured_dict):
    calls, _ = _install_fake_client(
        monkeypatch, [ptbr_summary, json.dumps(structured_dict, ensure_ascii=False)]
    )

    summary, structured = GeminiService().structure_two_stage(ptbr_transcript)

    assert summary == ptbr_summary
    assert structured == structured_dict
    assert calls[0]["config"].system_instruction == SUMMARIZE_PROMPT
    assert calls[1]["config"].system_instruction == DECOMPOSE_PROMPT
    assert ptbr_summary in calls[1]["contents"]  # Stage 2 fed by Stage 1 output


def test_stage1_failure_raises_summarization_tag(monkeypatch, ptbr_transcript):
    _install_fake_client(monkeypatch, [_FatalError(), _FatalError()])

    with pytest.raises(PipelineStageError) as exc:
        GeminiService().summarize(ptbr_transcript)
    assert exc.value.stage == "summarization"


def test_stage2_failure_raises_decomposition_tag(monkeypatch, ptbr_summary):
    _install_fake_client(monkeypatch, [_FatalError(), _FatalError()])

    with pytest.raises(PipelineStageError) as exc:
        GeminiService().decompose(ptbr_summary)
    assert exc.value.stage == "decomposition"


def test_decompose_invalid_json_raises_decomposition_tag(monkeypatch, ptbr_summary):
    _install_fake_client(monkeypatch, ["isto não é json"])

    with pytest.raises(PipelineStageError) as exc:
        GeminiService().decompose(ptbr_summary)
    assert exc.value.stage == "decomposition"


def test_per_stage_retry_on_transient_503(monkeypatch, ptbr_transcript, ptbr_summary):
    calls, keys_used = _install_fake_client(
        monkeypatch, [_TransientError(), _TransientError(), ptbr_summary]
    )

    result = GeminiService().summarize(ptbr_transcript)

    assert result == ptbr_summary
    assert len(calls) == 3  # 2 transient failures + success, same key
    assert keys_used == ["key-primary"]


def test_fatal_error_fails_over_to_fallback_key(monkeypatch, ptbr_transcript, ptbr_summary):
    calls, keys_used = _install_fake_client(monkeypatch, [_FatalError(), ptbr_summary])

    result = GeminiService().summarize(ptbr_transcript)

    assert result == ptbr_summary
    assert keys_used == ["key-primary", "key-fallback"]


def test_no_key_configured_raises_stage_tagged(monkeypatch, ptbr_transcript):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key_fallback", "")

    with pytest.raises(PipelineStageError) as exc:
        GeminiService().summarize(ptbr_transcript)
    assert exc.value.stage == "summarization"
    assert "No Gemini API key" in str(exc.value)
