from gmix.rag.ingest_dir import SOURCES_FILE, add_source_row, knowledge_dir, read_sources, source_row
from gmix.tools.eval_rag import load_cases
from gmix.tools.fetch_wikipedia import clean_math, slugify, to_markdown

MATH_EXTRACT = (
    "réapprovisionnement \n  \n    \n      \n        T\n      \n    \n    {\\displaystyle T}\n  \n"
    " à déterminer. Le stock initial est \n  \n    \n      \n        k\n        ⋅\n        T\n      \n    \n"
    "    {\\displaystyle k\\cdot T}\n  \n."
)


def test_math_blocks_become_inline_latex() -> None:
    assert clean_math(MATH_EXTRACT) == "réapprovisionnement $T$ à déterminer. Le stock initial est $k\\cdot T$ ."


def test_plain_paragraphs_are_not_swallowed_by_math_cleanup() -> None:
    text = "Premier paragraphe.\n\nDeuxième paragraphe avec une formule \n  \n    x\n    {\\displaystyle x}\n  \n fin."
    assert clean_math(text) == "Premier paragraphe.\n\nDeuxième paragraphe avec une formule $x$ fin."


def test_math_cleanup_stays_linear_on_long_blank_runs() -> None:
    """Régression : des centaines de lignes blanches sans formule ne doivent pas bloquer le nettoyage."""
    import time

    text = "Paragraphe.\n" + "   \n" * 400 + "        x\n" * 50 + "Fin sans formule."
    start = time.perf_counter()
    assert clean_math(text) == text
    assert time.perf_counter() - start < 1.0


def test_markdown_conversion_keeps_attribution_and_drops_reference_sections() -> None:
    extract = "Intro.\n\n== Description ==\nTexte utile.\n\n== Notes et références ==\nRéf. 1"
    markdown = to_markdown("Stock de sécurité", "fr", 42, extract)
    assert markdown.startswith("# Stock de sécurité")
    assert "oldid=42" in markdown and "CC BY-SA 4.0" in markdown
    assert "## Description" in markdown and "Réf. 1" not in markdown
    assert slugify("Stock de sécurité (gestion)") == "stock-de-securite-gestion"


def test_supply_chain_corpus_is_fully_declared_with_licenses() -> None:
    """Traçabilité (exigence n° 1) : tout fichier du corpus a une licence dans SOURCES.md, toute ligne un fichier."""
    folder = knowledge_dir("supply-chain")
    declared = read_sources((folder / SOURCES_FILE).read_text(encoding="utf-8"))
    on_disk = {p.name for p in folder.glob("*.md") if p.name not in {SOURCES_FILE, "README.md"}}
    assert on_disk == set(declared)
    assert [name for name, row in declared.items() if not row["Licence ou droit d'usage"]] == []


def test_rag_reference_questions_are_well_formed() -> None:
    domain = "supply-chain"
    cases = load_cases(domain)
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["question"].strip() and case["must_contain_any"] and case["expected_points"], case["id"]
    declared = read_sources((knowledge_dir(domain) / SOURCES_FILE).read_text(encoding="utf-8"))
    titles = {row["Titre"].lower() for row in declared.values()}
    for case in cases:
        for expected in case.get("expected_docs", []):  # chaque document attendu existe dans le corpus déclaré
            assert any(expected.lower() in title for title in titles), (case["id"], expected)


def test_sources_table_is_parsed_and_extended_in_place(tmp_path) -> None:
    sources = tmp_path / "SOURCES.md"
    sources.write_text(
        "# Sources\n\n| Fichier | Titre | Licence ou droit d'usage |\n|---|---|---|\n"
        "| cours.pdf | Cours | usage interne |\n\n## Statut\nTexte après le tableau.\n",
        encoding="utf-8",
    )
    add_source_row(sources, source_row(["wiki.md", "Wiki", "CC BY-SA 4.0"]))
    parsed = read_sources(sources.read_text(encoding="utf-8"))
    assert parsed["cours.pdf"]["Licence ou droit d'usage"] == "usage interne"
    assert parsed["wiki.md"]["Titre"] == "Wiki"
    assert sources.read_text(encoding="utf-8").rstrip().endswith("Texte après le tableau.")
