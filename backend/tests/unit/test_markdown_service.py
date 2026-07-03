import datetime
import re

from app.services.markdown_service import make_filename, render, slugify

_DATE = datetime.date(2026, 7, 2)


def test_every_checklist_item_is_a_task_line(structured_dict):
    md = render(**structured_dict)
    task_lines = [line for line in md.splitlines() if line.startswith("- [ ] ")]
    assert len(task_lines) == len(structured_dict["checklist"])
    for item in structured_dict["checklist"]:
        assert f"- [ ] {item}" in md


def test_three_section_headings_present(structured_dict):
    md = render(**structured_dict)
    assert "## 🎯 Objetivo Direto" in md
    assert "## ✅ Micro-Tasks" in md
    assert "## 🔁 Fluxo de Execução" in md


def test_no_html_tags_in_output(structured_dict):
    md = render(**structured_dict)
    assert not re.search(r"</?[a-zA-Z][^>]*>", md)


def test_fluxo_first_is_input_last_is_output(structured_dict):
    md = render(**structured_dict)
    assert f"1. **Input** — {structured_dict['fluxo'][0]}" in md
    assert f"3. **Output** — {structured_dict['fluxo'][-1]}" in md


def test_filename_ptbr_accents_stripped():
    name = make_filename("Relatório de Vendas até Sexta", "abcd1234-x", _DATE)
    assert name == "relatorio-de-vendas-ate-sexta-2026-07-02.md"


def test_filename_windows_forbidden_chars_stripped():
    name = make_filename('Plano <Q3>: "urgente"? C:\\temp|*', "abcd1234-x", _DATE)
    assert re.fullmatch(r"[a-z0-9-]+\.md", name)
    assert "<" not in name and ":" not in name and "\\" not in name


def test_slug_truncates_over_60_chars_at_word_boundary():
    long_text = "palavra " * 20  # slug would be ~140 chars
    slug = slugify(long_text)
    assert len(slug) <= 60
    assert not slug.endswith("-")
    assert re.fullmatch(r"[a-z0-9-]+", slug)


def test_symbols_only_objective_falls_back_to_job_id():
    name = make_filename("!!! ??? ***", "abcd1234-rest-of-uuid", _DATE)
    assert name == "focustask-abcd1234-2026-07-02.md"


def test_filename_charset_contract(structured_dict):
    name = make_filename(structured_dict["objetivo"], "abcd1234-x", _DATE)
    assert re.fullmatch(r"[a-z0-9-]+\.md", name)
