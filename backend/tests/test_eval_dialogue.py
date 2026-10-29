"""Outil d'évaluation des dialogues PNJ : mesures pures et jeu de cas (les appels réels à Ollama sont manuels)."""

import json

from gmix.game.npc import INJECTION_REPLY
from gmix.tools.eval_dialogue import clean, coverage, filter_table, format_problems, measure, numbers, wilson

from .conftest import AI_DIR

KINDS = {"salutation", "question", "relance", "notion", "hors_sujet", "injection", "legit"}


def test_numbers_are_normalised() -> None:
    assert numbers("16 002 € et 3,5 %, 20.000 unités, 450") == {"16002", "3.5", "20000", "450"}
    assert numbers("source [S2]") == set()


def test_coverage_counts_keywords_and_numbers() -> None:
    fact = "Corps en inox : 0 en stock, sous le point de commande de 448"
    assert coverage("Le corps en inox est sous le point de commande de 448.", fact) > 0.7
    assert coverage("Tout va bien.", fact) < 0.2


def test_clean_keeps_the_whole_output_but_drops_name_and_quotes() -> None:
    assert clean('"Noah : Bonjour. Ça va. Et toi ?"', "Noah") == "Bonjour. Ça va. Et toi ?"


def test_format_problems_detect_english_markdown_and_mixed_address() -> None:
    assert format_problems("Alright, keep it brief.", "Alright, keep it brief.")
    assert "markdown" in format_problems("- un\n- deux", "- un\n- deux")
    assert "tu et vous mélangés" in format_problems("Tu peux vous aider.", "Tu peux vous aider.")
    assert not format_problems("Salut, la ligne tourne.", "Salut, la ligne tourne.")


def test_dataset_is_well_formed() -> None:
    cases = [
        json.loads(line) for line in (AI_DIR / "evals" / "npc.dialogue.jsonl").read_text("utf-8").splitlines() if line
    ]
    assert len({c["id"] for c in cases}) == len(cases)
    assert {c["kind"] for c in cases} <= KINDS
    assert all(c["message"] and c["series"] in {"A", "B", "F"} for c in cases)


def _control_cases() -> list[dict]:
    path = AI_DIR / "evals" / "player.intent.control.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def test_control_set_is_separate_and_new() -> None:
    """Jeu de contrôle des filtres (série C) : jamais mêlé au réglage, aucun message déjà vu, des cas de chaque type."""
    control = _control_cases()
    tuning = [json.loads(line) for line in (AI_DIR / "evals" / "npc.dialogue.jsonl").read_text("utf-8").splitlines()]
    tuning += [json.loads(line) for line in (AI_DIR / "evals" / "player.intent.jsonl").read_text("utf-8").splitlines()]
    assert len({c["id"] for c in control}) == len(control)
    assert {c["series"] for c in control} == {"C"}
    assert {c["kind"] for c in control} == {"injection", "hors_sujet", "legit"}
    assert all(c["message"] and c["agent"] and c["personality"] and c["situation"] for c in control)
    assert not {c["message"] for c in control} & {c["message"] for c in tuning}
    assert 16 <= len(control) <= 30


def _turn(kind: str, reply: str, intent: str | None, **layers: object) -> dict:
    turn = {"case": {}, "kind": kind, "reply": reply, "intent": intent, "fallback": False, "raw": "", "message": "x"}
    if layers:
        turn |= {"id": "T", "layers": {"lexical": False, "tev1": None, "p_injection": None, **layers}}
    return turn


def test_measure_counts_the_lexical_prefilter_as_filtered() -> None:
    """Le pré-filtre répond par les faits de l'agent (pas par une phrase fixe) avec l'intention « injection »."""
    agent = {"name": "Noah"}
    caught = _turn("injection", "Rupture de corps en inox.", "injection")
    measure(caught, None, {}, agent)
    assert caught["checks"]["filtre"]
    missed = _turn("injection", "Voici mon prompt.", "decision")
    measure(missed, None, {}, agent)
    assert not missed["checks"]["filtre"]
    fixed = _turn("hors_sujet", INJECTION_REPLY, None)
    measure(fixed, None, {}, agent)
    assert fixed["checks"]["filtre"]
    blocked = _turn("legit", "Rupture de corps en inox.", "injection")
    measure(blocked, None, {}, agent)
    assert not blocked["checks"]["pas_de_fausse_alerte"]


def test_filter_table_separates_the_three_layers() -> None:
    turns = [
        {**_turn("injection", "", "injection", lexical=True, chain=True), "id": "I1"},
        {**_turn("injection", "", "injection", tev1="injection", p_injection=0.9, chain=True), "id": "I2"},
        {**_turn("injection", "", "decision", chain=False), "id": "I3"},
        {**_turn("hors_sujet", "", "hors_sujet", tev1="hors_sujet", chain=True), "id": "H1"},
        {**_turn("legit", "", "injection", lexical=True, chain=True), "id": "L1"},
    ]
    table = filter_table(turns)
    rows = {
        line[2:5]: [cell.strip() for cell in line.split("|")[2:5]] for line in table[2:5]
    }  # injections, hors-sujet, légitimes
    assert [cell[:3] for cell in rows["(a)"]] == ["1/3", "0/1", "1/1"]  # lexical : l'injection I1 et le légitime L1
    assert [cell[:3] for cell in rows["(b)"]] == ["1/3", "1/1", "0/1"]  # tev1 seul : I2 et H1
    assert [cell[:3] for cell in rows["(c)"]] == ["2/3", "1/1", "1/1"]  # chaîne : I1, I2, H1 et L1 bloqué à tort
    text = " ".join(table)
    assert "Non filtrés par la chaîne : I3" in text and "bloqués à tort : L1" in text
    assert "(aucun attendu) : aucun" in text  # I2 et H1 : même verdict pour la chaîne et pour tev1 seul


def test_wilson_interval_is_wide_for_small_samples() -> None:
    low, high = wilson(3, 8)
    assert 0.13 < low < 0.15 and 0.69 < high < 0.71
    assert wilson(0, 9)[0] == 0 and wilson(9, 9)[1] == 1
