# Références d'inspiration : monde « usine 3D »

Matière fournie par l'utilisateur le 22/10/2026 pour la génération de business games de supply chain
(atelier 3D Godot, agents PNJ, simulation : ADR 0006). Ce sont des **inspirations de conception**, pas des
sources : aucun chiffre ici n'est un fait sourcé.

## Fichiers

| Fichier | Contenu |
|---|---|
| `mon-monde-usine-3d.pdf` | Cahier « Mon monde – usine 3D », 12 pages, daté du 22/10/2026 |
| `carte-usine.jpg` | Carte isométrique de l'usine : réception, stock MP, production, contrôle qualité, emballage, maintenance, pilotage, reliés au fournisseur et à l'entrepôt PF / client |
| `agents-par-departement.jpg` | Fiches « Chaque département a ses agents » (un agent type par département, externe ou usine) |

## Ce que contient le PDF

- **Chaîne** : source de matière première, usine, entrepôt de produits finis (PF), client.
- **10 départements** : 2 externes (fournisseur, client) et 8 dans l'usine (réception, stock MP, production, contrôle qualité, emballage, maintenance et pièces de rechange, pilotage, entrepôt PF). Le texte dit « 7 départements » pour l'usine seule, sans l'entrepôt PF.
- **Production** : N lignes identiques en parallèle (1 à 3), chacune faite de machines en série avec des tables d'attente ; le goulot fixe le débit de la ligne.
- **Agents et états** : un ou plusieurs agents par département (chef de ligne, opérateurs, magasinier, technicien, etc.), états disponible, occupé, en déplacement, en pause, absent.
- **Paramètres** : délais et fiabilité fournisseur, capacités de stock, temps de cycle, MTBF, MTTR, taux de défaut, taille de lot, demande client.
- **Formules** : disponibilité, débit réel, débit de ligne et d'usine, taux de production, temps de traversée, temps pour un lot.
- **Interactions et flux** : tableaux « de, vers, ce qui passe, agents, déclencheur » (commande de MP, kit, OF, retouche, alerte de stock, panne).
- **Horloge** : journée de 8 h simulées, accélérable de ×1 à ×60, avec pause.

## À savoir avant d'utiliser ces documents

- Le document le dit lui-même : « Toutes les valeurs données sont des exemples, à remplacer selon le produit. » Les 95 % de fiabilité, 2 % de non-conformes, MTBF et MTTR, 100 produits par jour, etc. ne sont pas sourcés. Pour le moteur, les chiffres viennent de `ai/simulation.yaml` et des sources de `knowledge/` (exigence n° 1 du projet).
- Pas d'incohérence entre 60 et 53 produits / h : les 60 (section 8) sont un débit théorique « sans pauses ni pannes » (3 lignes x 20 / h) ; les 53 (section 5.3) sont le débit réel, calculé avec la disponibilité et le taux de défaut du goulot.
- Limite de la formule du cahier : elle ignore les pannes et le rendement cumulé des postes (audit du game-designer, 28/10/2026). Ne pas la reprendre telle quelle dans le moteur.
- Une vidéo Instagram a aussi été citée par l'utilisateur comme inspiration. Elle n'a pas pu être consultée : à faire décrire par l'utilisateur avant de s'en servir.
