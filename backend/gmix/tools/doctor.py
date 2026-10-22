"""Diagnostic des services sans lancer l'API : python -m gmix.tools.doctor (code retour 1 si dégradé)."""

import asyncio
import sys

from gmix.db import get_engine
from gmix.health import full_health
from gmix.llm.service import LLMService


async def main() -> int:
    llm = LLMService.from_settings(with_cache=False)
    try:
        report = await full_health(llm)
    finally:
        await llm.aclose()
        await get_engine().dispose()

    for name, result in report["services"].items():
        details = {k: v for k, v in result.items() if k != "ok" and v not in (None, [], "")}
        print(f"[{'OK' if result['ok'] else 'KO'}] {name:<9} {details}")
    ollama = report["services"]["ollama"]
    for key, label in (("missing_models", "requis"), ("missing_optional_models", "optionnels")):
        if ollama.get(key):
            print(f"Modèles {label} absents : " + ", ".join(ollama[key]) + "  ->  ollama pull <modèle>")
    print(f"Statut global : {report['status']}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
