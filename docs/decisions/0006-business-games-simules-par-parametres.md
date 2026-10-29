# 0006 : business games simulés, générés par paramètres, agents PNJ à mémoire

Date : 2026-10-22. Statut : accepté. Remplace la génération narrative par LLM (worker `generation`).

Contexte : la génération par qwen2.5:7b prenait 7 à 9 min, occupait le GPU et donnait des scénarios à
relire (sens des effets, KPI mal choisis, montants non calibrés). Le jeu de référence
github.com/eloiseferrante27-alt/Business_game montre un principe plus solide : une chaîne logistique simulée
semaine par semaine, où chaque module a ses actions et ses indicateurs.

Décision :
- Le formateur ne rédige rien : il choisit des paramètres (secteur, modules, agents en plus, caractère des
  agents, difficulté, semaines, aléas, produits, nom d'entreprise). `gmix.game.generation` assemble un jeu
  déterministe (graine conservée) à partir de `ai/simulation.yaml`, validé par `gmix.game.spec.SimSpec`
  puis par une partie jouée en pilote automatique, qui fixe aussi l'objectif de trésorerie. Instantané,
  sans modèle : plus de worker ni de topics de génération.
- `gmix.game.engine` simule chaque semaine : livraisons selon délai et fiabilité, usure et pannes, production
  bornée par capacité, TRS et composants, défauts, demande (saison, prix, aléa), OTIF, coûts, trésorerie.
  Un module non retenu tourne en pilote automatique ; un rôle tenu garde la main sur son module, un rôle libre
  laisse le module à toute l'équipe.
- Les aléas sont tirés une semaine à l'avance et annoncés. Le moteur calcule pour chaque agent ses
  informations essentielles (`briefings`) ; le modèle de dialogue ne fait que les dire, en une ou deux
  phrases, avec le caractère de l'agent. Les échanges sont gardés en base (`npc_memories`) et les six derniers
  du lobby avec cet agent entrent dans le prompt.
- Notions transmises : citations lues dans l'en-tête des fiches du corpus (`> Source :`), sauf le TRS (norme
  AFNOR NF E60-182, hors corpus).

Reprise du jeu de référence : principe hebdomadaire, profils de difficulté, noms et villes des fournisseurs,
produits du secteur industrie, noms des ouvriers, deux aléas, machine de ligne et bureau d'atelier portés
en GDScript. **Le dépôt n'a pas de licence : l'accord de son autrice est à obtenir avant toute diffusion.**

Conséquences : jeux justes et jouables par construction, mais limités aux mécaniques codées (supply chain) ;
un nouveau secteur s'ajoute dans ai/simulation.yaml, une nouvelle mécanique demande du code et des tests.
Les parties créées avant cette décision sont archivées (migration 5b1d2e7a9c40) et renvoient 410.
