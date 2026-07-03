import pytest

# Constitution Principle II: fixtures must include PT-BR with accents and
# colloquial speech.


@pytest.fixture
def ptbr_transcript() -> str:
    return (
        "Então, a gente precisa subir o backend novo, vê lá o endpoint de upload... "
        "não, espera, primeiro valida a duração do áudio, depois chama o Whisper "
        "e só então manda pro Gemini estruturar as tarefas, tá?"
    )


@pytest.fixture
def structured_dict() -> dict:
    return {
        "objetivo": "Publicar o backend novo com validação de áudio antes da transcrição",
        "checklist": [
            "Validar duração do áudio no upload",
            "Chamar o Whisper para transcrever",
            "Enviar transcrição ao Gemini",
        ],
        "fluxo": [
            "Áudio recebido no endpoint",
            "Transcrição gerada localmente",
            "Tarefas estruturadas entregues",
        ],
    }
