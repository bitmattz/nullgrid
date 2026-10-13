"""Helpers shared by the nullgrid tests (conftest.py holds the fixtures)."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def write_config(paths, text: str) -> None:
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text(text)
