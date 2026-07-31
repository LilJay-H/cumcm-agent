from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(project_root: Path, override_path: Path | None = None) -> dict[str, Any]:
    default_path = project_root / "config" / "default.json"
    config = json.loads(default_path.read_text(encoding="utf-8"))
    if override_path is not None:
        override = json.loads(override_path.read_text(encoding="utf-8"))
        config = _merge(config, override)
    return config

