# Prompts des agents IA runtime

Un fichier par tâche de `ai/models.yaml`, nommé d'après l'id de la tâche (`npc.dialogue.md`).
Chargés par `gmix.llm.prompts.load_prompt()`.

| Fichier (2026-10-28) | Version | Rôle |
|---|---|---|
| `npc.dialogue.md` | 3 | réplique d'un agent PNJ : ses faits (briefings), ses notions, l'historique des échanges |
| `player.intent.questions.yaml` | 4 | questions fermées du filtre (intention, injection) et seuil d'injection 0,6 |
| `game.design.concept.md` | 1 | conception du scénario, des mécaniques et des objectifs (ADR 0008, sortie JSON contrainte) |
| `game.design.cast.md` | 1 | noms, caractères et présentations des personnages |
| `game.design.journey.md` | 1 | panneaux, outils, didacticiel et questions de débrief |

Les prompts `game.design.*` ont une section `## repair` (variable `errors`, hors `variables`) : pour réparer, le code
envoie `[system, user, assistant(sortie fautive), user(repair)]` (`PromptTemplate.render_repair`). Leurs variables
sont des blocs de texte construits par `gmix.game.design.*_variables` (annexe 0008 §4.3) ; le schéma n'est jamais
recopié dans le prompt, et aucun chiffre n'y figure : les nombres viennent du moteur.

## Format

```markdown
---
task: npc.dialogue
version: 3          # incrémenter à chaque changement de comportement (traçabilité des générations)
variables: [npc_name, rag_context]
---
## system
Texte du rôle et des règles, avec $npc_name.
## user
$player_message
```

Variables en `$nom` / `${nom}` (`string.Template`) : on peut écrire du JSON sans échappement.
Un vrai `$` s'écrit `$$`. Une variable déclarée mais non fournie lève une erreur.

## Règles d'économie de tokens

- Prompt système < 250 tokens : rôle, 4 à 6 règles, rien d'autre. Chaque token est repayé à chaque appel.
- **Ne jamais recopier le schéma JSON dans le prompt** : Ollama contraint déjà la sortie (`format`).
  Ne décrire que la sémantique non évidente d'un champ, en une ligne.
- Pas d'exemples (few-shot) tant qu'une évaluation (`ai/evals`) ne montre pas qu'ils sont nécessaires.
- Contexte RAG injecté via `$rag_context` déjà tronqué au budget de la tâche (`rag.max_context_tokens`).
- Questions fermées (oui/non, choix, note) : pas de prompt de chat, une liste de questions pour un
  modèle de décision (`*.questions.yaml`, format Jev/SystemOne, `LLMService.decide`). Ce fichier porte aussi
  `thresholds` (seuils d'interprétation des probabilités, lus par `load_thresholds`, non envoyés au modèle) et, en
  commentaire de tête, les mesures qui les justifient.
- Historique de dialogue : les 6 derniers échanges (`MEMORY_TURNS` de gmix/game/npc.py) ; un résumé au-delà reste à faire.

## Qualité

- Toute affirmation chiffrée, légale ou normative doit venir des extraits [S…] : sinon, rester général.
- Les PNJ ont un périmètre d'expertise (`npc.expertise`) : hors périmètre, ils le disent.
- Les messages joueurs passent d'abord par `player.intent` (détection hors-sujet / injection).

## Changer un prompt ou un seuil

1. Incrémenter `version` : chaque rapport d'évaluation consigne la version du prompt qu'il a jouée.
2. Rejouer `gmix.tools.eval_dialogue` (séries A et B, depuis `backend\`) pour `npc.dialogue`, ou
   `gmix.tools.eval_decision player.intent` pour les questions : commandes et indicateurs dans ai/evals/README.md.
3. Dater la mesure dans docs/ai-runtime.md ; ne pas régler un critère sur les seuls cas qui le mesurent (les gains
   du filtre mesurés sur la série F sont optimistes) : régler sur le jeu de réglage (série F, 34 messages), valider
   une fois sur le jeu de contrôle (série C, `ai/evals/player.intent.control.jsonl`), qui ne sert jamais à régler.
   Ne pas recopier de message de ces jeux dans les questions (`tests/test_eval_contamination.py`).
