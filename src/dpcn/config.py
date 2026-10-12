"""Load config/*.yaml and .env into one Config object."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import yaml
from dotenv import load_dotenv


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: this file) to the directory holding pyproject.toml."""
    here = (start or Path(__file__)).resolve()
    for d in [here, *here.parents]:
        if (d / "pyproject.toml").exists() and (d / "config").is_dir():
            return d
    raise FileNotFoundError("Could not find repo root (pyproject.toml + config/)")


def _ns(obj):
    """Recursively turn dicts into SimpleNamespace for attribute access."""
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_ns(v) for v in obj]
    return obj


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Config:
    def __init__(self, root: Path | None = None):
        self.root = root or find_root()
        load_dotenv(self.root / ".env")

        settings = _load_yaml(self.root / "config" / "settings.yaml")
        insts = _load_yaml(self.root / "config" / "institutions.yaml")
        self.rules = _load_yaml(self.root / "config" / "cluster_rules.yaml")

        self.window = _ns(settings["window"])
        self.openalex = _ns(settings["openalex"])
        self.work_filter = _ns(settings["work_filter"])
        self.matching = _ns(settings["matching"])
        self.networks = _ns(settings["networks"])
        self.connections = _ns(settings["connections"])
        self.quartile = _ns(settings["quartile"])
        self.verify = _ns(settings["verify"])
        self.paths = SimpleNamespace(**{k: self.root / v for k, v in settings["paths"].items()})

        self.group: int = insts["group"]
        self.cluster_label: str = insts["cluster_label"]
        self.labs: list[dict] = insts["institutions"]
        self.lab_ids: set[str] = {lab["openalex_id"] for lab in self.labs}
        self.lab_by_id: dict[str, dict] = {lab["openalex_id"]: lab for lab in self.labs}
        self.lab_by_short: dict[str, dict] = {lab["short"]: lab for lab in self.labs}

        self.api_key: str = os.getenv("OPENALEX_API_KEY", "").strip()
        self.email: str = os.getenv("OPENALEX_EMAIL", "").strip()

    def path(self, *parts: str) -> Path:
        """Absolute path under the repo root."""
        return self.root.joinpath(*parts)

    @property
    def year_filter(self) -> str:
        return f"publication_year:{self.window.start}-{self.window.end}"


def load_config(root: Path | None = None) -> Config:
    return Config(root)
