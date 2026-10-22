# Points bloquants et décisions en attente

Mis à jour le 2026-10-22. À tenir à jour par l'architecte.

## Décisions prises

| Sujet | Décision | Trace |
|---|---|---|
| Statut du projet | Indépendant de tout établissement : aucune ressource d'école (cours, serveur, SSO) n'est supposée | CLAUDE.md |
| Domaine prioritaire | Supply chain et logistique (premier du menu formateur) | ai/domains.yaml, knowledge/supply-chain/ |
| Authentification | Comptes créés dans l'application (identifiant + mot de passe), scrypt, jeton de 8 h | docs/decisions/0004 |
| Mode de jeu | En réseau local et à distance ; un serveur Godot par lobby pour la présence | docs/decisions/0005 |
| Hébergement de l'IA | Sur le poste de développement pour l'instant ; déplaçable sans changer le code | docs/ai-runtime.md |
| Modèles | Génération sur qwen2.5:7b (toutes les étapes) ; tev1:0.8b pour filtrer les messages des joueurs | ai/models.yaml |
| Stockage objet | RustFS (MinIO archivé) | docs/decisions/0001 |
| Règles de partie | Appliquées par l'API (moteur pur, verrou de ligne), pas par un worker | docs/architecture.md |

## Fait

- Environnement : Ollama 0.40.4, tev1 mesuré, 59 assets 3D, corpus supply chain (30 articles, 273 passages).
- 2026-10-22 : comptes et rôles ; génération complète par l'IA (worker `generation`) ; moteur de partie ;
  lobbies avec code d'accès ; PNJ (filtre tev1, RAG, dialogue) ; client Godot (connexion, menus formateur et
  joueur, salle du lobby, monde 3D construit depuis le gabarit `parc_activites`, HUD décisions / KPI /
  dialogue / débrief) ; présence multijoueur ENet avec ticket signé.
- Mesures de génération (RTX 3060 Laptop 6 Go, qwen2.5:7b à 18 % sur CPU) : 7 à 9 min pour 4 phases,
  environ 15 000 tokens dont 5 000 générés.

## Bloquants restants

1. **Justesse des scénarios générés : la relecture du formateur reste indispensable.** Mesuré sur 4
   générations : avec des montants libres, qwen2.5:7b inversait souvent le sens des effets par rapport à son
   explication. Depuis, le modèle ne donne qu'un sens et une ampleur, le code calcule le montant et tev1
   vérifie chaque sens contre l'explication : la dernière génération était cohérente (stock de sécurité 2, 3
   ou 4 semaines : couverture en hausse graduée, rotation en baisse). Restent des KPI parfois mal choisis
   (une activité au lieu d'un indicateur), des décisions proches d'une phase à l'autre (second essai
   automatique) et des montants indicatifs, non calibrés sur un secteur. Piste suivante : mécaniques chiffrées
   par domaine écrites par le game-designer (stock de sécurité, point de commande, Wilson) que l'IA paramètre.
2. **Corpus supply chain encore provisoire.** Wikipédia donne définitions et formules, pas les ordres de
   grandeur réalistes (coûts de possession, délais, taux de service par secteur). Il faut des supports de
   formation fournis avec leur accord et des études de cas chiffrées publiques, déclarés dans SOURCES.md.
   Les 14 autres domaines n'ont aucun corpus : leurs jeux sont signalés « non sourcés ».
3. **Capacité IA pour une séance réelle.** Une génération occupe le GPU 7 à 9 min ; pendant ce temps les PNJ
   répondent lentement. La RTX 3060 (6 Go) suffit au développement, pas à une vingtaine de joueurs.
4. **Hébergement à distance à choisir** (serveur avec GPU, nom de domaine, HTTPS, ports UDP ou WebSocket pour
   les serveurs de partie) quand les parties à distance seront testées. Avant cela : jeton de
   rafraîchissement (ADR 0004).

## Contraintes connues (non bloquantes)

- Jeu en salle : autoriser dans le pare-feu Windows de l'hôte le port TCP 8000 (API) et les ports UDP
  GAME_SERVER_PORTS (7000-7049) des serveurs de partie Godot.
- 16 Go de RAM partagés entre Docker (~2,5 Go plafonnés), Godot, Ollama et l'éditeur.
- tev1:4b (4,6 Go) ne tient pas en VRAM à côté du modèle de génération : chargé une fois en fin de
  génération pour la revue.
- Seuils de game.brief_check et game.coherence_review non mesurés (permissifs, avertissements seulement).
- PostgreSQL Docker sur 5433 (5432 = PostgreSQL 18 local) ; services internes limités à 127.0.0.1.
- `fetch_wikipedia` exige `WIKI_CONTACT` (contact du projet) dans .env.
- Mots de passe du .env : valeurs de développement ; JWT_SECRET généré par setup.ps1.

## Questions ouvertes

- As-tu accès à des supports de formation en supply chain (avec droit d'usage) pour le corpus ?
- Taille des lobbies et durée type d'une séance.
- Quand tester le mode à distance, et sur quel hébergement ?
- Faut-il des mécaniques chiffrées écrites à la main par domaine (plus justes) plutôt que laissées à l'IA ?
