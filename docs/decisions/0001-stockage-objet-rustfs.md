# 0001 : stockage objet RustFS (API S3)

Date : 2026-10-15. Statut : accepté.

Contexte : il faut un stockage objet local pour les assets 3D, les documents du RAG et les exports.
MinIO communautaire a perdu sa console d'administration (mai 2025), n'a plus d'images Docker publiées
(octobre 2025) et son dépôt est archivé depuis avril 2026.

Options : MinIO figé sur une ancienne image (plus maintenu), SeaweedFS (mature, plus complexe), Garage
(léger, AGPL, sans console), RustFS (Apache 2.0, console proche de MinIO, version 1.0 stable en septembre 2026).

Décision : RustFS 1.0.1 en développement. Le backend n'utilise que l'API S3 standard (boto3) : changer de
fournisseur ne demande que de modifier docker-compose.yml et les variables S3_* du .env.

Conséquences : `request_checksum_calculation="when_required"` dans le client boto3 pour rester compatible
avec les serveurs S3 tiers ; les volumes sont rendus accessibles à l'utilisateur 10001 par `storage-perms`.
