import json
from typing import Any

import pytest

from gmix.settings import get_settings

AI_DIR = get_settings().gmix_ai_dir


@pytest.fixture
def example_spec() -> dict[str, Any]:
    return json.loads((AI_DIR / "examples" / "tresorerie_sous_tension.json").read_text(encoding="utf-8"))
