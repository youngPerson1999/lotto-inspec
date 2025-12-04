"""Lightweight .env loader for local development without Docker."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _parse_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    return key.strip(), _clean_value(value.strip())


def _clean_value(raw: str) -> str:
    if not raw:
        return ""
    quote_chars = {"'", '"'}
    if raw[0] in quote_chars and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def load_env_file(path: Path | None = None) -> None:
    """Populate os.environ with values from .env if not already set."""

    env_path = path or Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    lines: Iterable[str]
    with env_path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()

    for line in lines:
        parsed = _parse_line(line)
        if not parsed:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


__all__ = ["load_env_file"]
