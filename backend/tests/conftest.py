import pytest

# Constitution Principle II: fixtures must include PT-BR with accents and
# colloquial speech. Principle V: no live dependencies — DB and LLM are
# always mocked at the service boundary.


@pytest.fixture
def ptbr_transcript() -> str:
    return (
        "Então, a gente precisa subir o backend novo, vê lá o endpoint de upload... "
        "não, espera, primeiro valida a duração do áudio, depois chama o Whisper "
        "e só então manda pro Gemini estruturar as tarefas, tá?"
    )


@pytest.fixture
def ptbr_summary() -> str:
    return (
        "Entendimento Geral\n"
        "A equipe discute a publicação do backend novo com validação de áudio.\n\n"
        "Escopo\n"
        "Publicar o backend com validação de duração antes da transcrição.\n\n"
        "Regras de Negócio\n"
        "A duração do áudio deve ser validada antes de chamar o Whisper."
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


@pytest.fixture
async def api_client():
    """httpx ASGI client for app.main:app — lifespan NOT run (no DB/Whisper/bot)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_db(monkeypatch):
    """Monkeypatch repository functions used by the process routes; records calls."""
    calls = {"create_job": [], "set_processing": [], "set_summary": [], "set_done": []}

    def _recorder(name):
        async def _f(*args, **kwargs):
            calls[name].append(args)

        return _f

    for name in calls:
        monkeypatch.setattr(f"app.api.routes.process.{name}", _recorder(name))
    return calls
