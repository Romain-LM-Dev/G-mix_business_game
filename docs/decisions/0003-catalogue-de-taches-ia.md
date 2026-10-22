# 0003 : catalogue de tâches IA, contexte fixe par modèle, tev1 avec repli

Date : 2026-10-15. Statut : accepté.

Contexte : 6 Go de VRAM, des agents IA à la fois dans la génération (qualité) et dans le jeu (latence), et
l'exigence d'optimiser la consommation de tokens.

Décision :
- Le code appelle des tâches déclarées dans ai/models.yaml (modèle, repli, options, budgets, schéma, RAG,
  cache), validées par les tests ; aucun nom de modèle dans le code.
- `num_ctx` est fixé par modèle : mesuré sur ce poste, alterner 512 et 4096 sur qwen2.5:1.5b rechargeait le
  modèle à chaque appel (~7 s). Corrigé, l'aller-retour complet du test de fumée est passé de 13,4 s à 0,4 s.
- Questions fermées -> modèle de décision tev1 (API /v1/systemone, compatible Jev) ; tant qu'il est absent
  ou non validé en français, émulation par un petit modèle contraint par `enum`, au même format de réponse.
- Sorties structurées par décodage contraint, puis validation de schéma et contrôles déterministes avant
  toute revue par IA.

Conséquences : changer de modèle est une modification de configuration testée ; le choix de chaque modèle
doit être justifié par une évaluation (ai/evals).
