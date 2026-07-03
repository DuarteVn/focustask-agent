import json
import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Dormant local fallback (Constitution Principle I: Local-First, Zero-Cost Core).
# Interface-compatible with GeminiService.structure() so it can replace Gemini
# without touching callers. The prompt mirrors gemini_service.SYSTEM_PROMPT —
# keep the two in sync when the output contract changes.
SYSTEM_PROMPT = """Você é um assistente cognitivo especializado em gestão de tarefas para pessoas com TDAH.
Sua ÚNICA função: receber uma transcrição bruta de reunião/conversa e retornar UM ÚNICO objeto JSON válido.
Sem prosa, sem markdown, sem explicação — somente o JSON.

Schema JSON (estrito):
{
  "objetivo": "string — UMA frase no imperativo (máx. 30 palavras) descrevendo o que deve ser entregue",
  "checklist": [
    "string — passo atômico e acionável começando com verbo de ação"
  ],
  "fluxo": [
    "string — estágio da jornada de execução (máx. 8 palavras cada)"
  ]
}

Regras:
- objetivo: UMA frase, imperativo, o que deve ser entregue. Máx. 30 palavras.
- checklist: 3 a 10 itens. Cada item = passo específico e executável de forma independente. Começar com verbo de ação.
- fluxo: 3 a 6 estágios mostrando a jornada do estado inicial ao resultado final.
  - Primeiro estágio: estado inicial ou entrada (o que existe hoje)
  - Último estágio: resultado final ou entrega esperada
  - Estágios do meio: as principais transformações
  - Cada estágio: máx. 8 palavras, claro e específico
- Responda NO MESMO IDIOMA da transcrição.
- Retorne SOMENTE o objeto JSON. Nada antes ou depois."""


def _extract_json(raw: str) -> dict:
    """Strip markdown fences and parse the first JSON object found."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {raw[:200]}")
    return json.loads(match.group())


class OllamaService:
    def structure(self, transcript: str, language: str = "pt") -> dict:
        payload = {
            "model": settings.ollama_model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcrição:\n{transcript}"},
            ],
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }

        logger.info("Sending transcript to Ollama model=%s", settings.ollama_model)
        with httpx.Client(base_url=settings.ollama_base_url, timeout=120.0) as client:
            resp = client.post("/api/chat", json=payload)
            resp.raise_for_status()
            raw_content = resp.json()["message"]["content"]

        logger.debug("Ollama raw response: %s", raw_content[:500])
        return _extract_json(raw_content)

    def is_reachable(self) -> bool:
        try:
            with httpx.Client(base_url=settings.ollama_base_url, timeout=5.0) as client:
                return client.get("/api/tags").status_code == 200
        except Exception:
            return False


ollama_service = OllamaService()
