"""Télécharge des articles Wikipédia (CC BY-SA 4.0) en texte brut dans knowledge/<domaine>/ et les déclare
dans SOURCES.md (titre, révision, licence), prêts pour `python -m gmix.rag.ingest_dir <domaine>`.

Usage : python -m gmix.tools.fetch_wikipedia supply-chain --lang fr "Stock" "Formule de Wilson"

Wikipédia est un socle de départ, pas une référence : à compléter par des cours et des sources officielles.
"""

import argparse
import re
import time
import unicodedata
from datetime import date
from urllib.parse import quote

import httpx

from gmix.rag.ingest_dir import (
    SOURCES_COLUMNS,
    SOURCES_FILE,
    add_source_row,
    knowledge_dir,
    read_sources,
    source_row,
)
from gmix.settings import get_settings


def user_agent(contact: str) -> str:
    """Politique Wikimédia (https://w.wiki/4wJS) : nom, contact réel (e-mail ou URL) et bibliothèque, sinon HTTP 403.
    En-tête HTTP : ASCII uniquement."""
    if not contact or not contact.isascii():
        raise SystemExit(
            "WIKI_CONTACT manquant ou non ASCII dans .env : indiquez un e-mail ou une URL de contact du projet "
            "(exigé par Wikimédia pour les accès automatisés)."
        )
    return f"G-mix/0.1 ({contact}; business game knowledge base) httpx/{httpx.__version__}"


LICENSE = "CC BY-SA 4.0 (attribution : contributeurs de Wikipédia)"
DROPPED_SECTIONS = {
    "voir aussi", "notes et références", "références", "notes", "bibliographie", "liens externes",
    "articles connexes", "see also", "references", "notes and references", "external links",
    "further reading", "bibliography", "sources",
}  # fmt: skip
HEADING = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$")
# Une formule extraite = lignes indentées de symboles MathML puis « {\displaystyle LaTeX} » : on garde le LaTeX.
# Branches exclusives (ligne vide OU ligne indentée non vide) : pas de retour arrière exponentiel.
MATH = re.compile(
    r"[ \t]*\n(?:[ \t]*\n|[ \t]{2,}(?!\{\\displaystyle)\S[^\n]*\n)*"
    r"[ \t]*\{\\displaystyle (?P<tex>[^\n]*)\}[ \t]*\n(?:[ \t]*\n)*[ \t]*"
)


def clean_math(text: str) -> str:
    return MATH.sub(lambda m: f" ${m.group('tex').strip()}$ ", text)


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def to_markdown(title: str, lang: str, revid: int, extract: str) -> str:
    url = f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}?oldid={revid}"
    lines = [
        f"# {title}",
        "",
        f"> Source : Wikipédia ({lang}), « {title} », révision {revid} : {url}",
        f"> Licence : {LICENSE}. Texte brut converti, sections de références retirées.",
        "",
    ]
    for line in clean_math(extract).splitlines():
        heading = HEADING.match(line)
        if heading:
            if heading.group(2).strip().lower() in DROPPED_SECTIONS:
                break
            lines.append("#" * len(heading.group(1)) + " " + heading.group(2))
        else:
            lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def fetch(client: httpx.Client, lang: str, title: str) -> tuple[str, int, str]:
    params = {
        "action": "query",
        "prop": "extracts|revisions",
        "explaintext": 1,
        "exsectionformat": "wiki",
        "rvprop": "ids",
        "titles": title,
        "redirects": 1,
        "format": "json",
        "formatversion": 2,
    }
    response = client.get(f"https://{lang}.wikipedia.org/w/api.php", params=params)
    response.raise_for_status()
    page = response.json()["query"]["pages"][0]
    if page.get("missing"):
        raise ValueError(f"article absent : {lang}:{title}")
    return page["title"], page["revisions"][0]["revid"], page.get("extract", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Articles Wikipédia -> knowledge/<domaine>/")
    parser.add_argument("domain")
    parser.add_argument("titles", nargs="+")
    parser.add_argument("--lang", default="fr")
    args = parser.parse_args()

    folder = knowledge_dir(args.domain)
    folder.mkdir(parents=True, exist_ok=True)
    sources_path = folder / SOURCES_FILE
    if not sources_path.exists():
        header = source_row(SOURCES_COLUMNS)
        separator = "|" + "|".join("---" for _ in SOURCES_COLUMNS) + "|"
        sources_path.write_text(f"# Sources : {args.domain}\n\n{header}\n{separator}\n", encoding="utf-8")
    known = read_sources(sources_path.read_text(encoding="utf-8"))

    with httpx.Client(headers={"User-Agent": user_agent(get_settings().wiki_contact)}, timeout=30) as client:
        for requested in args.titles:
            title, revid, extract = fetch(client, args.lang, requested)
            filename = f"wikipedia-{args.lang}-{slugify(title)}.md"
            (folder / filename).write_text(to_markdown(title, args.lang, revid, extract), encoding="utf-8")
            if filename not in known:
                row = [filename, title, f"Contributeurs de Wikipédia ({args.lang})", f"rév. {revid}", LICENSE, ""]
                add_source_row(sources_path, source_row(row))
                known[filename] = {}
            print(f"{filename} ({len(extract)} caractères)")
            time.sleep(0.5)  # politesse envers l'API Wikimédia
    print(f"Déclaré dans {sources_path} ; ingestion : python -m gmix.rag.ingest_dir {args.domain}")
    print(f"(téléchargé le {date.today().isoformat()})")


if __name__ == "__main__":
    main()
