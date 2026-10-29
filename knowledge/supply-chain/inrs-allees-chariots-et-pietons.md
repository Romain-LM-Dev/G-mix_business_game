# Allées de chariots et séparation piétons / engins (INRS)

> Source : INRS, « Chariots automoteurs de manutention à conducteur porté. Évaluation et prévention des principaux risques lors de l'utilisation », brochure ED 949, 1re édition 2005, réimpression mars 2013 (sans mise à jour), § 2.2.2 « Mesures organisationnelles et d'aménagement du site », pages imprimées 19-20 (pages PDF 21-22) : https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-949.pdf. Complété par INRS, « Conception et aménagement des plates-formes et entrepôts logistiques », ED 6350, 1re édition octobre 2019, annexe 3 « Indications sur les largeurs de voies de circulation », page imprimée 38 (page PDF 40) : https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6350.pdf. Consultés le 2026-10-29.
> Licence : publications INRS ; synthèse rédigée en interne, citations courtes (reproduction intégrale non faite). Droits de diffusion extérieure à confirmer auprès de l'INRS.

## ED 949, § 2.2.2, pages 19-20

- Les lieux de travail doivent être aménagés pour que la circulation des piétons et des véhicules se fasse de façon sûre
  (art. R. 232-1-9 cité par la brochure) ; dès que l'importance de la circulation de véhicules le justifie, « les
  circulations de véhicules et de piétons soient distinctes ».
- Pour séparer le flux piétons du flux chariots, un passage pour piétons « d'une largeur d'au moins 0,80 m », distinct des
  allées de chariots et séparé par un garde-corps, doit être aménagé.
- Largeur d'allée (circulaire DRT 99/7 du 15 juin 1999, reprenant l'arrêté du 30 juillet 1974 abrogé ; la brochure dit
  que ces dimensions « peuvent permettre de satisfaire » à l'article R. 233-13-16) :
  - sens unique : largeur du chariot (ou du chargement s'il est plus large) + 1 mètre ;
  - double sens : largeur des deux chariots (ou chargements) + 1,40 mètre.
- Éviter dans les allées les angles et courbes brusques, les plans inclinés et les rampes (début de liste de mesures,
  p. 20).
- Brochure ED 949, § 2.3, p. 23-24 (tableau des mesures contre le heurt de piéton) : établir un plan de circulation séparant le
  flux chariots du flux piétons ; matérialiser les allées piétons et les protéger par des barrières.

## ED 6350, annexe 3, page 38 : largeurs de voies (indications)

Tableau « sens unique sans dépassement » / « double sens ou sens unique avec dépassement » :
- piéton seul : 0,80 à 0,90 m / 1,50 m (0,90 m si dégagement d'évacuation incendie) ;
- piéton utilisant un engin de manutention ou engin à conducteur porté : largeur de l'engin (ou de la charge) + 1 m /
  largeur des 2 engins (ou des 2 charges) + 1,40 m ;
- véhicule léger : 3 m / 5 m ; poids lourd : 4 m / 6,50 m (en ligne droite).
- ED 6350, p. 15 : « Le choix des largeurs est primordial et fige l'utilisation des zones de stockage » (palettiers,
  choix des chariots, sens unique ou double sens).

## Lecture pour le jeu (dérivation)

La règle `aisle_min` du pack n'est pas un nombre unique : elle dépend de la largeur de l'engin. Pour un chariot de
largeur 1 m environ (hypothèse du jeu, non issue de la source), sens unique : 1 + 1 = 2 m ; double sens : 2 + 1,40 =
3,40 m. Le 2,5 m actuel du pack n'est donc pas sourcé tel quel : le sourcer par « largeur du chariot + 1 m ».
