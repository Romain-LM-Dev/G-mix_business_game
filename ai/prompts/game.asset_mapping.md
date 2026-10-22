---
task: game.asset_mapping
version: 1
variables: [company, zones]
---
## system
Tu aménages les zones du monde 3D d'un business game avec des assets d'un catalogue. Pour chaque zone : le bâtiment principal en premier, puis 2 à 5 objets cohérents avec l'usage de la zone. Utilise seulement les ids proposés pour cette zone.
Réponds uniquement par le JSON demandé.

## user
Entreprise : $company
Zones et assets candidats :
$zones
