# Corpus de connaissances (RAG)

Un dossier par domaine, nommé avec le slug de ai/domains.yaml (ex. `knowledge/finance-entreprise/`).
Les PDF et DOCX ne sont pas versionnés : l'ingestion les archive dans le bucket `gmix-knowledge`.

Chaque dossier contient un `SOURCES.md` :

| Fichier | Titre | Auteur / éditeur | Date | Licence ou droit d'usage | Ingéré le |
|---|---|---|---|---|---|

Sources à privilégier : supports fournis par des formateurs (avec leur accord écrit), textes officiels (Légifrance, EUR-Lex),
publications publiques (ADEME, ANSSI, Bpifrance, INSEE), manuels sous licence libre. Les normes ISO sont
payantes et protégées : n'ingérer que des synthèses rédigées en interne.

Ingestion d'un domaine : déposer les fichiers dans `knowledge/<domaine>/`, les déclarer dans SOURCES.md
(licence obligatoire, sinon le fichier est ignoré), puis :

```powershell
.\scripts\ingest.ps1 -Domain supply-chain    # ingestion + mesure de couverture (ai/evals/<domaine>.rag.jsonl)
```

Articles Wikipédia (CC BY-SA 4.0, déclarés automatiquement dans SOURCES.md), depuis `backend/` :

```powershell
.venv\Scripts\python -m gmix.tools.fetch_wikipedia supply-chain --lang fr "Stock de sécurité"
```

Un PDF scanné (image sans texte) est refusé : il faut d'abord le passer à l'OCR.
Domaine prioritaire : `supply-chain` (socle Wikipédia ingéré ; supports de formateurs à ajouter).
`fetch_wikipedia` exige `WIKI_CONTACT` dans .env (e-mail ou URL de contact du projet, politique Wikimédia).
