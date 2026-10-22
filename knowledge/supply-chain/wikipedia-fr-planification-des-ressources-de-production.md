# Planification des ressources de production

> Source : Wikipédia (fr), « Planification des ressources de production », révision 235185080 : https://fr.wikipedia.org/wiki/Planification_des_ressources_de_production?oldid=235185080
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

La planification des ressources de production (en anglais  materials resources planning ou materials requirements planning ou encore manufacturing resources planning, en abrégé MRP) associe logiciel et base de données en un système de gestion de production informatisé permettant la planification de la production en fonction des ressources en personnel, en matières premières, en machines et en temps, par rapport à un besoin daté ou un besoin de stock.

On distingue la « planification des besoins en composants » (en anglais materials requirements planning), née officiellement aux États-Unis en 1965 et qui ne représentait alors qu’une méthode de calcul des besoins en matières, de son évolution, la « planification des ressources de fabrication » (en anglais manufacturing resources planning, MRP2 ou MRP II). Ce modèle plus large, qui intègre la gestion de toutes les ressources de l'entreprise (consommables, c'est-à-dire « matières et composants », et renouvelables, c'est-à-dire « capacité machines et main-d'œuvre »), constitue un système de pilotage des ressources qui repose sur la prévision des ventes et les nomenclatures de produits et qui opère comme le MRP en flux poussé (c'est-à-dire que l'on établit le plan de production sur la base de prévisions).

## Évolution vers l'APS
Les limites des systèmes MRP/MRP2, notamment la planification à capacité infinie et l'approche séquentielle matières-puis-capacité, ont conduit au développement de systèmes de planification et d'ordonnancement avancés (APS, pour Advanced planning and scheduling). Contrairement au MRP, un système APS planifie simultanément les matières et les capacités en tenant compte de l'ensemble des contraintes (machines, main-d'œuvre, outillage, délais) et utilise des algorithmes d'optimisation combinatoire pour générer des plans réalisables et proches de l'optimum. Les systèmes APS sont proposés soit sous forme de modules complémentaires aux ERP existants (SAP IBP, Oracle), soit par des éditeurs spécialisés en optimisation (Siemens Opcenter APS, Dassault Systèmes DELMIA Ortems, DecisionBrain, Asprova).

## Phases de la MRP
La MRP a été mise au point dans les années 1960 par Joseph Orlicky. On distingue schématiquement trois phases dans la MRP :
la « planification des besoins en matières 0 » (materials requirements planning zero, MRP0), mise au point en 1964/65 : ce n'est qu'une méthode de calcul des besoins en matières ;
la « planification des besoins en matières 1 » (materials requirements planning one, MRP1) : première application industrielle de la gestion intégrée des flux de production, mise au point en 1971 ;
la « planification des ressources pour la fabrication 2 » (manufacturing resources planning two, MRP2) ; en plus du calcul des besoins nets en matières premières et composants, MRP2 effectue une planification des lancements en tenant compte des capacités des ressources par période ; mise au point en 1979.

Le processus classique de gestion de production est le suivant :

### Collecte des informations
. La première étape consiste à collecter les informations nécessaires à une gestion efficace.

#### Macro-données techniques
Macro-nomenclature
Macro-gamme
Macro-article
Macro-poste de charges

#### Données techniques
Article (vision produit)
Nomenclature (vision composant)
Gamme (vision processus)
Poste de charge (vision ressource)

#### Autres données
Prévisions des ventes
Commandes clients fermes
Stocks disponibles
En-cours
Ordres de Fabrication et d'Achat
Suivi des encours de fabrication

### Plan industriel et commercial (P.I.C.)

### Programme directeur de production (P.D.P.)
Le programme directeur de production fait le lien entre le calcul des besoins (prévision de vente de produits finis) et le plan industriel et commercial (propositions de production). C’est un élément clé pour planifier et établir les quantités à produire pour chaque produit fini. Le raisonnement est alors à moyen terme.

### Plan de charge (P.D.C.)
Un Plan de charge est alors réalisé. Si la charge dépasse temporairement la capacité, on effectue alors un lissage, c'est-à-dire un déplacement dans le temps de ressources afin de limiter les retards de délai, ou les recours à l'embauche d'intérimaires.
La recherche de l'optimum consiste alors à utiliser les ressources au maximum de leur capacité sans jamais la dépasser.

## De MRP à MRP2, le précurseur des progiciels de gestion intégrés ERP

Le MRP2 est le précurseur des progiciels de gestion intégrés (ERP, Enterprise Resources Planning) et reste souvent l'un de leurs modules fondamentaux.[réf. nécessaire]
