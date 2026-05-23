"""Read and write key=value pairs in the .env file without destroying existing content."""
from __future__ import annotations
import re
from pathlib import Path

_ENV_PATH = Path(".env")


def load_env_dict() -> dict[str, str]:
    if not _ENV_PATH.exists():
        return {}
    result = {}
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def save_env_dict(updates: dict[str, str]) -> None:
    """Merge updates into .env, preserving comments and order.  Creates .env if absent."""
    if not _ENV_PATH.exists():
        _ENV_PATH.write_text("")

    lines = _ENV_PATH.read_text().splitlines()
    written_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            new_lines.append(line)
            continue
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                written_keys.add(key)
                continue
        new_lines.append(line)

    # Append any keys not already present
    for key, value in updates.items():
        if key not in written_keys:
            new_lines.append(f"{key}={value}")

    _ENV_PATH.write_text("\n".join(new_lines) + "\n")
