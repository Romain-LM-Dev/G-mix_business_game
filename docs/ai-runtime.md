# Agents IA du jeu (Ollama)

## Principe

Le code demande une **tâche** (`npc.dialogue`, `game.outline`…) ; `ai/models.yaml` décide du modèle, des
options, du budget de tokens, du RAG, du cache et du modèle de repli. `gmix.llm.service.LLMService` applique :
contrôle du budget avant l'appel, contexte fixe par modèle, sortie JSON contrainte puis validée, journal des
tokens consommés (logger `gmix.llm`).

## Niveaux de modèles (poste actuel : RTX 3060 Laptop 6 Go)

| Alias | Modèle | Usage | Contexte |
|---|---|---|---|
| decide-fast | tev1:0.8b (optionnel) | routage, pré-filtrage, questions fermées | ~2 000 tokens utiles |
| decide | tev1:4b (optionnel) | revue qualité notée (score) | ~2 000 tokens utiles |
| nano | qwen2.5:1.5b | répliques courtes, reformulation, repli de decide-fast | 4096 |
| small | qwen2.5:3b | dialogues PNJ, détail d'une phase, choix d'assets | 6144 |
| main | qwen2.5:7b | plan du jeu, débrief, repli de decide | 8192 |
| embed | embeddinggemma (768 dim.) | RAG et assets | 2048 |

Mesures sur ce poste (modèles chauds) : réponse `nano` de 8 tokens en ~0,1 s, embedding ~35 ms, question
fermée émulée par `nano` en 0,1 à 0,3 s, aller-retour complet Godot -> Kafka -> worker -> Godot en ~0,4 s.
Un changement de `num_ctx` sur un même modèle forçait un rechargement (~7 s par appel) : d'où le contexte
fixé par modèle.

Candidats à évaluer avant d'en changer : `qwen3.5:4b` pour `small` (3,3 à 4 Go), `qwen3.5:9b` pour `main`
(6,6 Go : déborde sur le CPU, plus lent mais acceptable en génération asynchrone).

## tev1 et Jev (modèles de décision)

tev1 (Together AI, affiné depuis Qwen3.5, 0,8B et 4B) répond à des questions fermées sans générer de texte :
`choice` (choix parmi des options + probabilités), `noul` (probabilité que ce soit vrai), `score` (niveau
sur une grille). Jusqu'à 64 questions par appel, endpoint Ollama `/v1/systemone` au format de l'API Jev
(TypeSafe AI, hébergée) : on pourra basculer vers Jev plus tard sans changer le code appelant.
Limites annoncées : contexte effectif ~2 000 tokens, **non évalué en français**, ne doit pas être le seul
contrôle d'une décision à fort enjeu. Exige Ollama >= 0.40.4.

Si tev1 est absent, `LLMService.decide()` émule la réponse avec le modèle de repli (JSON contraint par un
`enum`), au même format (`"emulated": true`).

Mesure du 2026-10-15 sur 34 messages de joueurs en français dont 6 tentatives d'injection
(`python -m gmix.tools.eval_decision player.intent`, modèles chargés) :

| Modèle | Intention | Injections (seuil 0,7) | Fausses alertes | Latence |
|---|---|---|---|---|
| tev1:0.8b | 93 % | 5/6 | 2/28 | ~0,1 s |
| tev1:4b | 100 % | 6/6 | 5/28 | ~0,9 s |
| qwen2.5:3b (émulation) | 68 à 75 % | 3 à 4/6 | 0/28 | ~0,5 s |
| qwen2.5:1.5b (émulation) | 68 % | 0/6 | 0/28 | ~0,2 s |

Enseignements :
- des critères explicites (formulations typiques) font passer tev1:0.8b de 64 % à 93 % : soigner les questions ;
- les probabilités `noul` de tev1 sont mal calibrées (tassées entre 0,7 et 0,8) : seuil 0,7 pour l'injection,
  et jamais comme seule protection. La vraie protection est structurelle : les solutions des décisions ne sont
  jamais dans le contexte d'un PNJ ;
- sur 6 Go de VRAM, tev1:0.8b (0,8 Go) cohabite avec le modèle de dialogue : il sert le temps réel ;
  tev1:4b (4,6 Go) forcerait des rechargements : réservé aux tâches hors temps réel (revue, notation).

## Pipeline de génération d'un business game

Code : `gmix/game/generation.py` (étapes, réparations), `gmix/workers/generation.py` (Kafka, progression).

| # | Étape | Tâche / outil | Budget entrée / sortie | Garde-fou |
|---|---|---|---|---|
| 0 | Demande exploitable et dans le domaine ? | `game.brief_check` (décision) | état court / 0 texte | refus motivé au formateur avant toute dépense (seuils permissifs, non mesurés) |
| 1 | Plan (objectifs, entreprise, rôles, KPI, phases) | RAG top-6 puis `game.outline` (main) | ≤ 4 000 / ≤ 2 048 | schéma `outline` resserré ; réparations : demande du formateur, formules, durées, `assessed_by` |
| 2 | PNJ experts | `game.npcs` (main) | ≤ 2 800 / ≤ 1 024 | `zone` en enum des zones du gabarit |
| 3 | Détail de chaque phase (décisions, effets, aléas) | RAG ciblé puis `game.phase_detail` (main) | ≤ 4 200 / ≤ 1 536 par phase | rôles sans décision, KPI de base, PNJ et sources en enum ; effet = sens + ampleur, montant calculé par le code ; énoncé répété : second essai |
| 4 | Assets par zone | `candidate_assets` (pgvector, k=8) + choix sûrs du gabarit, puis `game.asset_mapping` | ≤ 3 200 / ≤ 600 | `enum` des ids candidats, cache ; repli sur le gabarit |
| 5 | Débrief | `game.debrief` (main) | ≤ 3 500 / ≤ 1 024 | schéma `debrief` resserré |
| 6 | Assemblage et contrôles | schéma complet + `gmix.game.coherence` | 0 token | ids uniques, aléas orphelins retirés, avertissements dans `review` |
| 7 | Sens des effets | `game.coherence_review` (tev1:4b, une question fermée par effet) | option + explication | effet contredit par l'explication : inversé, réparation listée |
| 8 | Correction ciblée | 2 essais par étape JSON | idem étape | échec motivé au formateur |

Mesures du 2026-10-22 qui ont fixé ces choix. qwen2.5:7b inversait souvent le signe des effets (« add -2 »
sur un KPI où « plus bas = mieux ») et en inventait les montants : il choisit désormais un sens (hausse ou
baisse de la valeur) et une ampleur (faible, moyenne, forte = 15, 30 ou 50 % de l'écart entre valeur initiale
et cible), le code calcule le montant, puis tev1 vérifie chaque sens contre l'explication que liront les
joueurs. Une revue globale par décision (« les effets suivent-ils l'explication ? ») ne détectait rien.
Les plafonds (`maxItems`) sont imposés au décodage, pas seulement demandés au prompt : sans eux, qwen2.5:3b
dépassait `num_predict` et rendait un JSON tronqué. Toutes les étapes génératives sont sur `main`
(qwen2.5:7b) : le 3b produisait des options vagues et répétées, n'était pas plus rapide sur ce poste et
chaque bascule de modèle coûtait 17 à 32 s. Les sources de la spec sont dédupliquées par document et citent
la révision exacte de la fiche (ligne « > Source : » du corpus).

Présélection d'assets (étape 5), mesurée sur 12 besoins étiquetés (`python -m gmix.tools.assets evaluate`) :
rappel 11/12 dans les 4 premiers candidats, 12/12 dans les 8 premiers, sans aucun token de génération.

## Où tourne l'IA

Aujourd'hui sur le poste de développement. Pour la déplacer sur un serveur GPU : `OLLAMA_BASE_URL` pointe vers
ce serveur et `OLLAMA_API_KEY` fournit le jeton exigé par le reverse proxy placé devant Ollama (Ollama n'a pas
d'authentification propre : ne jamais l'exposer directement). Avec plus de VRAM, passer `player.intent` sur
`decide` (tev1:4b) et `small` sur un modèle plus grand ne demande que de modifier ai/models.yaml.

## Agents en jeu

- `player.intent` filtre chaque message (hors-sujet, injection) avant tout appel génératif : réponse fixe,
  aucun token généré (`gmix.game.npc`, `POST /lobbies/{id}/npcs/{npc}/talk`).
- Recherche bornée au domaine sur le message du joueur ; `rag.query_rewrite` (rendre la question autonome
  après plusieurs échanges) n'est pas encore branché.
- `npc.dialogue` : 2 à 4 phrases, faits limités aux extraits [S…] renvoyés au client avec la réponse,
  périmètre d'expertise du PNJ, 6 derniers échanges en historique. Réponse complète en v1 (pas de streaming).
- `npc.bark` : phrases d'ambiance sans RAG (à pré-générer au chargement du lobby plutôt qu'à la volée).
- `answer.grading` et `debrief.feedback` en fin de partie.

## Leviers d'économie

En place : routage par tâche, budgets vérifiés avant l'appel, contexte fixe par modèle, décodage contraint,
décisions sans génération de texte, cache exact (table `llm_cache`), `think` désactivé par défaut, contrôles
déterministes avant toute revue par IA. À faire : résumé de l'historique des dialogues au-delà de 6 échanges,
pré-génération des répliques d'ambiance, comptage des tokens par étape dans `generation_jobs.usage`.

## Réglages Ollama recommandés (6 Go de VRAM)

`.\scripts\models.ps1 -Tune` définit `OLLAMA_FLASH_ATTENTION=1` et `OLLAMA_KV_CACHE_TYPE=q8_0` (cache KV
environ divisé par deux), à appliquer en relançant Ollama. Garder Godot fermé pendant une génération
avec `main` : le jeu consomme aussi de la VRAM.
