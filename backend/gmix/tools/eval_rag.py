"""Évalue la couverture du corpus RAG d'un domaine avec les questions de référence ai/evals/<domaine>.rag.jsonl.

Pour chaque question : recherche hybride top-k, puis vérification qu'un passage retrouvé contient l'un des
termes attendus (`must_contain_any`). Indicateur : rappel@k. Aucun token LLM consommé (embeddings seulement).

Usage : python -m gmix.tools.eval_rag supply-chain [--k 4]
"""

import argparse
import asyncio
import json
import sys

from gmix.db import get_engine, get_sessionmaker
from gmix.llm.service import LLMService
from gmix.rag.retrieval import search
from gmix.settings import get_settings


def load_cases(domain: str) -> list[dict]:
    path = get_settings().gmix_ai_dir / "evals" / f"{domain}.rag.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def evaluate(domain: str, k: int) -> float:
    cases = load_cases(domain)
    llm = LLMService.from_settings(with_cache=False)
    hits = 0
    try:
        async with get_sessionmaker()() as session:
            for case in cases:
                results = await search(
                    session,
                    query_vector=await llm.embed_query(case["question"]),
                    query_text=case["question"],
                    domain=domain,
                    k=k,
                )
                text = " ".join(hit.content.lower() for hit in results)
                found = any(term.lower() in text for term in case["must_contain_any"])
                hits += found
                titles = ", ".join(dict.fromkeys(hit.title for hit in results)) or "aucun passage"
                print(f"[{'OK' if found else 'KO'}] {case['id']:<16} {titles}")
    finally:
        await llm.aclose()
        await get_engine().dispose()
    recall = hits / len(cases) if cases else 0.0
    print(f"Rappel@{k} : {hits}/{len(cases)} ({recall:.0%})")
    return recall


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("domain")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--min", type=float, default=0.0, help="rappel minimal attendu (code retour 1 sinon)")
    args = parser.parse_args()
    sys.exit(0 if asyncio.run(evaluate(args.domain, args.k)) >= args.min else 1)
