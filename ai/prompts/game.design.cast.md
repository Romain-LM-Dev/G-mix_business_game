---
task: game.design.cast
version: 1
variables: [company, pitch, audience_label, agents, personalities, objectives]
---
## system
Tu écris les personnages d'un business game. Pour chaque agent de la liste : un nom français crédible, un caractère choisi parmi ceux proposés, et une présentation courte de son parcours et de sa façon de travailler.
Règles :
- Écris en français, sans aucun chiffre.
- Chaque agent garde son identifiant et son métier. Les noms sont tous différents.
- Varie les caractères et choisis-les selon le métier, parmi ceux proposés seulement.
- La présentation est lue par le joueur sur la fiche : n'y mets aucun fait de la partie (stock, retard, argent), aucune règle, aucune consigne.
## user
Entreprise : $company. $pitch
Public : $audience_label

Agents à nommer :
$agents

Caractères possibles :
$personalities

Objectifs du jeu, pour t'imprégner du contexte sans les citer :
$objectives

Écris les personnages.
## repair
Ta réponse contient des erreurs :
$errors
Corrige ces points, sans rien changer d'autre ni écrire de chiffre, et renvoie tous les personnages.
