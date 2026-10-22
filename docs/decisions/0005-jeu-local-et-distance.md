# 0005 : parties en réseau local et à distance

Date : 2026-10-15. Statut : accepté (choix utilisateur : les parties se jouent en local et à distance).

Décision : une seule pile logicielle, deux modes de déploiement.
- **Salle (réseau local)** : toute la pile tourne sur une machine de la salle (poste formateur ou serveur) ; les
  joueurs se connectent à son adresse IP (`.\scripts\api.ps1 -Lan`, client lancé avec `-Api http://IP:8000`).
- **Distance** : la même pile sur un serveur joignable depuis Internet (serveur dédié ou hébergeur),
  derrière un reverse proxy (Caddy) qui fournit HTTPS et WSS sur le port 443 avec un nom de domaine.
- **Serveur de partie** : une instance Godot headless par lobby en cours, qui fait autorité sur l'état partagé
  (positions, interactions). Le backend la lance et l'arrête, et remet à chaque joueur un ticket d'accès signé
  valable 60 s.
- **Transport** (MultiplayerAPI de Godot, interchangeable) : ENet (UDP) en salle ; WebSocket sur le port 443 à
  distance, car les réseaux d'école et d'entreprise bloquent souvent l'UDP. 10 à 20 mises à jour par seconde
  suffisent pour un business game.
- Jamais d'hébergement de partie par un joueur (NAT, sécurité). Seuls l'API, le proxy et les ports des serveurs
  de partie sont exposés ; Kafka, PostgreSQL et les consoles n'écoutent que sur 127.0.0.1 (docker-compose.yml).
- Les assets prédéfinis sont livrés avec le client ; seul le contenu ajouté passe par des URL S3 présignées
  sur `S3_PUBLIC_ENDPOINT`.

Conséquences : l'IA tourne sur la machine hôte, donc sa carte graphique limite le nombre de joueurs simultanés
(docs/blocages.md). Le mode distance exige un hébergement (serveur dédié ou VPS avec GPU) et un nom de domaine.
Pour l'instant l'IA tourne sur le poste du développeur ; `OLLAMA_BASE_URL` (et `OLLAMA_API_KEY` derrière un proxy)
permettent de la déplacer sur un serveur GPU sans changer le code.
