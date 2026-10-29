# Disponibilité

> Source : Wikipédia (fr), « Disponibilité », révision 240442167 : https://fr.wikipedia.org/wiki/Disponibilit%C3%A9?oldid=240442167
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

Dans le domaine de l'ingénierie de fiabilité, la disponibilité d'un équipement ou d'un système est une mesure de performance obtenue en divisant la durée pendant laquelle ledit équipement ou système est opérationnel par la durée totale pendant laquelle on aurait souhaité qu'il le soit. On exprime classiquement ce ratio sous forme de pourcentage.

## Définition
Par définition, la disponibilité est l'aptitude d'un bien ou d'une entité à être en état d'accomplir une fonction requise dans des conditions données, à un instant donné ou pendant un intervalle de temps donné, en supposant que la fourniture des moyens extérieurs nécessaires soit assurée.
Il ne faut pas confondre la disponibilité avec la « rapidité de réponse », que l'on appelle aussi « performance ».
La disponibilité est aussi à prendre de manière relative. Les systèmes n'ont pas la même importance suivant le moment, l'impact n'est pas le même selon qu'on a absolument besoin du système ou qu'on est dans une période de moins grand besoin.
La disponibilité est notée D (en anglais, elle est notée A, pour availability).

## Modalités de calcul

### Exemples
Soit une machine que l'on souhaite utiliser 12 heures par jour, mais qui tombe en panne en moyenne pendant 1 heure chaque jour et a besoin d'une demi-heure de réglages divers pour sa remise en fonctionnement. Sa disponibilité est : ${\text{Ai}}\ =\ {\frac {\text{12 - 1 - 0,5}}{\text{12}}}\ =\ {\frac {\text{10,5}}{\text{12}}}\ =\ {\text{87,5}}\ \%\!$ Des études plus poussées peuvent être réalisées en tenant compte du temps d'arrivée des techniciens, du temps de diagnostic, du temps de correction de la défaillance et de la logistique pour les pièces de rechange.

La sauvegarde informatique peut être une grosse consommatrice de resources réseau au détriment des autres applications. La nuit, si personne ne travaille dans l'établissement, cette sauvegarde peut se faire sans perte de disponibilité pour les applications interactives.

### Formule de la disponibilité
La disponibilité est le plus souvent estimée à partir de sa valeur asymptotique (limite de la disponibilité instantanée lorsqu'on fait tendre l'instant considéré vers l'infini), définie par la formule : ${\text{Ai}}={\frac {\text{MTTF}}{\text{MTTF+MTTR}}}\ ={\frac {\text{MTTF}}{\text{MTBF}}}\!$ où le MTTF (mean time to failure) est le temps moyen de bon fonctionnement jusqu'à la première panne, le MTTR (mean time to repair) est le temps moyen jusqu'à réparation (temps de réparation + temps d'attente entre la panne et le début de la réparation) et le MTBF (mean time between failures) est le temps moyen entre pannes.
Considérant que le besoin est de 8760 heures, soit un an :

## Gestion d'un parc ou d'une flotte
Soit un parc de m machines (ou une flotte de m véhicules). La relation ci-dessus peut s'écrire : ${\frac {disponibles}{total}}={\frac {1}{1+{\frac {MTTR}{MTTF}}}}$ .

il est souhaitable que MTTF, qui mesure la fiabilité globale, soit grand ;
mais il est surtout important que MTTR, qui mesure la performance du système de réparations, soit petit devant MTTF ; cela suppose :
côté machine, que chaque machine ou véhicule ait une bonne maintenabilité : structure claire, organes accessibles, éléments standards (réparabilité) et que l'ensemble soit facile à tester (testabilité);
côté utilisateur, que l'atelier de réparation soit convenablement doté (pièces de rechange, banc(s) de tests, personnels) et géré.
Pour une réparation rapide, si les machines (resp. véhicules) sont organisées en une hiérarchie blocs/modules/éléments, on peut procéder aux réparations en plusieurs stades :

une première équipe repère et change le ou les blocs défectueux, pour remettre en service la machine le plus vite possible ;
une seconde équipe repère et change les modules fautifs dans les blocs défectueux, pour rendre ces blocs de nouveau opérationnels ; puis, elle (ou une troisième équipe) repère et change les éléments défectueux dans les modules fautifs pour restituer des modules opérationnels.
Avec une telle organisation, la durée de réparation déterminant la disponibilité n'est plus la durée totale de réparation, mais se réduit à la durée du dépannage par la première équipe.
Selon les cas, disposer d'un parc (resp. d'une flotte) plus important(e) demandera l'acquisition de nouvelles unités (respectant si possible un principe de communalité avec le parc actuel) et/ou une organisation plus efficace de l'atelier de réparation.

## Dans le domaine de l'énergie

Le taux de disponibilité énergétique est définie dans le contexte du nucléaire comme « le ratio entre l’énergie qui aurait pu être produite par la capacité disponible pendant une période donnée et l’énergie qui aurait pu être produite (pendant la même période) à la puissance de référence d’une tranche ».
Le stockage de l'électricité est encore impossible en grande quantité. Le taux de disponibilité et de réponse des moyens de production électrique est donc un enjeu majeur pour la gestion et la stabilité et la sécurité du réseau électrique. C'est aussi un enjeu d'efficacité énergétique et économique : Selon EDF (2009), en France, 1 % de taux de disponibilité supplémentaire du parc nucléaire représentait 200 millions d'euros d'excédent brut d'exploitation. À l'automne 2009, sur 58 réacteurs en service, 18 étaient à l'arrêt, et le taux de disponibilité avait en 2008 reculé d'un point (à hauteur de 79,2 %).
La gestion informatisée, la maitrise de la demande en énergie électrique, les interconnexions entre réseaux et des dispositifs d'effacement ont amélioré la souplesse de réponse des réseaux. Les smartgrids  devraient aussi encore y contribuer notamment dans la perspective d'une « troisième révolution industrielle » s'appuyant sur un « Internet de l'énergie », tel que proposé par Jeremy Rifkin.
À titre d'exemple, en France, les énergies intermittentes (éolien, solaire notamment) ont un faible taux de disponibilité énergétique et de réponse, mais développent des nouveaux moyens de stockage d'énergie[réf. nécessaire]. Les centrales à énergies fossiles ont un bon taux de disponibilité mais sont polluantes et sources de gaz à effet de serre. La production de base est assurée en France par le parc nucléaire dont la disponibilité tend à diminuer de 2006 à 2009 en raison du vieillissement des centrales notamment (78 %, soit niveau le plus bas depuis 1993, EDF ayant repoussé son objectif de 85 % à l'horizon 2015). La production nucléaire est principalement tamponnée par l'hydroélectricité, qui a produit 39 TWh en 2010 et a un très bon taux de disponibilité (de 87,2 % en 2010 contre 86,7 % en 2009), avec un taux de réponses aux sollicitations dépassant 99 %.
