import json
import logging
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"
_TRANSIENT_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 5

SUMMARIZE_PROMPT = """Você é um consolidador de contexto especializado em análise de reuniões e conversas.
Sua ÚNICA função: receber uma transcrição bruta e produzir um resumo consolidado em prosa,
com EXATAMENTE estas três seções, nesta ordem e com estes títulos:

Entendimento Geral
(o que está sendo discutido, quem está envolvido, qual o objetivo macro)

Escopo
(o que está dentro e o que está explicitamente fora do que deve ser feito)

Regras de Negócio
(TODAS as regras, restrições, condições e prazos mencionados — mesmo os citados uma única vez)

Regras:
- Capture TODAS as regras de negócio e restrições, mesmo as mencionadas apenas uma vez no início da conversa.
- Remova preenchimentos ("é...", "tipo assim"), tangentes e autocorreções ("não, espera" — mantenha apenas a versão final).
- NÃO crie tarefas, checklists nem listas de ação — apenas entendimento consolidado.
- Responda NO MESMO IDIOMA da transcrição.
- Texto puro em prosa; nenhuma formatação além dos três títulos de seção."""

DECOMPOSE_PROMPT = """Você é um assistente cognitivo especializado em gestão de tarefas para pessoas com TDAH.
Sua ÚNICA função: receber um Resumo Consolidado de uma reunião/conversa e retornar UM ÚNICO objeto JSON válido.
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
- Baseie-se SOMENTE no Resumo Consolidado fornecido — respeite todas as Regras de Negócio listadas nele.
- Responda NO MESMO IDIOMA do resumo.
- Retorne SOMENTE o objeto JSON. Nada antes ou depois."""


class PipelineStageError(RuntimeError):
    """LLM pipeline failure tagged with the failing stage (FR-024)."""

    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


class GeminiService:
    def summarize(self, transcript: str, language: str = "pt") -> str:
        """Stage 1: consolidate understanding/scope/business rules as prose."""
        return self._generate(
            system_prompt=SUMMARIZE_PROMPT,
            content=f"Transcrição:\n{transcript}",
            stage="summarization",
            json_mode=False,
        )

    def decompose(self, summary: str, language: str = "pt") -> dict:
        """Stage 2: micro-tasks from the consolidated summary ONLY (FR-022)."""
        text = self._generate(
            system_prompt=DECOMPOSE_PROMPT,
            content=f"Resumo Consolidado:\n{summary}",
            stage="decomposition",
            json_mode=True,
        )
        try:
            return json.loads(text)
        except (TypeError, ValueError) as e:
            raise PipelineStageError("decomposition", f"Invalid JSON from model: {e}") from e

    def structure_two_stage(self, transcript: str, language: str = "pt") -> tuple[str, dict]:
        """Chain both stages. Returns (summary, structured)."""
        summary = self.summarize(transcript, language)
        return summary, self.decompose(summary, language)

    def _generate(self, system_prompt: str, content: str, stage: str, json_mode: bool) -> str:
        keys = [k for k in [settings.gemini_api_key, settings.gemini_api_key_fallback] if k]
        if not keys:
            raise PipelineStageError(stage, "No Gemini API key configured")

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            response_mime_type="application/json" if json_mode else None,
        )

        last_err = None
        for key in keys:
            client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(timeout=settings.gemini_timeout_ms),
            )
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    response = client.models.generate_content(
                        model=_MODEL,
                        contents=content,
                        config=config,
                    )
                    return response.text
                except Exception as e:
                    last_err = e
                    code = getattr(e, "code", None)
                    transient = isinstance(e, genai_errors.ServerError) or code in _TRANSIENT_CODES
                    if transient and attempt < _MAX_RETRIES:
                        wait = _RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                        logger.warning(
                            "Gemini transient error in %s (attempt %d/%d): %s | retrying in %ds",
                            stage, attempt, _MAX_RETRIES, e, wait,
                        )
                        time.sleep(wait)
                        continue
                    logger.warning("Gemini key failed in %s: %s", stage, e)
                    break

        raise PipelineStageError(stage, f"All Gemini keys failed: {last_err}")


gemini_service = GeminiService()
