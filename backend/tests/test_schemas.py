from app.models.schemas import (
    MAX_CHECKLIST_ITEMS,
    MAX_FLUXO_STAGES,
    MAX_OBJETIVO_WORDS,
    StructuredOutput,
)


def _valid_kwargs(structured_dict: dict) -> dict:
    return dict(structured_dict)


def test_valid_output_passes_unchanged(structured_dict):
    out = StructuredOutput(**structured_dict)
    assert out.objetivo == structured_dict["objetivo"]
    assert out.checklist == structured_dict["checklist"]
    assert out.fluxo == structured_dict["fluxo"]


def test_objetivo_over_30_words_is_truncated(structured_dict):
    structured_dict["objetivo"] = " ".join(f"palavra{i}" for i in range(45))
    out = StructuredOutput(**structured_dict)
    assert len(out.objetivo.split()) == MAX_OBJETIVO_WORDS


def test_checklist_over_10_items_is_truncated(structured_dict):
    structured_dict["checklist"] = [f"Fazer passo {i}" for i in range(15)]
    out = StructuredOutput(**structured_dict)
    assert len(out.checklist) == MAX_CHECKLIST_ITEMS
    assert out.checklist[0] == "Fazer passo 0"


def test_fluxo_over_6_stages_is_truncated(structured_dict):
    structured_dict["fluxo"] = [f"Estágio {i}" for i in range(9)]
    out = StructuredOutput(**structured_dict)
    assert len(out.fluxo) == MAX_FLUXO_STAGES


def test_below_minimum_is_kept_but_logged(structured_dict, caplog):
    structured_dict["checklist"] = ["Único item"]
    structured_dict["fluxo"] = ["Início", "Fim"]
    with caplog.at_level("WARNING", logger="app.models.schemas"):
        out = StructuredOutput(**structured_dict)
    # Minima cannot be fabricated — output is preserved, warning emitted.
    assert out.checklist == ["Único item"]
    assert out.fluxo == ["Início", "Fim"]
    assert any("minimum" in r.message for r in caplog.records)
