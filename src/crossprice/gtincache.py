"""The GTIN cache and the daily probe plan (docs/decisions.md D-010).

Barcodes are not in ``/products.json``; each costs one product ``.js`` request.
A product is probed once and its variants' GTINs are cached in
``data/gtin/cache.csv`` with the date. Each run spends at most ``GTIN_BUDGET``
probes per retailer, in this order:

1. products another matcher pairs with a product elsewhere, never probed
   (best candidate score first);
2. probed products that are compared today and whose entry is older than
   ``REFRESH_DAYS`` (oldest first);
3. never-probed products of brands that at least one other retailer also sells
   (stable pseudo-random order, so the cache fills evenly over the days);
4. any other entry older than ``REFRESH_DAYS`` (oldest first).
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

GTIN_BUDGET = 20
REFRESH_DAYS = 7
COLUMNS = ("retailer_id", "product_id", "variant_id", "gtin14", "source", "fetched_on")


@dataclass
class Entry:
    gtin14: str | None
    source: str
    fetched_on: date


@dataclass
class GtinCache:
    # (retailer, product) -> {variant id -> entry}
    products: dict[tuple[str, int], dict[int, Entry]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> GtinCache:
        cache = cls()
        if not path.exists():
            return cache
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                key = (r["retailer_id"], int(r["product_id"]))
                cache.products.setdefault(key, {})[int(r["variant_id"])] = Entry(
                    gtin14=r["gtin14"] or None,
                    source=r["source"],
                    fetched_on=date.fromisoformat(r["fetched_on"]),
                )
        return cache

    def save(self, path: Path, keep_retailers: Iterable[str] | None = None) -> None:
        keep = set(keep_retailers) if keep_retailers is not None else None
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(COLUMNS)
            for (rid, pid), variants in sorted(self.products.items()):
                if keep is not None and rid not in keep:
                    continue
                for vid, e in sorted(variants.items()):
                    w.writerow([rid, pid, vid, e.gtin14 or "", e.source, e.fetched_on.isoformat()])

    def gtins(self, retailer_id: str) -> dict[int, str]:
        return {
            vid: e.gtin14
            for (rid, _), variants in self.products.items()
            if rid == retailer_id
            for vid, e in variants.items()
            if e.gtin14
        }

    def fetched_on(self, retailer_id: str, product_id: int) -> date | None:
        variants = self.products.get((retailer_id, product_id))
        if not variants:
            return None
        return min(e.fetched_on for e in variants.values())

    def update(
        self,
        retailer_id: str,
        product_id: int,
        gtins: Mapping[int, str | None],
        source: str,
        day: date,
    ) -> None:
        """Replace a product's entries with a fresh probe (every variant, GTIN or not)."""
        self.products[(retailer_id, product_id)] = {
            vid: Entry(gtin14=g, source=source, fetched_on=day) for vid, g in gtins.items()
        }

    def stats(self) -> dict[str, int]:
        variants = [e for v in self.products.values() for e in v.values()]
        return {
            "products_probed": len(self.products),
            "variants": len(variants),
            "variants_with_gtin": sum(1 for e in variants if e.gtin14),
        }


def _stable(retailer_id: str, product_id: int) -> str:
    return hashlib.sha256(f"gtin|{retailer_id}|{product_id}".encode()).hexdigest()


def plan_probes(
    retailer_id: str,
    product_ids: Iterable[int],
    candidate_scores: Mapping[int, float],
    compared: set[int],
    shared_brand: set[int],
    cache: GtinCache,
    day: date,
    budget: int = GTIN_BUDGET,
) -> list[int]:
    """Product ids to probe today for one retailer, at most ``budget``, in priority order."""
    stale_before = day - timedelta(days=REFRESH_DAYS)
    tiers: list[list[tuple[object, int]]] = [[], [], [], []]
    for pid in set(product_ids):
        when = cache.fetched_on(retailer_id, pid)
        if when is None:
            if pid in candidate_scores:
                tiers[0].append((-candidate_scores[pid], pid))
            elif pid in shared_brand:
                tiers[2].append((_stable(retailer_id, pid), pid))
        elif when <= stale_before:
            tiers[1 if pid in compared else 3].append((when.toordinal(), pid))
    out: list[int] = []
    for tier in tiers:
        for _, pid in sorted(tier, key=lambda x: (x[0], x[1])):
            if len(out) >= budget:
                return out
            out.append(pid)
    return out
