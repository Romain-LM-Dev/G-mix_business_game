# Formule de Wilson

> Source : Wikipédia (fr), « Formule de Wilson », révision 185813998 : https://fr.wikipedia.org/wiki/Formule_de_Wilson?oldid=185813998
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

Issue de la recherche opérationnelle, la formule de Wilson (1934) également connue sous le nom Quantité Economique de Commande ou EOQ (Economic Order Quantity) sous son nom original, ou aussi formule du lot économique détermine la période optimale de réapprovisionnement d'une unité de production (magasin, usine). Elle est couramment employée par les services logistiques. Elle a en fait été introduite dès 1913 par Ford W. Harris, mais a été attribué à Wilson car il en a fait l'analyse en profondeur.

## Description

La formule de Wilson se fonde sur un modèle simpliste optimisant le coût de gestion d'un stock dans le cadre d'une période fixe de réapprovisionnement $T$ à déterminer. On suppose que la consommation par unité de temps (disons journalière) $k$ est certaine et identique tous les jours. 

Le coût de gestion est évalué comme la somme d'un coût de stockage et d'un coût de lancement. Le coût de stockage est supposé linéaire en nombre moyen d'unités en stock. Comme à chaque début de période on commande exactement les unités pour la consommation de la période, le stock initial est $k\cdot T$ et le stock final est nul. On a donc un stock moyen de ${\frac {k\cdot T}{2}}$ unités. Avec un coût de stockage par unité et par jour de $c_{s}$ euros, le coût de stockage par unité de temps est de $c_{s}\cdot {\frac {k\cdot T}{2}}$ . Le coût de lancement d'une commande est noté $c_{l}$ , soit ${\frac {c_{l}}{T}}$ euros par unité de temps. On peut donc exprimer le coût total de gestion par unité de temps en fonction de la période de réapprovisionnement par: $C(T)=c_{s}\cdot {\frac {k\cdot T}{2}}+{\frac {c_{l}}{T}}$ Cette fonction de coût (hyperbolique) est minimale pour $T={\sqrt {\frac {2c_{l}}{c_{s}\cdot k}}}$ Et la quantité que l'on doit commander à chaque livraison est la suivante: $Q={\sqrt {\frac {2c_{l}\cdot k}{c_{s}}}}$ Les limites de cette formule résident dans le fait qu'elle est extrêmement dépendante de deux paramètres subjectifs : les coûts de stockage et de lancement.

En effet, les coûts de stockage sont en partie non proportionnels à la quantité stockée (c'est le cas par exemple du coût de location du hangar, structure), et les coûts de lancement sont difficiles à évaluer : lancer une commande supplémentaire coûte le temps des salariés qui sont rémunérés (charge de travail affectée à une tâche), et quelques frais de papier/téléphone. Il faudra nécessairement prendre en compte les coûts de transport liés à la commande.

Le modèle de la quantité économique de commande est très populaire dans le domaine scientifique de la gestion des stocks. Un grand nombre d'extensions de ce modèle ont été développés.
