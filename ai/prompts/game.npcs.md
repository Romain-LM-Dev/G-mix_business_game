---
task: game.npcs
version: 2
variables: [company, situation, roles, kpis, phases, competencies, zones]
---
## system
Tu crées les personnages non joueurs (PNJ) d'un business game de formation, en français. Chaque PNJ est un expert crédible que les joueurs consultent pour comprendre les notions du jeu ; il conseille mais ne décide jamais à leur place.
Règles :
- 2 à 4 PNJ aux expertises complémentaires qui couvrent les notions des phases.
- `expertise` : notions précises du domaine, pas de généralités.
- `dialogue_goals` : idées justes et vérifiables que le PNJ doit faire comprendre.
- `zone` : lieu de travail logique du PNJ parmi les zones proposées.
- `name` : prénom et nom d'une personne (ex. Claire Martin), jamais un identifiant ; ids en snake_case commençant par npc_.
Réponds uniquement par le JSON demandé.

## user
Entreprise : $company
Situation : $situation
Rôles des joueurs : $roles
Indicateurs : $kpis
Phases : $phases
Compétences visées : $competencies
Zones disponibles :
$zones
