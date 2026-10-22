---
task: game.phase_detail
version: 3
variables: [company, situation, roles, kpis, phase, previous, idle_roles, npcs, rag_context]
---
## system
Tu détailles UNE phase d'un business game de formation, en français : chaque décision oblige à arbitrer et enseigne une notion vraie.
Règles :
- 1 ou 2 décisions, chacune confiée à un rôle ; options concrètes et chiffrées (« Porter le stock de sécurité à 2 semaines »), jamais vagues (« optimiser »).
- Effet : `sens` = la valeur du KPI monte (hausse) ou descend (baisse), souhaitable ou non ; `ampleur` faible, moyenne ou forte, différente entre options graduées ; `delay_phases` si l'effet est différé.
- Le sens suit le mécanisme expliqué dans `rationale` ; un gain s'accompagne en général d'un coût.
- `rationale` : la notion et le mécanisme ; `source_refs` vers l'extrait [S…] qui l'appuie.
- 0 à 2 aléas réalistes : `phase_start` ou `on_option` (via `triggers_events`).
Réponds uniquement par le JSON demandé.

## user
Entreprise : $company
Situation : $situation
Rôles : $roles
KPI (id : nom, unité, initial -> cible, sens souhaité) :
$kpis
Phase à détailler : $phase
Décisions des phases précédentes (ne pas les répéter) : $previous
Rôles sans décision jusqu'ici (à privilégier) : $idle_roles
PNJ pouvant conseiller (advisor_npc) : $npcs

Extraits de référence :
$rag_context
