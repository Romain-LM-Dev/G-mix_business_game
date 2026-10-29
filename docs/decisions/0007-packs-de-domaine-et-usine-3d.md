# 0007 : packs de domaine et monde « usine 3D » (sous-simulation journalière rejouée en 3D)

Date : 2026-10-28. Statut : accepté le 2026-10-28 (décisions de l'utilisateur en fin de document ; points 11 et 12
ajoutés à l'acceptation).
Complète l'ADR 0006 (génération par paramètres, moteur pur) sans le remplacer. Contrat précis et plan
d'exécution : `0007-annexe-contrat-usine.md`.

## Contexte

L'utilisateur décrit une usine minimale « valable pour tout produit » (docs/references/usine-3d/) : 10 départements,
N lignes identiques (1 à 3) de machines en série avec tables d'attente, pannes (MTBF, MTTR), goulot, ressources
partagées (quai, chariot, technicien, chef de ligne), agents à états, horloge de 8 h par jour accélérable. Le
moteur actuel (ADR 0006) raisonne par semaine et par ligne agrégée (capacité x TRS). Le jeu doit rester un
générateur général : chaque domaine apporte ses lieux, agents, éléments, paramètres, actions, assets et panneaux.
Contraintes : reproductible, sans IA, testable, léger (RTX 3060 6 Go, 16 Go), règles dans `gmix.game.engine`
(fonctions pures, appelées par l'API sous verrou de ligne), Kafka hors temps réel, exigence n° 1 (vrai et sourcé).

## Décision

1. **Tour de décision inchangé, dynamique d'usine calculée dedans** (confirmé par l'utilisateur). Les joueurs
   décident par tour (une semaine de 5 jours de 8 h rejouée jour par jour, `clock.days_per_turn` réglable de 1 à 5),
   sans action en direct pendant la journée. `engine.advance` joue le tour par une simulation à
   événements discrets (module pur `gmix.game.factory`, `heapq` de la bibliothèque standard), en minutes simulées :
   machines en série, tables d'attente (pleine : l'amont s'arrête ; vide : l'aval attend), pauses planifiées,
   réglages au changement de lot, usure d'outil, pannes, réparations par le technicien (une à la fois), réception,
   kits, contrôle, emballage, entrepôt PF, commandes client datées. Hasard : un flux par source (machine, demande,
   fournisseur) dérivé de la graine par une chaîne stable, donc mêmes pannes et même demande pour deux équipes
   qui jouent la même spec. Les « actions » des agents du cahier sont des comportements simulés ; les joueurs
   fixent des décisions et des règles (lancer un OF, commander la MP, préventif, priorité de réparation,
   protéger le goulot).
2. **Le rejeu 3D est la vérité calculée, pas une animation libre.** `advance` produit une chronologie compacte
   (instantanés toutes les 5 min simulées et événements datés). L'API la retire de l'état, la range en base
   (`lobby_timelines`) et la sert par `GET /api/v1/lobbies/{id}/weeks/{week}/timeline`. Godot la rejoue
   localement, chacun à sa vitesse : pause, x1, x60, x240, x960, événement suivant, choix du jour. Rien du rejeu ne
   passe par Kafka ni par le serveur de partie ; `lobby.state` ne transporte jamais la chronologie.
3. **Pannes par usure.** Durée de marche avant panne selon une loi de Weibull de forme > 1 dont la moyenne est le
   MTBF ; le préventif remet l'âge à zéro. Avec une loi exponentielle (sans mémoire), le préventif n'aurait aucun
   effet : le jeu enseignerait faux.
4. **Pack de domaine déclaratif** : `ai/packs/<id>.yaml` (propriétaire game-designer), qui porte le domaine
   (`ai/domains.yaml`), le modèle de moteur (`engine: weekly | factory`), les options du formateur, les
   départements (zone au sol, éléments liés aux assets, postes, agent), les figurants, les modules, rôles et
   actions, les valeurs par défaut avec leur provenance, les notions et formules sourcées, les aléas, les
   panneaux d'interface. Le pack `atelier` reste `ai/simulation.yaml` (lu tel quel). La spec gagne des champs
   facultatifs (`departments`, `factory`, `panels`, `provenance`, `meta.domain`, `meta.pack`) : toute spec v2
   existante reste valide. Les formules sont du code testé, jamais évaluées depuis le YAML.
5. **Généralité honnête** : un nouveau domaine qui réutilise un modèle existant ne demande que du YAML et des
   assets. Une nouvelle mécanique (finance, projet…) demande un nouveau modèle pur et testé dans
   `gmix.game.engine`, choisi par `engine:` ; départements, agents, panneaux, actions et assets restent déclaratifs.
6. **Interface modulable** : 5 types de panneaux génériques (`kpis`, `table`, `gauge`, `chart`, `flow`) liés par
   un chemin à l'état public, placés dans le bandeau, le tableau de bord ou un poste. Les formulaires d'action
   restent ceux des modules. Sans panneau déclaré, le HUD actuel s'affiche (pack `atelier` inchangé). Autoloads
   Api, Realtime, Presence et Session inchangés.
7. **Agents** : un agent parlant par département du cahier (10), avec un rôle et une fonction de faits
   (`agent.facts`) ; opérateurs et chauffeurs sont des figurants sans dialogue. États (disponible, occupé, en
   déplacement, en pause, absent) calculés par le moteur, visibles dans l'état public, le rejeu et les faits.
   Le dialogue (`npc.dialogue`) ne dit que ces faits.
8. **Provenance de chaque paramètre** : `source` (citation obligatoire), `calibre` (choisi pour la jouabilité,
   note obligatoire), `exemple` (valeur du cahier, non sourcée). La relecture et le débrief affichent les valeurs
   non sourcées. Les valeurs du cahier entrent en `exemple`.
9. **Plan en U, quai unique partagé** (le texte du cahier fait foi sur la carte ; validé par l'utilisateur) :
   réception et entrepôt PF de part et d'autre de la porte de quai, flux réception -> stock MP -> lignes ->
   contrôle -> emballage -> PF.
10. **Phasage** : tranche 1 (verticale) puis extensions (annexe, section 6).
11. **Goulot dans les lignes, postes hors lignes dimensionnés** (choix de l'utilisateur). Le goulot de chaque ligne
    est une de ses machines (M3 dans l'exemple du cahier). Contrôle et emballage ont une capacité d'au moins
    1,2 fois le débit théorique de l'usine à 3 lignes ; réception, kits, chariot et quai ne doivent pas freiner
    non plus. Le débit de l'usine est alors la somme des débits des lignes (en régime établi, tant que la MP et la
    place en entrepôt PF, qui dépendent des décisions des joueurs, ne manquent pas). Le cahier ne le permet pas
    (emballage : 17 min par palette de 6, soit 21 produits / h pour 53 / h sortis des lignes) : le pack corrige
    (annexe §5), critère 3 de la tranche 1.
12. **Mémoire des agents partagée entre les joueurs du lobby** (choix de l'utilisateur, contre la recommandation de
    limiter l'historique au joueur courant) : règle actuelle de `gmix.game.npc` (`npc_memories`), étendue aux
    agents de l'usine. **Risque accepté** : injection persistante (un joueur dépose une consigne rejouée aux autres).
    Mesure du 2026-10-28 : la chaîne pré-filtre lexical + tev1:0.8b détecte 4 injections variées sur 9 ; tev1:4b
    les détecte toutes mais bloque la moitié des messages légitimes à mots piégés. Atténuations déjà en place :
    pré-filtre lexical `looks_like_injection` avant tout modèle, tours douteux (injection, hors-sujet) jamais
    mémorisés ni rejoués (`should_remember`), réponse sobre en personnage, sans génération. Pas
    de travail de code ajouté par cet ADR ; risque à reprendre dans docs/blocages.md (annexe, étape 12).

Rejeté : simulation en temps réel continu sur le serveur de partie (non reproductible, contraire à « règles =
moteur pur sous verrou », lourd) ; formules fermées par semaine avec une animation décorative (la 3D montrerait
des pannes et des attentes qui n'ont pas eu lieu) ; formules écrites dans le YAML et évaluées (ni sûr ni testé).

## Conséquences

- Nouveau module `gmix.game.factory` et ses tests ; `engine` choisit le modèle selon `spec.factory`.
- Migration `lobby_timelines` et une route en lecture ; pas de topic Kafka ni de worker (`topics.py` inchangé).
- `ModuleId`, `StationKind`, `ActionField.source` et (29/10) `ExtraAgentId` s'ouvrent (vérifiés contre le
  pack ; formats des limites, des postes et de la chronologie fixés dans l'annexe le 29/10) ; `World.template` gagne
  `usine` ; `Clock.breaks` (pauses du personnel, facultatif) ajouté à l'acceptation ; Godot lit `spec.world.size`
  (fin de la constante de hall 32 x 24).
- Onze assets à fabriquer en tranche 1 (quatorze en tout), sous licence CC0 ou propriété du projet ; `prop_production_line` (jeu de référence
  sans licence) n'est pas réutilisé pour les machines.
- Corpus complété le 2026-10-28 (18 fiches, knowledge/supply-chain/SOURCES.md) : MTBF et MTTR, disponibilité,
  maintenance, théorie des contraintes, loi de Little, formule de Kingman, TRS, rendement cumulé, carte p. Sans
  fiche : loi de Weibull (forme en `calibre`) et temps de lot (`exemple`).
- Budgets : `POST /games` < 1 s (pilote automatique compris, 3 lignes x 4 machines, 12 tours), `advance` < 150 ms,
  état public < 64 Ko, chronologie < 200 Ko par tour, 45 images/s en vue usine avec le modèle 3b chargé.

## Ce qui reste ouvert

- Horloge de rejeu commune pilotée par le formateur (projection en salle) : tranche 3, via le serveur de partie.
- Migration du pack `atelier` au format pack, avec panneaux ; second domaine pour éprouver la généralité.
- Vidéo Instagram toujours non consultée ; les défauts sont retenus (pas d'action en direct, quai partagé). Reste
  à savoir si elle montre chaque produit sur un convoyeur ou des stocks agrégés (coût en assets et en images/s),
  et quel style de caméra et d'interface (carte isométrique et fiches comme les images ?).
- Risque accepté de la mémoire partagée (point 12) : à inscrire dans docs/blocages.md ; à revoir si un filtre
  plus sûr sans fausses alertes devient disponible.
- Garde-fou des nombres dans les répliques des agents (docs/blocages.md) : plus de chiffres et d'unités dans
  les faits (min, h, OF), donc plus de risque d'invention par le modèle 3b.

## Décisions de l'utilisateur (2026-10-28)

1. Cadence : un tour = une semaine rejouée jour par jour (défaut confirmé ; `days_per_turn` permet de changer sans
   refonte).
2. Quai : un quai partagé et un plan en U (défaut validé).
3. Pas d'action en direct pendant la journée : rejeu de décisions par tour (défaut validé, vidéo non consultée).
4. Goulot : dans les lignes (M3), postes hors lignes dimensionnés (point 11), au lieu du défaut proposé (goulot
   hérité du cahier, à l'emballage).
5. Mémoire des agents : partagée entre les joueurs (point 12), risque d'injection persistante accepté.
