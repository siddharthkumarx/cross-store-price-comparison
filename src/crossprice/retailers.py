"""The compared retailer list (config/retailers.yml, generated from recon evidence)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Retailer:
    id: str
    name: str
    vertical: str
    host: str
    screen_reviewed: frozenset[str] = frozenset()

    @property
    def base_url(self) -> str:
        return f"https://{self.host}"

    def product_url(self, handle: str, variant_id: int | None = None) -> str:
        url = f"{self.base_url}/products/{handle}"
        return f"{url}?variant={variant_id}" if variant_id else url


def load_retailers(path: Path) -> list[Retailer]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    retailers = [
        Retailer(
            id=str(r["id"]),
            name=str(r["name"]),
            vertical=str(r["vertical"]),
            host=str(r["host"]),
            screen_reviewed=frozenset(str(t) for t in r.get("screen_reviewed") or []),
        )
        for r in raw["retailers"]
    ]
    ids = [r.id for r in retailers]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate retailer ids in retailers.yml")
    return retailers
