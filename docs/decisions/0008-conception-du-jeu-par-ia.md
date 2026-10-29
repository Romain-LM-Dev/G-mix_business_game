# 0008 : conception du business game par l'IA, sur un moteur déterministe

Date : 2026-10-29. Statut : proposé (trois questions à l'utilisateur en fin de document).
Amende l'ADR 0006 : l'IA redevient la couche de conception ; la génération par paramètres reste et sert de repli.
Complète l'ADR 0007 (packs, usine, panneaux). Contrat précis et plan d'exécution : `0008-annexe-contrat-conception.md`.

## Contexte

- Demande de l'utilisateur (28 et 29/10) : « génération du business game de façon intelligente avec l'IA […] l'interface
  joueur doit être modulable et lisible ». Le projet est un générateur général : domaine sélectionnable, éléments,
  assets et outils propres au domaine, supply chain en priorité.
- Ancien pipeline (commit 5a5d288) : `game.brief_check` (tev1) puis plan, PNJ, détail de chaque phase, assets et débrief
  par qwen2.5:7b, contrôles déterministes, `game.coherence_review` (tev1:4b, une question par effet). Il durait 7 à 9 min
  et occupait le GPU. Le modèle écrivait les effets et les montants : sens inversés, montants inventés, KPI mal choisis ;
  une revue globale ne détectait rien ; le 3b tronquait son JSON quand aucun plafond n'était imposé au décodage.
  **À garder** : un job asynchrone par Kafka avec sa progression relayée au formateur ; les sorties JSON contraintes
  par un schéma dont les énumérations sont construites à l'exécution (un asset ne pouvait pas être inventé) ; les
  contrôles déterministes avant toute revue par l'IA ; une réparation ciblée en deux essais ; le cache exact ; la règle
  « le modèle choisit un sens et une ampleur, le code calcule le montant ».
- ADR 0006 : les jeux sont justes et jouables, mais le formateur coche des paramètres et l'IA ne conçoit plus rien.
- Poste : 6 Go de VRAM. Le 7b tourne à 21,5 tok/s et met 7 à 27 s à charger ; tev1 le fait sortir de la VRAM. Le 3b
  suffit au dialogue mais invente parfois des nombres.

## Décision

1. **L'IA conçoit, le moteur calcule.** Le formateur donne un brief libre (20 à 2000 caractères), le public visé et,
   s'il le veut, des contraintes : il impose lui-même certains champs de `GameParams`. Avec des **énumérations construites
   depuis le pack**, l'IA choisit le secteur, les modules (donc les rôles et les outils), les agents en plus, le
   caractère des agents, le profil de difficulté, la durée, le nombre de produits, les options du pack, le niveau d'aléas
   et un **plan d'aléas** (3 semaines imposées au plus). Elle choisit aussi les **réglages** : pour chaque clé de profil
   que le pack déclare réglable, le profil qui fournit sa valeur (découverte, équilibré ou expert). Toutes les valeurs
   sont donc déjà calibrées dans le pack et ont une provenance ; l'IA n'en écrit aucune.
   Elle écrit les textes : titre, accroche, contexte, objectifs pédagogiques (verbe observable, notion du pack,
   indicateur du débrief, modules), personnages (nom, caractère du pack, présentation), didacticiel et questions de
   débrief. Elle compose aussi l'interface : panneaux et outils du pack, dans l'ordre de son choix. Elle prend toujours
   un élément d'un catalogue existant ; elle n'invente jamais :
   - **un nombre** : aucun chiffre dans un texte, aucune valeur hors des énumérations et des bornes ;
   - **une règle ou un effet** : le moteur `gmix.game.engine` les calcule et reste le seul juge des résultats ;
   - **une notion hors du pack** : elles ont toutes une citation, donc tout ce qui est transmis est sourcé ;
   - **un asset hors du catalogue** ;
   - **une réplique d'agent hors des faits du moteur** : `npc.dialogue` est inchangé, et la présentation d'un
     personnage ne va pas dans son prompt.
2. **Garanties de justesse et de jouabilité**, dans cet ordre :
   - décodage contraint : schéma JSON, énumérations, bornes, longueurs, nombre d'éléments, texte sans chiffre ;
   - validation par `GameParams` et `SimSpec`, avec des messages en français ;
   - contrôle de cohérence sans modèle : une notion d'objectif appartient à un module retenu, l'indicateur est permis
     par la notion, un aléa planifié touche un module joué, une ancre du didacticiel existe ;
   - partie d'essai en pilote automatique : en découverte, le pilote atteint les objectifs ; en expert, il en manque au
     moins un. Un jeu trop difficile est **réparé sans modèle** : les réglages se relâchent cran par cran vers
     découverte, puis le plan d'aléas disparaît ;
   - réparation par le modèle, deux essais au plus par section, avec la liste des erreurs ;
   - repli par section : le concept se replie sur la génération par paramètres actuelle, les personnages et le
     parcours sur les défauts du pack. Le formateur reçoit toujours un jeu jouable ;
   - `spec.design.origin` garde le modèle, les versions des prompts, la graine, les empreintes du brief et du pack, la
     durée, les tokens, les réparations et les avertissements ;
   - un jeu conçu par l'IA reste en brouillon (`draft`). Le formateur le relit, régénère une section, modifie, puis
     **publie** ; un lobby ne se crée que sur un jeu publié.
3. **Généralité, par étapes.** (A) **Tranche 1** : l'IA conçoit et règle des jeux dans les moteurs existants (atelier
   hebdomadaire, usine). Une demande que le pack ne couvre pas est listée dans `design.unmet`, sans être simulée.
   (B) Une bibliothèque de primitives pures et testées (stocks et flux, files, ressources qui tombent en panne,
   demande et prix, effectifs, trésorerie, qualité), extraites des deux moteurs quand un second domaine choisi par
   l'utilisateur en a besoin. Pas de factorisation par anticipation. (C) Un nouveau domaine dont l'IA rédige le
   brouillon de pack (primitives, valeurs `a_sourcer`, notions tirées du corpus) : il n'est jamais jouable avant la
   relecture par game-designer.
4. **Pipeline.** `POST /games/designs` répond 202 et publie `generation.requested` sur `gmix.generation.commands`.
   Le worker `generation` traite un job à la fois avec un seul modèle chargé, en trois sections et trois appels :
   `concept` (scénario, mécaniques, objectifs), `cast` (personnages), `journey` (interface, didacticiel, débrief).
   Chaque appel appartient à une tâche de ai/models.yaml (`game.design.*`) et sa sortie est contrainte par le format
   d'Ollama. Il n'y a ni RAG, ni embeddings, ni tev1 dans la tranche 1 : les notions du pack tiennent dans le prompt.
   Avec la graine et `cache: true`, une relance ou une reprise retrouve les appels déjà faits dans le cache. La
   progression passe par `gmix.generation.events` puis par le WebSocket du seul demandeur ; une interrogation
   périodique sert de secours. Budget : 3 min en médiane, 5 min au 90e centile, 10 min au plus, puis repli.
5. **Interface modulable et lisible.** Le pack déclare un catalogue de panneaux (5 types, ADR 0007) et d'outils (barre
   d'actions). L'IA en choisit une partie et l'ordonne ; le formateur réordonne ou masque dans l'aperçu ; le joueur
   règle sa disposition sur son poste. Le validateur impose des **limites de lisibilité** (`UI_LIMITS` : nombre de
   panneaux par emplacement, colonnes, longueur des libellés, 6 outils, 5 étapes) et Godot prouve à 4 tailles
   de fenêtre, sur une spec qui atteint toutes les limites, qu'aucun texte ne déborde et qu'aucune police n'est sous
   15 px. Le thème est un **jeu de jetons** (`meta.ui_theme` -> couleurs, espacements, polices) que le pack ou le
   formateur peut changer. La DA du jeu de référence vient dans un autre chantier (godot-dev, assets-3d).
   Le jeu de référence fournit ces motifs :

   | Motif du jeu de référence | Dans G-mix | Tranche |
   |---|---|---|
   | Pastilles KPI colorées par seuil | panneau `kpis` au bandeau, couleur selon `target`, `better` et `warn` | 1 |
   | Barre d'actions numérotée | `spec.tools` (6 au plus, touches 1 à 6), déclarés par le pack, choisis par l'IA | 1 |
   | Modales commande et ordre de fabrication | formulaires d'action des modules (déjà là), ouverts par un outil | 1 |
   | Didacticiel en 5 étapes | `spec.tutorial` (5 étapes ancrées au plus), écrit par l'IA, défaut du pack | 1 |
   | Préparation de partie | écran « Concevoir avec l'IA » et aperçu du formateur | 1 |
   | Inspecteur d'un objet ou d'un agent | emplacement `inspecteur` (objet sélectionné) | 2 |
   | Parcours d'usine en onglets | onglets dans l'ordre de `spec.departments`, qui recadrent la caméra | 2 |
   | Dialogue à questions proposées | 2 questions suggérées par agent, écrites par l'IA | 2 |
   | Textes de 7 à 11 px | non repris : 15 px au moins en 1280x720 | - |
6. **Évaluation.** `ai/evals/game.design.jsonl` contient 24 briefs : 12 de réglage et 12 de contrôle, chacun avec ses
   attentes vérifiables sans modèle. `gmix.tools.eval_design` lance le vrai pipeline et mesure les specs valides au
   premier essai et après réparation, les replis, la jouabilité, la fidélité au brief, les chiffres tentés, les notions
   sourcées, la durée et les tokens. On retient le plus petit modèle qui passe les critères de l'annexe (§8),
   et de préférence celui du dialogue, qui ne déloge alors aucun autre modèle de la VRAM.
7. **Rapport aux ADR 0006 et 0007.** Le moteur déterministe, les packs, `factory.py`, la route de la chronologie, le
   monde 3D, les assets et le pack usine restent valables tels quels : ce sont les cibles de la conception. Il faut
   ajuster quatre points : les packs gagnent `tunables`, `tools`, `tutorial` et `notions.*.indicators` ;
   `spec.panels` devient une sélection ordonnée du catalogue du pack (sans conception, tout le catalogue dans l'ordre
   du pack, comme aujourd'hui) ; `generate` applique les réglages et le plan d'aléas ; le rendu des panneaux de
   l'étape 8 de 0007 respecte l'ordre, les pastilles et les préférences du joueur.

Rejeté :
- un modèle qui écrit les chiffres et les effets : c'est l'échec mesuré de l'ancien pipeline ;
- un pack YAML écrit par l'IA et jouable sans relecture : contraire à l'exigence n° 1 ;
- une génération synchrone dans l'API : plusieurs minutes de requête HTTP, et le GPU disputé ;
- `game.brief_check` par tev1:0.8b, trop faible comme filtre (mesure du 28/10) : un brief n'agit que sur le jeu de son
  auteur, sa sortie est contrainte, et le formateur relit avant de publier ;
- une relecture des textes par l'IA en tranche 1 : on mesure d'abord, par l'éval et la relecture de game-designer, puis
  on ajoute une question fermée par texte (tev1:4b) si des affirmations fausses apparaissent.

## Conséquences

- Nouveaux éléments : le module pur `gmix.game.design` ; le worker `generation` ; deux topics ; cinq routes ; une colonne
  `generation_jobs.request` ; des champs facultatifs dans la spec. Une spec v2 existante reste valide.
- La génération par paramètres (`POST /games`, instantanée, publiée d'emblée) reste disponible et sert de repli.
- Avec le 7b, une conception déloge le modèle de dialogue de la VRAM : risque en séance (question 2).
- Dépendances : l'étape 6 de 0007 (génération usine) pour les conceptions sur le pack usine ; l'étape 8 de 0007
  (`panels.gd`) pour le HUD. Le même agent enchaîne sur les mêmes fichiers.

## Questions à l'utilisateur

1. Installer `qwen3.5:4b` (environ 3,3 Go) pour la mesure comparative ? **Recommandation : oui.** S'il passe les
   critères du dialogue et de la conception, il sert aux deux et rien n'est délogé de la VRAM.
2. Si le modèle retenu n'est pas celui du dialogue, faut-il refuser une conception (409) tant qu'un lobby est en
   cours ? **Recommandation : oui.** La génération par paramètres reste disponible pendant la séance.
3. Panneaux de l'atelier dès la tranche 1, ce qui remplacerait son HUD et avancerait la tranche 4 de 0007 ?
   **Recommandation : non.** En tranche 1, l'atelier reçoit les outils, le didacticiel et le débrief conçus ; les
   panneaux conçus par l'IA ne concernent que l'usine.
