# Prompts des agents IA runtime

Un fichier par tâche de `ai/models.yaml`, nommé d'après l'id de la tâche (`game.outline.md`).
Chargés par `gmix.llm.prompts.load_prompt()`.

## Format

```markdown
---
task: npc.dialogue
version: 2          # incrémenter à chaque changement de comportement (traçabilité des générations)
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
  modèle de décision (`*.questions.yaml`, format Jev/SystemOne, `LLMService.decide`).
- Historique de dialogue : résumer au-delà de 6 échanges plutôt que tout renvoyer.

## Qualité

- Toute affirmation chiffrée, légale ou normative doit venir des extraits [S…] : sinon, rester général.
- Les PNJ ont un périmètre d'expertise (`npc.expertise`) : hors périmètre, ils le disent.
- Les messages joueurs passent d'abord par `player.intent` (détection hors-sujet / injection).
