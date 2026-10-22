"""Configuration centralisée : variables d'environnement + fichier .env à la racine du dépôt."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    gmix_env: str = "dev"
    log_level: str = "INFO"

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_user: str = "gmix"
    postgres_password: str = "gmix_dev"
    postgres_db: str = "gmix"

    kafka_bootstrap: str = "localhost:9092"

    s3_endpoint: str = "http://localhost:9000"
    # Adresse S3 vue par les clients (URL présignées) en réseau local ou à distance ; vide = s3_endpoint
    s3_public_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = "gmixadmin"
    s3_secret_key: str = "gmix-dev-secret"
    s3_bucket_assets: str = "gmix-assets"
    s3_bucket_knowledge: str = "gmix-knowledge"
    s3_bucket_games: str = "gmix-games"

    ollama_base_url: str = "http://localhost:11434"
    # Jeton Bearer si Ollama est déplacé sur un serveur derrière un reverse proxy (vide en local)
    ollama_api_key: str = ""

    # Contact exigé par Wikimédia pour gmix.tools.fetch_wikipedia (e-mail ou URL du projet)
    wiki_contact: str = ""

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "*"
    jwt_secret: str = "change-me"

    # Serveurs de partie Godot (ADR 0005) : un processus headless par lobby, lancé par l'API à la demande.
    # Vide : pas de présence multijoueur (chacun voit le monde seul, l'état de partie reste partagé par l'API).
    godot_console_exe: str = ""
    game_server_ports: str = "7000-7049"  # UDP (ENet) : à autoriser dans le pare-feu pour le jeu en salle

    gmix_ai_dir: Path = REPO_ROOT / "ai"

    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def buckets(self) -> list[str]:
        return [self.s3_bucket_assets, self.s3_bucket_knowledge, self.s3_bucket_games]


@lru_cache
def get_settings() -> Settings:
    return Settings()
