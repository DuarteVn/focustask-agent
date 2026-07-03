import datetime
import re
import unicodedata

_MAX_SLUG_LEN = 60


def render(objetivo: str, checklist: list[str], fluxo: list[str]) -> str:
    """Serialize validated structured output as Obsidian-ready Markdown.

    Deterministic by design (research R5): FR-025 requires `- [ ]` on every
    checklist item and zero HTML — only code can guarantee that on 100% of
    outputs.
    """
    lines = [
        f"# {objetivo}",
        "",
        "## 🎯 Objetivo Direto",
        "",
        objetivo,
        "",
        "## ✅ Micro-Tasks",
        "",
    ]
    for item in checklist:
        lines.append(f"- [ ] {item}")

    lines += ["", "## 🔁 Fluxo de Execução", ""]
    for i, stage in enumerate(fluxo):
        if i == 0:
            lines.append(f"{i + 1}. **Input** — {stage}")
        elif i == len(fluxo) - 1:
            lines.append(f"{i + 1}. **Output** — {stage}")
        else:
            lines.append(f"{i + 1}. {stage}")

    return "\n".join(lines) + "\n"


def slugify(text: str) -> str:
    """PT-BR-safe filesystem slug: NFKD, strip accents, [a-z0-9-] only,
    60-char word-boundary truncation (research R7)."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    if len(slug) > _MAX_SLUG_LEN:
        slug = slug[:_MAX_SLUG_LEN]
        if "-" in slug:
            slug = slug.rsplit("-", 1)[0]  # truncate at word boundary
    return slug


def make_filename(objetivo: str, job_id: str, date: datetime.date) -> str:
    slug = slugify(objetivo)
    if not slug:
        slug = f"focustask-{job_id[:8]}"  # FR-027 empty-slug fallback
    return f"{slug}-{date.isoformat()}.md"
