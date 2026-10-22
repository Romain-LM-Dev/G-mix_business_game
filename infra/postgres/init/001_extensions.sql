-- Exécuté une seule fois, à la création du volume PostgreSQL.
-- Le schéma applicatif est géré par Alembic (backend/alembic), pas ici.
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector : embeddings RAG + assets
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- recherche floue (noms d'assets, PNJ)
CREATE EXTENSION IF NOT EXISTS unaccent;   -- recherche plein texte française sans accents
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), hachages
