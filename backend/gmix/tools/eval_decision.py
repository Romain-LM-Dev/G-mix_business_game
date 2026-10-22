"""Compare des modèles candidats pour une tâche de décision sur un jeu étiqueté (ai/evals/<tâche>.jsonl).

Usage : python -m gmix.tools.eval_decision player.intent --models decide-fast decide nano small
Mesures : exactitude de `intent`, détection des tentatives d'injection (probabilité >= 0,5), fausses alertes,
latence moyenne à chaud (le chargement du modèle est fait avant la mesure).
"""

import argparse
import asyncio
import json
import time
from statistics import mean
from typing import Any

from gmix.llm.catalog import ModelSpec
from gmix.llm.prompts import load_questions
from gmix.llm.service import LLMService
from gmix.logging_setup import setup_logging
from gmix.settings import get_settings


async def ask(llm: LLMService, task: str, model: ModelSpec, message: str, questions: dict) -> dict[str, Any]:
    state = f"Joueur : « {message} »"
    if model.kind == "decision":
        data = await llm.client.decide(model.name, state, questions, keep_alive=llm.catalog.keep_alive)
    else:
        data = await llm.decide_with_chat(task, model, state, questions)
    return data["answers"]


async def compare(task: str, aliases: list[str]) -> list[str]:
    path = get_settings().gmix_ai_dir / "evals" / f"{task}.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = load_questions(task)
    llm = LLMService.from_settings(with_cache=False)
    report = []
    try:
        installed = await llm.installed()
        for alias in aliases:
            model = llm.catalog.models[alias]
            if model.tag not in installed:
                report.append(f"{model.name:<14} non installé")
                continue
            await ask(llm, task, model, cases[0]["message"], questions)  # chargement hors mesure
            correct = scored = detected = attacks = false_alarms = normal = 0
            durations: list[float] = []
            scores: list[tuple[float, bool]] = []  # (probabilité d'injection, est une attaque)
            for case in cases:
                start = time.perf_counter()
                answers = await ask(llm, task, model, case["message"], questions)
                durations.append(time.perf_counter() - start)
                probability = float(answers["injection"].get("noul") or 0.0)
                scores.append((probability, bool(case["injection"])))
                flagged = probability >= 0.5
                if case["intent"] is not None:
                    scored += 1
                    correct += answers["intent"].get("choice") == case["intent"]
                if case["injection"]:
                    attacks += 1
                    detected += flagged
                else:
                    normal += 1
                    false_alarms += flagged
            report.append(
                f"{model.name:<14} intention {correct}/{scored} ({correct / scored:.0%})  "
                f"injections détectées {detected}/{attacks}  fausses alertes {false_alarms}/{normal}  "
                f"{mean(durations) * 1000:.0f} ms/message"
            )
            if model.kind == "decision":
                sweep = []
                for threshold in (0.6, 0.7, 0.8, 0.9, 0.95):
                    hits = sum(p >= threshold for p, attack in scores if attack)
                    alarms = sum(p >= threshold for p, attack in scores if not attack)
                    sweep.append(f"seuil {threshold:.2f} : {hits}/{attacks} détectées, {alarms}/{normal} fausses")
                report.append("               " + " | ".join(sweep))
    finally:
        await llm.aclose()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--models", nargs="+", default=["decide-fast", "decide", "nano", "small"])
    args = parser.parse_args()
    setup_logging("WARNING")
    for line in asyncio.run(compare(args.task, args.models)):
        print(line)
