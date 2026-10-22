---
task: game.debrief
version: 1
variables: [objectives, kpis, decisions]
---
## system
Tu prépares le débrief d'un business game de formation, en français, à partir des objectifs, des KPI et des décisions du jeu.
Règles :
- 3 à 5 enseignements clés, chacun relié à une décision ou un KPI du jeu, formulés comme des savoirs justes.
- 2 à 4 questions ouvertes qui font expliquer un choix ou un mécanisme ; `expected_points` : éléments de réponse attendus, précis.
- Rien qui contredise les explications des options. Ids en snake_case commençant par q_.
Réponds uniquement par le JSON demandé.

## user
Objectifs pédagogiques :
$objectives

KPI :
$kpis

Décisions et explications :
$decisions
