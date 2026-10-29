"""Crée un compte en ligne de commande, en particulier le premier admin (ADR 0004 : aucun compte par défaut).

python -m gmix.tools.create_user --username admin --role admin   (mot de passe demandé au clavier)
python -m gmix.tools.create_user --username admin --role admin --provisional   (mot de passe aléatoire affiché,
    à changer à la première connexion : utilisé par scripts\\start.ps1)
"""

import argparse
import asyncio
import getpass
import re
import secrets
import sys

from sqlalchemy import func, select

from gmix.api.auth import MIN_PASSWORD_LENGTH, USERNAME_PATTERN, hash_password
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import User, UserRole

EXIT_EXISTS = 3  # identifiant déjà pris : start.ps1 n'y voit pas un échec (0 = créé, 1 = erreur)


class UserExists(ValueError):
    pass


async def create_user(
    username: str,
    password: str,
    role: UserRole,
    display_name: str | None = None,
    *,
    must_change_password: bool = False,
) -> User:
    async with get_sessionmaker()() as session:
        if await session.scalar(select(User.id).where(func.lower(User.username) == username.lower())):
            raise UserExists(f"Identifiant déjà utilisé : {username}")
        user = User(
            username=username,
            display_name=display_name or username,
            role=role,
            password_hash=hash_password(password),
            must_change_password=must_change_password,
        )
        session.add(user)
        await session.commit()
        return user


async def _run(args: argparse.Namespace, password: str) -> User:
    try:
        role = UserRole(args.role)
        return await create_user(
            args.username, password, role, args.display_name, must_change_password=args.provisional
        )
    finally:
        await get_engine().dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Crée un compte G-mix (premier admin, formateur, joueur).")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name")
    parser.add_argument("--role", choices=[r.value for r in UserRole], default=UserRole.ADMIN.value)
    secret = parser.add_mutually_exclusive_group()
    secret.add_argument("--password", help="sinon demandé au clavier, ce qui évite l'historique du terminal")
    secret.add_argument("--provisional", action="store_true", help="mot de passe aléatoire à changer à la connexion")
    args = parser.parse_args()
    if not re.fullmatch(USERNAME_PATTERN, args.username):
        parser.error("identifiant : 3 à 64 caractères parmi lettres, chiffres, point, tiret, tiret bas")
    password = secrets.token_urlsafe(9) if args.provisional else args.password or getpass.getpass("Mot de passe : ")
    if len(password) < MIN_PASSWORD_LENGTH:
        parser.error(f"mot de passe trop court ({MIN_PASSWORD_LENGTH} caractères minimum)")
    try:
        user = asyncio.run(_run(args, password))
    except UserExists as exc:
        print(exc, file=sys.stderr)
        return EXIT_EXISTS
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Compte créé : {user.username} ({user.role.value})")
    if args.provisional:
        print(f"Mot de passe provisoire : {password}  (à changer à la première connexion)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
