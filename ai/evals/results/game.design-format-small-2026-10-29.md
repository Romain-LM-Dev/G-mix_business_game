# Format contraint d'Ollama : `pattern`, `maxLength`, `minItems`, `maxItems` (2026-10-29)

Modèle : qwen2.5:3b (alias `small`), Ollama 0.40.4, température 0,4, num_predict 400, 6 graines par sonde, `gmix.tools.eval_format`. Comptes seulement, aucune latence (GPU partagé avec Godot).

JSON valide = se lit et respecte le schéma de la sonde ; Contrainte violée = parmi les JSON valides, au moins un défaut (chiffre de toute écriture, texte trop court ou trop long, nombre d'éléments).

| Sonde | JSON valide | Tronqué | Erreur Ollama | Illisible | Contrainte violée | Violations |
|---|---|---|---|---|---|---|
| pattern seul [^0-9] (prompt hostile) | 6/6 | 0 | 0 | 0 | 6 | chiffre |
| pattern seul [^0-9] et pleine chasse exclus (prompt hostile) | 5/6 | 0 | 1 | 0 | 5 | chiffre |
| pattern seul, liste blanche (prompt hostile) | 2/6 | 4 | 0 | 0 | 0 | - |
| pattern liste blanche + maxLength 40 (prompt hostile) | 2/6 | 4 | 0 | 0 | 2 | trop long |
| pattern liste blanche avec {20,40} (prompt hostile) | 6/6 | 0 | 0 | 0 | 0 | - |
| pattern seul [^0-9] (prompt réaliste) | 4/6 | 2 | 0 | 0 | 3 | chiffre |
| pattern liste blanche avec {20,80} (prompt réaliste) | 6/6 | 0 | 0 | 0 | 0 | - |
| textes longs : liste blanche {20,700}, {40,500} et 2 à 4 objectifs {10,140} | 6/6 | 0 | 0 | 0 | 0 | - |
| maxLength 40 seul | 6/6 | 0 | 0 | 0 | 0 | - |
| minLength 20 + maxLength 40 | 6/6 | 0 | 0 | 0 | 0 | - |
| minItems 2 + maxItems 3 | 6/6 | 0 | 0 | 0 | 0 | - |
| objets : minItems 2, maxItems 4, enum, liste blanche {20,40} | 6/6 | 0 | 0 | 0 | 0 | - |

## Motifs

- `liste noire` = `^[^0-9]*$`
- `liste blanche` = `^[A-Za-zÀ-ÖØ-öø-ÿŒœ ,.;:!?'’«»()–-]{20,40}$`

## Erreurs d'Ollama

- `/api/chat -> HTTP 500: {"error":"prediction aborted, token repeat limit reached"}`

## Exemples de violations

- pattern seul [^0-9] (prompt hostile) (graine 1) : chiffre : `{"texte": "La prise de la Bastille a eu lieu le １４ juillet １７８９ dans les termes de notre calendrier julien, ou bien le １４ juillet １７８９ selon notre calendrier gr`
- pattern seul [^0-9] (prompt hostile) (graine 2) : chiffre : `{
  "texte": "La prise de la Bastille a eu lieu le １４ juillet １７８９ dans le calendrier gregorien, qui est également connue sous le nom de Fête nationale en Franc`
- pattern seul [^0-9] et pleine chasse exclus (prompt hostile) (graine 2) : chiffre : `{
  "texte": "La prise de la Bastille a eu lieu le ۱۴ juillet ۱۷۸۹, date marquante de la Révolution française qui a connu des événements importants comme la chu`
- pattern seul [^0-9] et pleine chasse exclus (prompt hostile) (graine 3) : chiffre : `{
  "texte": "La prise de la Bastille a eu lieu le ۱۴ juillet ۱۷۷۰, ce jour-là, les Parisiens, inspirés par la Déclaration des droits de l'homme et du citoyen, `
- pattern liste blanche + maxLength 40 (prompt hostile) (graine 5) : trop long : `{
  "texte": "La prise de la Bastille a eu lieu le  bastille  illsigne  jour  illsigne  mois  illsigne  année  illsigne  en  illsigne  année  illsigne  en  ills`
- pattern liste blanche + maxLength 40 (prompt hostile) (graine 6) : trop long : `{
  "texte": "La prise de la Bastille a eu lieu le  bastille  jour  jour  ills  an  deux  mille  huit  cent  soixante-dix-sept  (le  utoile  en  français)."
}`
- pattern seul [^0-9] (prompt réaliste) (graine 2) : chiffre : `{
  "texte": "Le jeu voulu par le formateur consiste dans une durée de  ₁₂ semaines, ₃ lignes de production, un objectif de livraison à l'heure de ₉₅ % et un dé`
- pattern seul [^0-9] (prompt réaliste) (graine 3) : chiffre : `{"texte":"Le jeu voulu par le formateur vise une production de ３ lignes durant １２ semaines avec un objectif de livraison à l'heure de ９５ % et une trésorerie ini`
