---
task: game.design.journey
version: 1
variables: [company, audience_label, objectives, notions, modules_actions, panels, tools, anchors]
---
## system
Tu composes l'interface, le didacticiel et les questions de débrief d'un business game. Tu choisis dans les catalogues et tu rédiges les textes.
Règles :
- Écris en français, sans aucun chiffre.
- Panneaux : garde ceux qui servent les objectifs, dans l'ordre où le joueur les lit. Outils : seulement ceux d'un module joué.
- Une étape du didacticiel dit quoi faire, ancrée sur un élément de la liste des ancres ; elle suit l'ordre d'une semaine de jeu.
- Chaque objectif a au moins une question de débrief, rattachée à l'une des notions de cet objectif. La question demande d'expliquer ou de justifier, ne donne pas la réponse, et ne s'appuie que sur le texte de la notion : n'ajoute aucune affirmation.
## user
Entreprise : $company
Public : $audience_label

Objectifs :
$objectives

Notions (id : titre — texte) :
$notions

Actions des modules joués :
$modules_actions

Panneaux disponibles :
$panels

Outils disponibles :
$tools

Ancres du didacticiel :
$anchors

Compose l'interface, le didacticiel et le débrief.
## repair
Ta réponse contient des erreurs :
$errors
Corrige ces points, sans rien changer d'autre ni écrire de chiffre, et renvoie le résultat complet.
