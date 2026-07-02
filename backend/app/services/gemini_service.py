import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"

_SYSTEM_PROMPT = """You are a task structuring assistant for people with ADHD.
Given a raw audio transcript, extract structured task information and return ONLY valid JSON with exactly these keys:
{
  "objective": "single sentence stating what must be delivered (max 30 words)",
  "checklist": ["specific actionable step 1", "step 2", ...],
  "flow": {
    "input": "what enters the process (data, context, resources)",
    "logic": "what is processed or decided",
    "output": "expected result or deliverable"
  }
}

Rules:
- Remove filler words, self-corrections, verbal noise (ah, é, vê lá, espera, não volta lá)
- Keep language of the transcript (PT-BR in → PT-BR out)
- objective: ONE sentence, max 30 words
- checklist: 1-10 specific actionable items, no vague categories
- Return ONLY the JSON object, no markdown, no explanation"""


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("```", "").strip()
    return text


def _validate_structure(data: dict) -> None:
    if not isinstance(data.get("objective"), str) or not data["objective"].strip():
        raise ValueError("objective must be a non-empty string")
    checklist = data.get("checklist")
    if not isinstance(checklist, list) or len(checklist) < 1:
        raise ValueError("checklist must be a non-empty list")
    if len(checklist) > 20:
        raise ValueError("checklist has more than 20 items")
    for item in checklist:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("each checklist item must be a non-empty string")
    flow = data.get("flow")
    if not isinstance(flow, dict):
        raise ValueError("flow must be an object")
    for key in ("input", "logic", "output"):
        if not isinstance(flow.get(key), str) or not flow[key].strip():
            raise ValueError(f"flow.{key} must be a non-empty string")


class GeminiService:
    def __init__(self, settings=None):
        from app.core.config import get_settings
        self._settings = settings or get_settings()

    def structure(self, transcript: str, language: str) -> dict[str, Any]:
        keys = [k for k in [
            self._settings.gemini_api_key,
            self._settings.gemini_api_key_fallback,
        ] if k]
        if not keys:
            raise ValueError("No Gemini API key configured — set GEMINI_API_KEY in .env")

        last_error: Exception | None = None
        for api_key in keys:
            try:
                return self._call_gemini(api_key, transcript, language)
            except Exception as exc:
                last_error = exc
                logger.warning("gemini_key_failed key_suffix=...%s error=%s", api_key[-6:], exc)

        raise ValueError(f"All Gemini keys failed: {last_error}")

    def _call_gemini(self, api_key: str, transcript: str, language: str) -> dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = f"Language: {language}\n\nTranscript:\n{transcript}"
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                raw = _strip_markdown(response.text)
                data = json.loads(raw)
                _validate_structure(data)
                logger.info("gemini_structured attempt=%d key_suffix=...%s", attempt + 1, api_key[-6:])
                return data
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning("gemini_parse_failed attempt=%d error=%s", attempt + 1, exc)

        raise ValueError(f"Gemini output unparseable after 3 attempts: {last_error}")
