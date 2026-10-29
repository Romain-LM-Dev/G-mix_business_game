# Points bloquants et décisions en attente

Mis à jour le 2026-10-23 (points ouverts de la séance du 22 au 23/10). À tenir à jour par l'architecte.

## Décisions prises

| Sujet | Décision | Trace |
|---|---|---|
| Statut du projet | Indépendant de tout établissement : aucune ressource d'école (cours, serveur, SSO) n'est supposée | CLAUDE.md |
| Domaine prioritaire | Supply chain et logistique (premier du menu formateur) | ai/domains.yaml, knowledge/supply-chain/ |
| Authentification | Comptes créés dans l'application (identifiant + mot de passe), scrypt, jeton de 8 h | docs/decisions/0004 |
| Mode de jeu | En réseau local et à distance ; un serveur Godot par lobby pour la présence | docs/decisions/0005 |
| Hébergement de l'IA | Sur le poste de développement pour l'instant ; déplaçable sans changer le code | docs/ai-runtime.md |
| Business games | Simulés et générés par paramètres, sans modèle ; agents PNJ à mémoire | docs/decisions/0006 |
| Modèles | Dialogue des agents sur qwen2.5:3b ; tev1:0.8b pour filtrer les messages des joueurs | ai/models.yaml |
| Stockage objet | RustFS (MinIO archivé) | docs/decisions/0001 |
| Règles de partie | Appliquées par l'API (moteur pur, verrou de ligne), pas par un worker | docs/architecture.md |

## Fait

- Environnement : Ollama 0.40.4, tev1 mesuré, 61 assets 3D (52 importés, 9 procéduraux), corpus supply chain
  (30 articles, 273 passages).
- 2026-10-22 : comptes et rôles ; génération complète par l'IA (worker `generation`) ; moteur de partie ;
  lobbies avec code d'accès ; PNJ (filtre tev1, RAG, dialogue) ; client Godot (connexion, menus formateur et
  joueur, salle du lobby, monde 3D construit depuis le gabarit `parc_activites`, HUD décisions / KPI /
  dialogue / débrief) ; présence multijoueur ENet avec ticket signé.
- 2026-10-22 (suite) : business games simulés par paramètres (ADR 0006) inspirés du jeu de référence
  eloiseferrante27-alt/Business_game : 4 secteurs, 7 modules, agents PNJ à caractère et à mémoire, atelier 3D
  animé par l'état de la partie. Génération instantanée ; l'ancien pipeline par LLM est retiré.
- 2026-10-23 : vue Sims par défaut (clic pour marcher sur un maillage de navigation cuit à l'exécution, menu
  contextuel, caméra libre ou suivie) ; interface en fenêtre de référence 1280x720 avec thème commun ; contrôles
  `godot.ps1 -Tour` (interface) et `-Flow` (parcours formateur) avec comptes jetables ; évaluation des dialogues avec le
  vrai modèle (`gmix.tools.eval_dialogue`, 121 cas, rapports dans ai/evals/results/) : qwen2.5:3b retenu, filtre
  `player.intent` en version 3 (seuil 0,6). Mesures : docs/ai-runtime.md.

## Bloquants restants

1. **Droits sur le jeu de référence.** Le dépôt eloiseferrante27-alt/Business_game n'a pas de licence. Ses
   données (fournisseurs, produits, prénoms, aléas, profils de difficulté) et deux éléments 3D portés en
   GDScript (machine de ligne, bureau d'atelier) sont repris : obtenir l'accord écrit de son autrice avant
   toute diffusion, sinon les remplacer.
2. **Calibrage des simulations.** Ordres de grandeur (coûts, délais, fiabilités, élasticité prix) choisis pour
   être plausibles et jouables, pas tirés d'un secteur réel ; le TRS cite une norme hors corpus (AFNOR NF
   E60-182). À faire relire par le game-designer avec des données sectorielles sourcées.
3. **Corpus supply chain encore provisoire.** Wikipédia donne définitions et formules, pas les ordres de
   grandeur réalistes (coûts de possession, délais, taux de service par secteur). Il faut des supports de
   formation fournis avec leur accord et des études de cas chiffrées publiques, déclarés dans SOURCES.md.
   Les 14 autres domaines n'ont aucun corpus : leurs jeux sont signalés « non sourcés ».
4. **Capacité IA pour une séance réelle.** Les dialogues des agents passent un par un sur le GPU : la RTX 3060
   (6 Go) suffit au développement, pas à une vingtaine de joueurs qui parlent en même temps.
5. **Hébergement à distance à choisir** (serveur avec GPU, nom de domaine, HTTPS, ports UDP ou WebSocket pour
   les serveurs de partie) quand les parties à distance seront testées. Avant cela : jeton de
   rafraîchissement (ADR 0004).

## Points ouverts du 2026-10-23

| Point | Détail | À prévenir |
|---|---|---|
| Parcours B (joueurs) et V de `flow_test` non écrits | Seul le parcours A (formateur) existe ; `--only=A,B,V` annonce les trois. Le comportement d'un joueur (rejoindre, rôle, décisions, dialogue) n'est pas couvert par un parcours scripté. | godot-dev |
| Vue Sims éprouvée seulement par événements simulés | Clic réel à la souris, clavier AZERTY réel, ressenti de la caméra : non éprouvés. Pavé tactile : non géré. À essayer à la main avant une séance. | godot-dev, utilisateur |
| Cinq assets sans collision propre | `prop_kpi_screen`, `prop_desk_computer`, `prop_meeting_table`, `prop_pallet`, `prop_pallet_stack` : `world.gd` leur ajoute une emprise de secours (couche 16). Une collision propre à l'asset la remplacerait. | assets-3d |
| Agents PNJ en ligne droite | Ils patrouillent en ligne droite entre les points de leur route (`spec.agents[].route`), sans maillage de navigation ni évitement d'obstacle. | godot-dev |
| Garde-fou de `gmix/game/npc.py` non écrit | Filtre lexical d'injection avant l'appel au modèle, détection d'un nombre absent des faits dans la réplique. Motifs : tev1:0.8b manque 5 injections sur 8 (série F), dont « Ignore tes instructions précédentes… », et le 3b invente 1 à 3 nombres sur 59 répliques. **En attente de décision de l'utilisateur.** | utilisateur, moteur-jeu, ia-runtime |
| `qwen3.5:4b` non mesuré | Candidat pour `small` (environ 3,3 Go), non installé au 2026-10-23. Le 3b reste en service. | ia-runtime |
| Mesures IA à refaire ou à confirmer | Latences du 3b des rapports `t03` et `v4` perturbées (Godot sur le GPU), à rejouer ; gains du filtre `player.intent` optimistes (réglés sur la série F qui les mesure). | ia-runtime |
| Outils Godot non suivis par git | `godot/scenes/tools/flow_test` et `ui_tour` ne sont pas versionnés ; c'est aussi le cas de `godot/scenes/world/sims_view.gd` et de la plupart des fichiers de la séance (un seul commit, 5a5d288 : `git status`). | utilisateur (commit), devops |

## Décisions par défaut du 29/10 (à confirmer par l'utilisateur)

ADR 0008 et ADR 0009 : acceptés (29/10, à confirmer).

| Sujet | Décision par défaut | Trace |
|---|---|---|
| Sites purement décoratifs | Interdits à l'IA (la 3D ne montre que ce qui est calculé) | ADR 0009 question 1 |
| Trajet de camion | Rejoué en 30 minutes simulées, étiquette pour un transit de plusieurs jours | ADR 0009 question 2 |
| Pack non couvert en assets | Fermé, sauf pour l'admin (audit `forced`) | ADR 0009 question 3, d.7 |
| Comparaison de modèles | Installer `qwen3.5:4b` (~3,3 Go) pour la mesurer (voir la ligne « `qwen3.5:4b` non mesuré ») | ADR 0008 |
| Modification d'un jeu | 409 pendant un lobby en cours | ADR 0009 critère 0009-11 |
| Panneaux d'atelier | Hors tranche 1 | ADR 0008 |
| Éditeur de grille | Retouches limitées aux rôles `decor` et `affichage` et au déplacement/rotation dans le bloc ; la topologie passe par les paramètres | ADR 0009 d.8 |

Risques associés :

| Risque | Détail | À prévenir |
|---|---|---|
| Mémoire des agents partagée | Entre joueurs d'un même lobby ; risque accepté par l'utilisateur | utilisateur, moteur-jeu |
| Sources à vérifier | Vitesses et heures de conduite : rag-knowledge livre les fiches en parallèle, elles ne sont pas encore citées | rag-knowledge, game-designer |
| Règles `calibre` sans source | Règles de placement dont la provenance est `calibre` | game-designer |
| Usine proposée sous condition | Seulement quand tous ses assets sont `importe` | assets-3d |
| Premier prompt `concept` | Peut dépasser 4100 tokens ; à mesurer | ia-runtime |
| Retouches `dropped` | Retouches retirées après un changement de paramètres (listées, non rejouées) | godot-dev, backend-api |
| Fantôme Godot et API | Écart possible entre le fantôme du client et le verdict de l'API (`check_placement`) | godot-dev, backend-api |

## Contraintes connues (non bloquantes)

- Jeu en salle : autoriser dans le pare-feu Windows de l'hôte le port TCP 8000 (API) et les ports UDP
  GAME_SERVER_PORTS (7000-7049) des serveurs de partie Godot.
- 16 Go de RAM partagés entre Docker (~2,5 Go plafonnés), Godot, Ollama et l'éditeur.
- tev1:4b (4,6 Go) ne tient pas en VRAM à côté du modèle de dialogue : réservé aux tâches hors temps réel.
- Table `generation_jobs` (ancien pipeline) conservée vide de nouveaux usages : à supprimer par une migration
  quand son historique ne servira plus.
- PostgreSQL Docker sur 5433 (5432 = PostgreSQL 18 local) ; services internes limités à 127.0.0.1.
- `fetch_wikipedia` exige `WIKI_CONTACT` (contact du projet) dans .env.
- Mots de passe du .env : valeurs de développement ; JWT_SECRET généré par setup.ps1.

## Questions ouvertes

- As-tu accès à des supports de formation en supply chain (avec droit d'usage) pour le corpus ?
- Taille des lobbies et durée type d'une séance.
- Quand tester le mode à distance, et sur quel hébergement ?
- Quels autres domaines simuler après la supply chain (mécaniques à coder pour chacun) ?
