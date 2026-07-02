# DEPRECATED — replaced by gemini_service.py
# This file is kept only to avoid import errors from cached bytecode.
# Remove after clearing __pycache__.
import json
import logging
import re

import httpx

from app.core.config import settings
from app.models.schemas import GlossaryItem, MicroTask, StructuredTask

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a cognitive assistant specialized in ADHD task management.
Your ONLY job: receive a raw meeting/conversation transcript and return a SINGLE valid JSON object.
No prose, no markdown, no explanation — just the JSON.

JSON schema (strict):
{
  "big_picture": "string — one sentence, the macro goal",
  "micro_tasks": [
    {"order": 1, "action": "string — one atomic action verb + object"}
  ],
  "definition_of_done": ["string — measurable criterion"],
  "glossary": [
    {"term": "string", "definition": "string — plain language"}
  ]
}

Rules:
- micro_tasks: break every action into the SMALLEST possible step. If unsure, split further.
- definition_of_done: measurable, observable. NOT vague like "finished" or "done".
- glossary: only include acronyms, jargon, or ambiguous terms actually present in the transcript.
- Respond in the SAME language as the transcript.
- Output ONLY the JSON object. Nothing before or after it."""


def _extract_json(raw: str) -> dict:
    """Strip markdown fences and parse first JSON object found."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {raw[:200]}")
    return json.loads(match.group())


class OllamaService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=120.0,
        )

    async def is_reachable(self) -> bool:
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def process_transcript(self, transcript: str) -> StructuredTask:
        payload = {
            "model": settings.ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcript:\n{transcript}"},
            ],
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }

        logger.info("Sending transcript to Ollama model=%s", settings.ollama_model)
        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()

        raw_content = resp.json()["message"]["content"]
        logger.debug("Ollama raw response: %s", raw_content[:500])

        data = _extract_json(raw_content)

        return StructuredTask(
            big_picture=data["big_picture"],
            micro_tasks=[MicroTask(**t) for t in data["micro_tasks"]],
            definition_of_done=data["definition_of_done"],
            glossary=[GlossaryItem(**g) for g in data.get("glossary", [])],
        )

    async def aclose(self) -> None:
        await self._client.aclose()


ollama_service = OllamaService()
