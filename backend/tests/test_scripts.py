"""Règles des scripts PowerShell du dépôt (CLAUDE.md) : PowerShell 5.1, UTF-8 avec BOM, pas de `&&`."""

import re
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parents[2] / "scripts").glob("*.ps1"))


def _code(text: str) -> str:
    """Le script sans ses commentaires (bloc <# … #> et fin de ligne), où `&&` peut être cité."""
    text = re.sub(r"<#.*?#>", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)#.*$", "", line) for line in text.splitlines())


def test_scripts_are_found() -> None:
    assert len(SCRIPTS) >= 10


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_script_is_utf8_with_bom(script: Path) -> None:
    assert script.read_bytes()[:3] == b"\xef\xbb\xbf", f"{script.name} : UTF-8 sans BOM (PowerShell 5.1 lit l'ANSI)"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_script_has_no_pipeline_chain_operators(script: Path) -> None:
    code = _code(script.read_text(encoding="utf-8-sig"))
    assert "&&" not in code, f"{script.name} : `&&` absent de PowerShell 5.1 (utiliser `A; if ($?) {{ B }}`)"
