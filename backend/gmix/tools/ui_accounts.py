"""Comptes jetables des contrôles du client Godot (scripts\\godot.ps1 -Tour et -Flow).

python -m gmix.tools.ui_accounts create --scenario tour|flow
    Crée les comptes du scénario. Sortie : une ligne JSON {"ids": [...], "env": {variable: jeton}} lue par PowerShell,
    qui passe les jetons à Godot par variables d'environnement (rien n'est écrit sur le disque).
python -m gmix.tools.ui_accounts cleanup <id> [<id> ...]
    Supprime les lobbies et parties créés par ces comptes, puis les comptes. Un identifiant dont le nom n'a pas de
    préfixe jetable (uitour_, flowtest_) est ignoré.
"""

import argparse
import asyncio
import json
import secrets
import sys
import uuid
from typing import Any

from sqlalchemy import delete, or_, select

from gmix.api.auth import create_access_token
from gmix.db import get_sessionmaker
from gmix.db.models import BusinessGame, Lobby, User, UserRole
from gmix.tools.create_user import create_user

# scénario -> préfixe des noms ; comptes : (variable lue par Godot, suffixe, rôle, nom affiché)
SCENARIOS: dict[str, tuple[str, list[tuple[str, str, UserRole, str]]]] = {
    "tour": (
        "uitour_",
        [
            ("GMIX_TOUR_ADMIN_TOKEN", "admin", UserRole.ADMIN, "Administratrice Jetable de Contrôle"),
            ("GMIX_TOUR_PLAYER_TOKEN", "joueur", UserRole.PLAYER, "Jean-Christophe de la Tour-Maubourg Saint-Exupéry"),
        ],
    ),
    "flow": (
        "flowtest_",
        [
            ("GMIX_FLOW_TRAINER_TOKEN", "formateur", UserRole.ADMIN, "Administratrice Jetable de Contrôle"),
            ("GMIX_FLOW_PLAYER_TOKEN", "joueur", UserRole.PLAYER, "Jean-Christophe de la Tour-Maubourg Saint-Exupéry"),
            ("GMIX_FLOW_PLAYER2_TOKEN", "joueur2", UserRole.PLAYER, "Camille Joueuse"),
        ],
    ),
}
PREFIXES = tuple(prefix for prefix, _ in SCENARIOS.values())  # seuls les noms portant un de ces préfixes sont supprimés


async def create(scenario: str) -> dict[str, Any]:
    prefix, accounts = SCENARIOS[scenario]
    tag = secrets.token_hex(3)  # évite les collisions entre lancements
    ids: list[uuid.UUID] = []
    env: dict[str, str] = {}
    try:
        for variable, suffix, role, name in accounts:
            user = await create_user(f"{prefix}{suffix}_{tag}", secrets.token_urlsafe(18), role, name)
            ids.append(user.id)
            env[variable] = create_access_token(user)
    except Exception:
        await cleanup(ids)  # aucun compte à moitié créé ne reste
        raise
    return {"ids": [str(user_id) for user_id in ids], "env": env}


async def cleanup(ids: list[uuid.UUID]) -> str:
    """Supprime lobbies et parties des identifiants exacts ayant un nom jetable, puis ces comptes.

    L'ordre suit les clés étrangères : lobbies.trainer_id n'a pas de ON DELETE, les lobbies partent avant les comptes.
    """
    named = or_(*(User.username.startswith(prefix, autoescape=True) for prefix in PREFIXES))
    doomed = select(User.id).where(User.id.in_(ids), named)
    async with get_sessionmaker()() as session:
        lobbies = await session.execute(delete(Lobby).where(Lobby.trainer_id.in_(doomed)))
        games = await session.execute(delete(BusinessGame).where(BusinessGame.created_by.in_(doomed)))
        users = await session.execute(delete(User).where(User.id.in_(doomed)))
        await session.commit()
    return f"{users.rowcount} compte(s), {lobbies.rowcount} lobby(ies), {games.rowcount} partie(s)"


def main() -> int:
    parser = argparse.ArgumentParser(description="Comptes jetables des contrôles du client Godot (-Tour, -Flow).")
    commands = parser.add_subparsers(dest="command", required=True)
    create_cmd = commands.add_parser("create", help="crée les comptes d'un scénario (sortie : JSON)")
    create_cmd.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    cleanup_cmd = commands.add_parser("cleanup", help="supprime les lobbies, parties et comptes jetables")
    cleanup_cmd.add_argument("ids", nargs="+", type=uuid.UUID)
    args = parser.parse_args()
    if args.command == "create":
        print(json.dumps(asyncio.run(create(args.scenario))))
    else:
        print("Nettoyage :", asyncio.run(cleanup(args.ids)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
