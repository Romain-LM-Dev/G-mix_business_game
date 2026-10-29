# Temps de conduite et pauses des conducteurs routiers (règlement (CE) n° 561/2006)

> Source : Règlement (CE) n° 561/2006 du Parlement européen et du Conseil du 15 mars 2006 (harmonisation de certaines dispositions de la législation sociale dans le domaine des transports par route), articles 6 et 7. Texte lu dans la reproduction de l'OPPBTP (« Droit de la prévention », mise à jour du 1er juin 2022) : https://content.preventionbtp.fr/pdf/droit_de_la_prevention/article-6-du-reglement-ce-n-561-2006-du-15-mars-2006-relatif-a-l-harmonisation-de-certaines-dispositions-de-la-legislation-sociale-dans-le-domaine-des-transports-par-route.pdf (art. 6) et .../article-7-du-reglement-ce-n-561-2006-... (art. 7, même schéma d'URL). Consulté le 2026-10-29.
> Licence : texte réglementaire de l'Union européenne ; synthèse rédigée en interne, citations courtes. Le texte consolidé sur EUR-Lex (https://eur-lex.europa.eu, CELEX 32006R0561) n'a pas pu être ouvert (contrôle anti-robot) : vérifier le texte en vigueur avant toute publication.

## Ce que la source dit (articles lus)

Article 6 (durées de conduite) :
- « La durée de conduite journalière ne dépasse pas neuf heures. » Elle peut être prolongée jusqu'à dix heures
  maximum, « mais pas plus de deux fois au cours de la semaine » (art. 6, § 1).
- La durée de conduite hebdomadaire ne dépasse pas cinquante-six heures, ni la durée maximale de travail hebdomadaire de
  la directive 2002/15/CE (art. 6, § 2).
- La conduite totale accumulée sur deux semaines consécutives ne dépasse pas quatre-vingt-dix heures (art. 6, § 3).

Article 7 (pause) :
- « Après un temps de conduite de quatre heures et demie, un conducteur observe une pause ininterrompue d'au moins
  quarante-cinq minutes, à moins qu'il ne prenne un temps de repos. »
- Cette pause peut être remplacée par une pause d'au moins quinze minutes suivie d'une pause d'au moins trente minutes,
  réparties de manière à respecter la règle des 4 h 30.

## Lecture pour le jeu (dérivation, pas une citation)

- Un camion ne conduit donc pas plus de 9 h par jour en régime normal (10 h au plus, deux fois par semaine), soit au
  plus 56 h par semaine : c'est ce qui borne `reseau.conduite_h_jour` (valeur maximale sourcée : 9, exceptionnellement 10).
- Délai de transport (ADR 0009) = préparation + ⌈ distance ÷ vitesse moyenne ÷ heures de conduite par jour ⌉. La
  vitesse moyenne n'est PAS donnée par le règlement : elle reste `calibre`. Exemple : 900 km à 70 km/h = 12,9 h de
  conduite = 2 jours à 9 h/jour (calcul, vitesse supposée).
- Les pauses de 45 min sont comprises dans la journée de travail, pas dans les 9 h de conduite : avec 9 h de conduite,
  il y a au moins deux pauses (une toutes les 4 h 30 de conduite).

## Non lu (ne pas citer comme sourcé)

Repos journalier (art. 8), repos hebdomadaire, conduite en équipage, dérogations et modifications du règlement (UE)
2020/1054 : non lus dans le texte officiel. Le règlement s'applique aux véhicules de plus de 3,5 t (champ d'application,
art. 2 : non lu ici).
