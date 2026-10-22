# 0004 : comptes locaux (identifiant et mot de passe)

Date : 2026-10-15. Statut : accepté (choix utilisateur : connexion avec un compte créé, pas de SSO).

Contexte : trois rôles (joueur, formateur, admin), parties en réseau local et à distance.

Décision :
- Comptes en base : identifiant unique (`username`), nom affiché, e-mail facultatif, rôle, mot de passe haché
  en scrypt (bibliothèque standard Python, paramètres OWASP n=2^14 r=8 p=1), jamais stocké ni journalisé en clair.
  Révision 2026-10-22 : scrypt au lieu d'Argon2id/pwdlib, pour éviter une dépendance native de plus.
- Création : premier admin en ligne de commande (aucun compte par défaut dans le code) ; l'admin crée les
  formateurs ; chaque formateur crée les comptes de ses joueurs (un par un ou import CSV). Mot de passe
  provisoire à changer à la première connexion. Pas d'inscription libre dans la première version.
- Sessions : jeton d'accès JWT de 15 min signé avec JWT_SECRET, plus jeton de rafraîchissement opaque de
  30 jours, stocké haché en base, renouvelé à chaque usage et révocable.
  Première version (2026-10-22) : jeton d'accès de 8 h (une séance) sans rafraîchissement ; un compte désactivé
  est refusé dès la requête suivante. Le rafraîchissement reste à faire avant l'ouverture du jeu à distance.
- Commande du premier admin : `backend\.venv\Scripts\python -m gmix.tools.create_user --username admin --role admin`.
- WebSocket : jeton d'accès dans l'en-tête Authorization (Godot : `handshake_headers`) ; l'identifiant de
  session découle de l'utilisateur au lieu d'être choisi par le client.
- Protection : limitation des tentatives de connexion par identifiant et par adresse IP ; HTTPS obligatoire
  à distance ; création de compte et changement de rôle publiés sur `gmix.audit`.

Conséquences : migration de `users` (`username` unique, `email` facultatif, `must_change_password`), table des
jetons de rafraîchissement, dépendances FastAPI de rôle. Réalisation : agent backend-api ; écran de connexion
et gestion des comptes : agent godot-dev.
