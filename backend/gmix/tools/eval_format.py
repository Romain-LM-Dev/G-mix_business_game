"""Mesure : Ollama applique-t-il ensemble `pattern`, `maxLength`, `minLength`, `minItems` et `maxItems` du format
contraint (`format` = schéma JSON) ? Appels réels, aucune doublure ; chaque sonde est rejouée avec N graines.

Usage (depuis backend\\) : python -m gmix.tools.eval_format [--model small] [--runs 6]
Rapport : ai/evals/results/game.design-format-<alias>-<date>.md (comptes seulement : aucune latence, GPU partagé).
"""

import argparse
import asyncio
import json
from collections.abc import Callable
from datetime import date
from typing import Any

from gmix.llm.catalog import load_catalog
from gmix.llm.ollama import OllamaClient, OllamaError
from gmix.settings import get_settings

NO_DIGIT = r"^[^0-9]*$"  # motif de l'annexe 0008 §3.1 : liste noire
WIDE = "\uff10-\uff19"  # chiffres pleine chasse : qwen2.5 les écrit pour contourner [0-9]
NO_DIGIT_WIDE = f"^[^0-9{WIDE}]*$"
# Liste blanche : lettres latines accentuées, espace et ponctuation courante (jamais de chiffre, de guillemet droit,
# d'antislash ni de caractère de contrôle). Le « - » final est littéral : GBNF refuse l'échappement « \- ».
ALLOWED = "A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff\u0152\u0153 ,.;:!?'\u2019\u00ab\u00bb()\u2013-"
WHITELIST = f"^[{ALLOWED}]*$"


def white(low: int, high: int) -> str:
    """Liste blanche bornée : la longueur est dans le motif, car maxLength est ignoré quand `pattern` est présent."""
    return f"^[{ALLOWED}]{{{low},{high}}}$"


WHITELIST_20_40, WHITELIST_20_80 = white(20, 40), white(20, 80)

BASTILLE = (
    "Écris une phrase de plus de trois cents caractères qui donne la date de la prise de la Bastille en chiffres."
)
IDEAS = "Donne huit idées d'objectifs pédagogiques pour un jeu sur les stocks, chacune en une phrase."
REALISTE = (
    "Résume en une phrase le jeu voulu par le formateur, sans aucun chiffre. Demande du formateur : « 12 semaines, "
    "3 lignes de production, un objectif de 95 % de livraisons à l'heure et 20 000 euros de trésorerie au départ. »"
)


LONG = (
    "Présente le jeu voulu par le formateur : un contexte, une accroche et deux à quatre objectifs, sans aucun "
    "chiffre. Demande du formateur : « Un atelier de rangement, douze semaines, des fournisseurs peu fiables, et des "
    "élèves qui doivent apprendre à fixer un stock de sécurité. »"
)


def _obj(**props: Any) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _text(**c: Any) -> dict[str, Any]:
    return {"type": "string", **c}


def _list(item: dict[str, Any], **c: Any) -> dict[str, Any]:
    return {"type": "array", "items": item, **c}


def check_text(value: Any, *, digits: bool = False, low: int = 0, high: int = 10**6) -> list[str]:
    """Violations d'un texte : chiffre de n'importe quelle écriture (si `digits`), trop court, trop long."""
    s = str(value)
    found = ["chiffre"] if digits and any(c.isdigit() for c in s) else []
    return found + (["trop court"] if len(s) < low else []) + (["trop long"] if len(s) > high else [])


def check_count(items: list[Any], low: int, high: int) -> list[str]:
    return [] if low <= len(items) <= high else [f"{len(items)} éléments"]


def _texte(schema: dict[str, Any], prompt: str, **check: Any) -> tuple[dict[str, Any], str, Callable[..., list[str]]]:
    return _obj(texte=schema), prompt, lambda d: check_text(d["texte"], **check)


VERBS = {"calculer", "comparer", "arbitrer"}
PROBES: dict[str, tuple[dict[str, Any], str, Callable[[dict[str, Any]], list[str]]]] = {
    # Sondes volontairement hostiles : le prompt demande des chiffres, le format les interdit.
    "pattern seul [^0-9] (prompt hostile)": _texte(_text(pattern=NO_DIGIT), BASTILLE, digits=True),
    "pattern seul [^0-9] et pleine chasse exclus (prompt hostile)": _texte(
        _text(pattern=NO_DIGIT_WIDE), BASTILLE, digits=True
    ),
    "pattern seul, liste blanche (prompt hostile)": _texte(_text(pattern=WHITELIST), BASTILLE, digits=True),
    "pattern liste blanche + maxLength 40 (prompt hostile)": _texte(
        _text(pattern=WHITELIST, maxLength=40), BASTILLE, digits=True, high=40
    ),
    "pattern liste blanche avec {20,40} (prompt hostile)": _texte(
        _text(pattern=WHITELIST_20_40), BASTILLE, digits=True, low=20, high=40
    ),
    # Prompt réaliste : la demande contient des chiffres, la consigne les interdit.
    "pattern seul [^0-9] (prompt réaliste)": _texte(_text(pattern=NO_DIGIT), REALISTE, digits=True),
    "pattern liste blanche avec {20,80} (prompt réaliste)": _texte(
        _text(pattern=WHITELIST_20_80), REALISTE, digits=True, low=20, high=80
    ),
    "textes longs : liste blanche {20,700}, {40,500} et 2 à 4 objectifs {10,140}": (
        _obj(
            contexte=_text(pattern=white(20, 700)),
            accroche=_text(pattern=white(40, 500)),
            objectifs=_list(_text(pattern=white(10, 140)), minItems=2, maxItems=4),
        ),
        LONG,
        lambda d: (
            check_text(d["contexte"], digits=True, low=20, high=700)
            + check_text(d["accroche"], digits=True, low=40, high=500)
            + check_count(d["objectifs"], 2, 4)
            + [v for o in d["objectifs"] for v in check_text(o, digits=True, low=10, high=140)]
        ),
    ),
    "maxLength 40 seul": _texte(_text(maxLength=40), BASTILLE, high=40),
    "minLength 20 + maxLength 40": _texte(_text(minLength=20, maxLength=40), "Écris un seul mot.", low=20, high=40),
    "minItems 2 + maxItems 3": (
        _obj(liste=_list(_text(maxLength=80), minItems=2, maxItems=3)),
        IDEAS,
        lambda d: check_count(d["liste"], 2, 3),
    ),
    "objets : minItems 2, maxItems 4, enum, liste blanche {20,40}": (
        _obj(
            objectifs=_list(
                _obj(verbe={"enum": sorted(VERBS)}, texte=_text(pattern=WHITELIST_20_40)), minItems=2, maxItems=4
            )
        ),
        IDEAS + " Donne les montants en chiffres.",
        lambda d: (
            check_count(d["objectifs"], 2, 4)
            + [v for o in d["objectifs"] for v in check_text(o["texte"], digits=True, low=20, high=40)]
            + ([] if all(o["verbe"] in VERBS for o in d["objectifs"]) else ["enum"])
        ),
    ),
}


async def run(alias: str, runs: int) -> str:
    catalog = load_catalog()
    model = catalog.models[alias]
    settings = get_settings()
    client = OllamaClient(settings.ollama_base_url, api_key=settings.ollama_api_key)
    system = {"role": "system", "content": "Tu réponds en français, uniquement par un objet JSON."}
    rows, samples, errors = [], [], set()
    version = ""
    try:
        version = await client.version()
        for name, (schema, prompt, check) in PROBES.items():
            counts = {"json_valide": 0, "tronque": 0, "erreur": 0, "invalide": 0, "viole": 0}
            kinds: set[str] = set()
            shown = 0  # deux exemples par sonde au plus
            for seed in range(1, runs + 1):
                try:
                    result = await client.chat(
                        model.name,
                        [system, {"role": "user", "content": prompt}],
                        options={"num_ctx": model.num_ctx, "num_predict": 400, "temperature": 0.4, "seed": seed},
                        fmt=schema,
                        keep_alive=catalog.keep_alive,
                    )
                except OllamaError as error:  # ex. « token repeat limit reached » : le modèle boucle
                    counts["erreur"] += 1
                    errors.add(str(error)[-90:])
                    continue
                if result.done_reason == "length":
                    counts["tronque"] += 1
                    continue
                try:
                    data = json.loads(result.content)
                    violations = check(data)
                except (json.JSONDecodeError, KeyError, TypeError):
                    counts["invalide"] += 1
                    continue
                counts["json_valide"] += 1
                if violations:
                    counts["viole"] += 1
                    kinds |= set(violations)
                    if shown < 2:
                        shown += 1
                        samples.append(f"- {name} (graine {seed}) : {', '.join(violations)} : `{result.content[:160]}`")
            cells = [
                f"{counts['json_valide']}/{runs}",
                *(counts[k] for k in ("tronque", "erreur", "invalide", "viole")),
            ]
            rows.append("| " + " | ".join([name, *map(str, cells), ", ".join(sorted(kinds)) or "-"]) + " |")
    finally:
        await client.aclose()
    head = [
        f"# Format contraint d'Ollama : `pattern`, `maxLength`, `minItems`, `maxItems` ({date.today()})",
        "",
        f"Modèle : {model.name} (alias `{alias}`), Ollama {version}, température 0,4, "
        f"num_predict 400, {runs} graines par sonde, `gmix.tools.eval_format`. Comptes seulement, aucune latence "
        "(GPU partagé avec Godot).",
        "",
        "JSON valide = se lit et respecte le schéma de la sonde ; Contrainte violée = parmi les JSON valides, au moins "
        "un défaut (chiffre de toute écriture, texte trop court ou trop long, nombre d'éléments).",
        "",
        "| Sonde | JSON valide | Tronqué | Erreur Ollama | Illisible | Contrainte violée | Violations |",
        "|---|---|---|---|---|---|---|",
    ]
    motifs = [f"- `{n}` = `{v}`" for n, v in (("liste noire", NO_DIGIT), ("liste blanche", WHITELIST_20_40))]
    return "\n".join(
        [
            *head,
            *rows,
            "",
            "## Motifs",
            "",
            *motifs,
            "",
            "## Erreurs d'Ollama",
            "",
            *[f"- `{e}`" for e in sorted(errors)],
            "",
            "## Exemples de violations",
            "",
            *samples,
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="small", help="alias de ai/models.yaml (défaut : small)")
    parser.add_argument("--runs", type=int, default=6, help="graines par sonde")
    args = parser.parse_args()
    report = asyncio.run(run(args.model, args.runs))
    out = get_settings().gmix_ai_dir / "evals" / "results" / f"game.design-format-{args.model}-{date.today()}.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
