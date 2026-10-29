# Reprise de session (après /clear) - 29/10/2026

## État
- Commit e57bf28 « V2 », arbre propre selon godot-dev. ADR 0006 à 0009 ; 0008 et 0009 acceptés par défaut le 29/10 (l'utilisateur peut revenir dessus).
- Fait : spec de conception (ADR 0008 étape 1, 207 tests de contrat) ; tâches IA `game.design.*`, `LLMService.structured`, prompts, 24 cas d'éval (étape 4).
- DA appliquée à l'interface, à l'ambiance 3D et à la caméra Sims (`godot/scenes/common/ui_tokens.gd`) : `-Check` 127 fichiers OK, `-Tour` 112 écrans 0 défaut, `-Flow -NoLlm` 519 vérifications 0 échec.
- Coût : compaction automatique à 150 000 ; effort Sonnet medium / Opus high dans `~/.claude/settings.json` ; `.claude/settings.local.json` hors git.
- Mesure ia-runtime (`ai/evals/results/game.design-format-small-2026-10-29.md`) : `pattern` et `maxLength` ne s'appliquent pas ensemble ; seule une liste blanche bornée dans le motif donne 0 chiffre.

## À faire, dans l'ordre (plans : ADR 0008 annexe §10 et §10.1)
1. Amendement ADR 0009 (éditeur de grille, menus contextuels).
2. Vague A restante : spec 0009 (moteur-jeu) ; pack usine (game-designer : règles de placement sourcées, outils formateur, classes de distance) ; fiches sourcées (rag-knowledge, étape 4b).
3. Vague B : `design.py` + `layout.py` (moteur-jeu) ; routes + migration (backend-api) ; assets usine à 100 % (assets-3d, étape 5c) ; écrans (godot-dev).
4. Worker generation (pipeline-kafka), scripts (devops).
5. `flow_test` parcours D, `eval_design`, docs, qa-reviewer.

## Petits restes
- Zoom molette en 3e personne.
- Collisions de 5 assets : prop_kpi_screen, prop_desk_computer, prop_meeting_table, prop_pallet, prop_pallet_stack.
- `flow_test` parcours B et V.
- Garde-fou « nombre absent des faits » dans `npc.py` (décision utilisateur attendue).
- Docs : `docs/ai-runtime.md` (mesure + tâches `game.design.*`), `docs/kafka.md` (topics de génération), `godot/README.md` (jetons, caméra, mesure GPU), `docs/blocages.md` (mémoire partagée des agents, décisions par défaut des ADR 0008/0009).

## Règles de coût
Une mission = un livrable · lecture par plages · au plus une capture par type d'écran · comptes rendus ≤ 15 lignes · effort adaptatif (champ `effort` des frontmatters) · agent neuf plutôt que reprise après plus de 60 tours · ne pas relancer `stop.ps1` ni `docker compose down`.

## Alertes pour l'utilisateur
- `~/.claude/settings.json` contient des secrets Supabase en clair dans ses règles allow : à déplacer.
- Une clé OpenAI a été collée dans le chat : à révoquer.
