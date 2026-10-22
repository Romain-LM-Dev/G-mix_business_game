# Évaluations des agents IA

Objectif : choisir le plus petit modèle suffisant pour chaque tâche, sur des données réelles et en français,
au lieu de supposer. Toute modification de `ai/models.yaml` ou d'un prompt se justifie par une mesure.

Un jeu par tâche (`<tâche>.jsonl`), 20 à 50 cas étiquetés à la main :

| Tâche | Mesure | Seuil de départ |
|---|---|---|
| `player.intent` | exactitude par classe, faux négatifs « injection » | ≥ 85 %, 0 injection manquée |
| `game.brief_check` | exactitude oui/non | ≥ 90 % |
| `game.outline` | schéma valide + `check_spec` sans erreur + note formateur 1-5 | ≥ 95 % valides, note ≥ 4 |
| `npc.dialogue` | fidélité aux extraits (aucune affirmation hors sources), longueur | 0 hallucination chiffrée |
| `answer.grading` | écart avec la note d'un formateur | ≤ 1 point sur 5 |

Pour chaque modèle candidat, relever : qualité, tokens entrée/sortie, latence, temps de chargement.
Priorité : comparer `tev1:0.8b` / `tev1:4b` à l'émulation par `qwen2.5:1.5b` sur `player.intent`,
car tev1 n'a pas été évalué en français par ses auteurs.
