"""Découpage des documents en passages pour le RAG : par paragraphes, puis par phrases si besoin."""

import re

from gmix.llm.tokens import estimate_tokens

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def split_into_chunks(text: str, max_tokens: int = 350, overlap_tokens: int = 60) -> list[str]:
    """Passages d'au plus ~max_tokens ; les dernières unités d'un passage sont reprises en tête
    du suivant (≤ overlap_tokens) pour ne pas couper une explication en deux."""
    units: list[str] = []
    for paragraph in (p.strip() for p in _PARAGRAPH.split(text)):
        if not paragraph:
            continue
        if estimate_tokens(paragraph) <= max_tokens:
            units.append(paragraph)
        else:
            units.extend(s.strip() for s in _SENTENCE.split(paragraph) if s.strip())

    chunks: list[str] = []
    current: list[str] = []
    for unit in units:
        if current and estimate_tokens("\n\n".join([*current, unit])) > max_tokens:
            chunks.append("\n\n".join(current))
            current = _tail(current, overlap_tokens)
            if current and estimate_tokens("\n\n".join([*current, unit])) > max_tokens:
                current = []
        current.append(unit)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _tail(units: list[str], overlap_tokens: int) -> list[str]:
    tail: list[str] = []
    used = 0
    for unit in reversed(units):
        cost = estimate_tokens(unit)
        if used + cost > overlap_tokens:
            break
        tail.insert(0, unit)
        used += cost
    return tail
