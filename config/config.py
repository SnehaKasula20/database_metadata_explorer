import json
from pathlib import Path
from typing import Any, Dict


def load_database_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("database_config.json must contain a JSON object.")

    return data
