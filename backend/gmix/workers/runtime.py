"""Lancement commun des workers : logs et arrêt propre par Ctrl+C (pas de signaux POSIX sous Windows)."""

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from typing import Any

from gmix.logging_setup import setup_logging
from gmix.settings import get_settings


def run_worker(main: Callable[[], Coroutine[Any, Any, None]]) -> None:
    setup_logging(get_settings().log_level)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
