# Temps moyen entre pannes

> Source : Wikipédia (fr), « Temps moyen entre pannes », révision 240442106 : https://fr.wikipedia.org/wiki/Temps_moyen_entre_pannes?oldid=240442106
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

Le temps moyen entre pannes ou durée moyenne entre pannes, souvent désigné par son sigle anglais MTBF (mean time between failures), est une des valeurs qui indiquent la fiabilité d'un composant, d'un produit ou d'un système. C'est la moyenne arithmétique du temps de fonctionnement entre les pannes d'un système réparable.
L'expression anglaise mean time between failures est parfois traduite à tort en français par « moyenne des temps de bon fonctionnement » alors qu'il s'agit du temps moyen de fonctionnement entre défaillances hors de tout arrêt volontaire ou programmé.

## Remarques
Les pannes ne sont qu'une des sources d'indisponibilité du système car d'autres paramètres influencent son bon fonctionnement (d'un point de vue technique comme d'un point de vue utilisateur). Ce qui intéresse l'entreprise, c'est la durée effective de production, qui prend en considération d'autres facteurs comme l'organisation (disponibilité des personnes), la logistique (approvisionnements, flux des biens produits) et les non-qualités.
Le MTBF (mean time between failures) est la mesure du taux de défaillances aléatoires dans un lot de composants, à l'exclusion des pannes systématiques dues par exemple aux défauts de fabrication (« défauts de jeunesse ») et à l'exclusion de l'usure due à un usage normal du système (wear-out en anglais).
La valeur du MTBF ne peut être définie que dans un usage et un environnement donnés. Par exemple, une chaussure a un MTBF extrêmement élevé si l'on marche peu, il est très peu probable qu'elle se déchire spontanément en deux. Mais si l'on marche beaucoup, il ne faudra que quelques mois pour que la semelle soit complètement usée.
Le MTBF est une notion statistique sur un lot de fabrication identique : dans l'exemple de la chaussure, si le cuir utilisé pour l'une d'elles a un défaut passé inaperçu, celle-ci ne durera que quelques jours, mais cela ne change pas la statistique sur une grande quantité.

## Calculs de MTBF
Le MTBF d'un composant ou d'un ensemble de composants peut être exprimé en heures, ou en son inverse, en FIT (failure(s) in time). Le FIT est le taux de défaillances aléatoires, généralement exprimé en composants par giga-heure. C’est-à-dire FIT = (proportion de composants en panne) x 109 / (durée cumulée de fonctionnement en heures).
Lorsqu'un système est composé de plusieurs composants, on fait la somme de tous les FIT de chacun des composants en supposant que la panne d'un seul composant provoque la panne du système. Dans le cas d'un système redondant, il faut ajuster le calcul en conséquence. Toutefois, le calcul est relativement complexe car les taux de défaillances ne sont alors plus constants et il faut faire appel à des calculs de moyennes intégrales.
On a alors MTBF = 109 / FIT dans le cas de composants présentant un taux de défaillance constant (répartition exponentielle).

## Définition précise
Pour un système réparable, le MTBF est le temps moyen entre le début de la réparation et la panne suivante. Le MTTF est l'identique du MTBF si ce n'est qu'il ne considère que la première panne.
Le temps moyen entre la panne et la remise en état de fonctionnement (dans lequel entrent les temps de diagnostic, d’approvisionnement, de réparation, etc.) est appelé « temps moyen avant réparation » (en anglais mean time to repair ou MTTR) ou « temps moyen d’indisponibilité » (en anglais mean downtime ou MDT).
Si la loi de fiabilité du système est une loi exponentielle (cas typique des composants électroniques), c'est-à-dire si le taux de défaillance λ est constant, alors le  MTTF (Mean Time To Failure = temps moyen de fonctionnement avant panne) est l’inverse de λ :

.
Le relevé des pannes se fait sur une période donnée (durée d'étude). Si l'étude s'arrête alors que le système est en panne, on a alors :

.
Si par contre l'étude s'arrête alors que le système fonctionne, on est dans le cas d'une censure à droite. Se pose le problème de la prise en compte du temps passé après la dernière panne :

soit on l'ignore, on néglige alors une partie de l'information ;
soit on le prend en compte tel quel, mais on minore alors le MTBF puisque l'on fait comme s'il s'était produit une panne au dernier moment, alors qu'elle n'est pas encore survenue ; pour n pannes, il y a n + 1 périodes de bon fonctionnement, et donc :
.
La différence devient anecdotique si le nombre de défaillances est très important.
Le MTTF est souvent désigné par la lettre grecque θ (thêta).
Si la loi de fiabilité est exponentielle, le taux de pannes et le MTTF sont inverses l’un de l’autre, on les utilise indifféremment.
Si la fiabilité obéit à une loi statistique identifiée, de fonction « densité de pannes » ƒ(t), alors le MTTF vaut

avec :

.
Le MTTF se déduit également du taux de réparation.
Le MTBF ne donne l’instant moyen où la probabilité de fonctionnement égale la probabilité de panne, que dans des distributions statistiques symétriques.
En distribution exponentielle, la probabilité qu’un élément soit défaillant avant le MTBF est de 0,63.

## Exemples
Les produits commerciaux se définissent en général par leur « durée de vie » ou leur « temps moyen de fonctionnement » dans un usage normal et un environnement défini.
Par exemple, les disques durs d'aujourd'hui ont souvent un MTBF supérieur à 100 000 heures, ce qui correspond, pour un serveur tournant en permanence, à plus de onze années de fonctionnement moyen sans panne. Intel a annoncé en 2008 des solid-state drives ayant un MTBF de 1,2 million d'heures.
Cette spécification est toujours accompagnée de conditions de milieu (température, humidité) et d'utilisation selon une norme définie (par exemple la norme MIL-HDBK-217F).
