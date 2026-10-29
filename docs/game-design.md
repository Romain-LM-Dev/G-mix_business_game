# Conception des business games

Modèle : simulation hebdomadaire d'une chaîne logistique, générée par paramètres (docs/decisions/0006).
Contenu : `ai/simulation.yaml` ; règles chiffrées : `backend/gmix/game/engine.py`.

## Ce qu'un business game garantit

1. **Vrai** : chaque notion transmise porte sa source (fiche du corpus ou norme citée) ; les agents ne disent
   que les chiffres calculés par le moteur et, pour une question de fond, les extraits du corpus.
2. **Cohérent** : capacités, stocks, commandes minimales et trésorerie sont calibrés sur la demande ; la spec
   est validée (références croisées) puis jouée en pilote automatique avant d'être proposée.
3. **Pédagogique** : quatre objectifs mesurés (OTIF, TRS, ruptures, trésorerie finale), un débrief avec
   leçons tirées de la partie, aléas survenus, notions et sources, journal des décisions de l'équipe.
4. **Jouable** : 4 à 12 semaines, 1 à 7 modules ; un joueur passif finit en rupture, le pilote automatique
   gagne en difficulté « découverte » et peine en « expert ».

## Menu de création (formateur)

Secteur (industrie, agroalimentaire, santé, automobile), modules joués, agents en plus (cliente, fournisseur,
direction), caractère des agents, difficulté, aléas, semaines, produits, nom d'entreprise, joueurs. La
relecture montre la partie de référence du pilote automatique ; la spec s'exporte, se modifie hors ligne et
se réimporte (validée).

## Modules, rôles et actions

| Module | Rôle | Action (poste de l'atelier) | Sans joueur |
|---|---|---|---|
| Approvisionnement | Acheteur·se | commander : offre (délai, fiabilité, prix, minimum) et quantité (quai de réception, rack composants) | point de commande, fournisseur standard |
| Production | Responsable de production | planifier une ligne (ligne) | deux semaines de couverture |
| Maintenance | Responsable maintenance | niveau d'entretien d'une ligne (ligne) | préventif |
| Qualité | Responsable qualité | part des lots contrôlés (poste qualité) | un lot sur deux |
| Commercial | Commercial·e | niveau de prix d'un produit (bureau) | prix catalogue |
| Transport | Responsable transport | mode de livraison (quai d'expédition) | messagerie |
| Finance | Contrôleur·se de gestion | découvert autorisé (bureau) | pas de contrainte |

Le formateur clôt chaque semaine (« Simuler la semaine ») ; l'état public est diffusé à tout le lobby.

## Agents PNJ

Un agent par module retenu, plus les agents choisis. Chacun a un rôle, des tâches, un caractère (préfixe et
style) et une zone de patrouille. Le moteur lui donne ses faits de la semaine ; un fait urgent affiche « ! »
au-dessus de sa tête et devient sa réplique quand un joueur approche. Le dialogue (`npc.dialogue`) répond en
une ou deux phrases à partir de ces faits et se souvient des six derniers échanges du lobby avec lui.

## Ajouter un secteur

Entrée `themes` de ai/simulation.yaml : quatre produits (prix, coût, demande, ligne) avec leur composant et
trois fournisseurs (rapide, standard, économique). Les tests vérifient chaque secteur dans les trois
difficultés.
