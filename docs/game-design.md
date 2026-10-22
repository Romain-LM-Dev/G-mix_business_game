# Conception des business games

## Ce qu'un business game généré doit garantir

1. **Vrai** : chaque chiffre, règle ou loi vient du corpus RAG du domaine ou d'une source citée
   (`sources`, `source_refs`). Un PNJ ne cite rien hors de ses extraits.
2. **Cohérent** : effets chiffrés compatibles entre eux et avec la taille de l'entreprise ; KPI dérivés
   calculés par formule ; chaque rôle décide ; chaque événement déclenché existe (`gmix.game.coherence`).
3. **Pédagogique** : objectifs observables (Bloom), chacun mesuré par un KPI, une décision ou une question
   de débrief ; chaque option a une explication (`rationale`) révélée au débrief.
4. **Jouable** : 60 à 180 minutes débrief compris, 2 à 4 phases, 2 à 4 options par décision, pas de
   bonne réponse évidente, erreurs instructives sanctionnées par un événement réaliste.

Exemple de référence validé : ai/examples/tresorerie_sous_tension.json (finance, BFR, délais de paiement LME).

## Menu de création (formateur)

1. Domaine (liste `GET /api/v1/domains`, avec la taille du corpus sourcé de chacun).
2. Niveau (débutant, intermédiaire, avancé), durée, nombre de joueurs.
3. Demande libre : contexte souhaité, secteur, contraintes, points à travailler.
4. Génération avec progression étape par étape (WebSocket), 7 à 9 min sur le poste actuel.
5. Relecture : résumé, KPI, décisions et effets, PNJ, sources, avertissements et réparations automatiques ;
   modification hors ligne par export JSON puis « Remplacer par un fichier » (validée par le schéma).
6. Publication : lobby et code d'accès ; le formateur lance la partie et passe les phases.

Non fait en v1 : choix des compétences par cases à cocher (celles du domaine sont utilisées), équipes,
régénération d'une seule section, éditeur visuel de la spec, rythme automatique des phases.

## Effets chiffrés des décisions générées

Le modèle choisit pour chaque effet un sens (la valeur du KPI monte ou baisse) et une ampleur (faible,
moyenne, forte) ; le code en déduit le montant : 15, 30 ou 50 % de l'écart entre valeur initiale et cible.
Quelques bons choix « moyens » atteignent donc la cible, aucune option ne règle tout seule le problème. Le sens
de chaque effet est ensuite vérifié contre l'explication de l'option (tev1) et inversé s'il la contredit.
Les montants restent indicatifs : un ordre de grandeur sectoriel exact demande un corpus chiffré.

## Ajouter un domaine

Entrée dans ai/domains.yaml (compétences, KPI, références, rôles) par l'agent game-designer, puis corpus
de documents sourcés dans knowledge/<domaine>/ ingéré par rag-knowledge. Sans corpus, la génération reste
générale et le formateur doit en être averti.
