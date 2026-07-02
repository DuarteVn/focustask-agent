import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"

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


class GeminiService:
    def structure(self, transcript: str, language: str = "pt") -> dict:
        keys = [k for k in [settings.gemini_api_key, settings.gemini_api_key_fallback] if k]
        if not keys:
            raise RuntimeError("No Gemini API key configured")

        last_err = None
        for key in keys:
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model=_MODEL,
                    contents=f"Transcrição:\n{transcript}",
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                return json.loads(response.text)
            except Exception as e:
                last_err = e
                logger.warning("Gemini key failed: %s", e)

        raise RuntimeError(f"All Gemini keys failed: {last_err}")


gemini_service = GeminiService()
