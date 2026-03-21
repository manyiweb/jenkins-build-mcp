"""Helpers for loading KEY=VALUE environment files."""

from __future__ import annotations

from pathlib import Path
import os


def load_env_file(path: str | Path) -> None:
    """Load a simple dotenv-like file into process environment."""
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")
        if not separator:
            continue

        os.environ[key.strip()] = value.strip()
