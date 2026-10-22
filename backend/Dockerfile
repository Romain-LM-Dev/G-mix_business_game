# Image unique API + workers (profil compose "app"). En dev, on lance plutôt depuis le venv (scripts\api.ps1).
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY gmix ./gmix
COPY alembic ./alembic
# Installation éditable : le code reste dans /app (alembic.ini et migrations trouvés par gmix.bootstrap)
RUN pip install -e .

EXPOSE 8000
CMD ["uvicorn", "gmix.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
