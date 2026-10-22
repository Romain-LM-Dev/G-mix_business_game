# 0002 : Kafka hors du temps réel 3D

Date : 2026-10-15. Statut : accepté.

Contexte : le cahier des charges demande une liaison Godot <-> backend par Kafka et FastAPI « ou adaptée à
la 3D ». Une partie 3D multijoueur échange 20 à 60 mises à jour de position par seconde et par joueur.

Décision :
- Godot <-> FastAPI : HTTP JSON pour les requêtes, WebSocket pour les événements poussés au client.
- FastAPI <-> workers : Kafka pour tout ce qui est asynchrone (génération IA, ingestion, décisions de jeu,
  journal, audit), avec relais des événements vers les WebSockets.
- Positions et animations : multijoueur Godot (ENet), serveur Godot headless par lobby à terme.
- Dialogue PNJ : streaming direct par l'API ; seule la transcription finale passe par Kafka.

Conséquences : latence faible là où elle se voit, et Kafka garde ce qu'il fait bien (découplage, reprise
après panne, relecture, plusieurs consommateurs). Le mode d'hébergement du serveur Godot reste à choisir
(docs/blocages.md).
