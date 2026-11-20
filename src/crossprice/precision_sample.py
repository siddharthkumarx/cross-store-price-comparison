"""Draw the manual-check sample of compared pairs (docs/precision.md).

    python -m crossprice.precision_sample --data data --out docs/manual-checks/2026-11-24.csv

One pair per compared product (its first two retailers by id), products that are
not barcode-verified first, then barcode products, in a stable pseudo-random order
seeded by the run id, so the same run always gives the same sample. The ``verdict``
and ``reason`` columns are filled in by the person who checks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

COLUMNS = [
    "n",
    "product_key",
    "match_tier",
    "match_confidence",
    "brand",
    "retailer_a",
    "title_a",
    "variant_a",
    "sku_a",
    "price_a_usd",
    "retailer_b",
    "title_b",
    "variant_b",
    "sku_b",
    "price_b_usd",
    "verdict",
    "reason",
]


def _variant(url: str) -> int | None:
    values = parse_qs(urlsplit(url).query).get("variant")
    return int(values[0]) if values else None


def draw(data: Path, n: int = 100) -> tuple[str, list[dict[str, str]]]:
    runs = [json.loads(x) for x in (data / "runs.jsonl").read_text().splitlines() if x]
    run_id = next(r["run_id"] for r in reversed(runs) if r["status"] in ("ok", "partial"))
    with (data / "latest" / "offers.csv").open(encoding="utf-8", newline="") as fh:
        offers = {(r["retailer_id"], int(r["variant_id"])): r for r in csv.DictReader(fh)}
    with (data / "latest" / "comparison.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    def key(row: dict[str, str]) -> str:
        return hashlib.sha256(f"{run_id}|{row['product_key']}".encode()).hexdigest()

    rows.sort(key=lambda r: (r["match_tier"] == "gtin", key(r)))
    out: list[dict[str, str]] = []
    for row in rows:
        members = sorted(
            k.removesuffix("_url") for k, v in row.items() if k.endswith("_url") and v
        )[:2]
        if len(members) < 2:
            continue
        sides = []
        for rid in members:
            vid = _variant(row[f"{rid}_url"])
            sides.append((rid, offers.get((rid, vid or 0), {})))
        (ra, a), (rb, b) = sides
        out.append(
            {
                "n": str(len(out) + 1),
                "product_key": row["product_key"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "brand": row["brand"],
                "retailer_a": ra,
                "title_a": a.get("product_title", ""),
                "variant_a": a.get("variant_title", ""),
                "sku_a": a.get("sku", ""),
                "price_a_usd": row[f"{ra}_price_usd"],
                "retailer_b": rb,
                "title_b": b.get("product_title", ""),
                "variant_b": b.get("variant_title", ""),
                "sku_b": b.get("sku", ""),
                "price_b_usd": row[f"{rb}_price_usd"],
                "verdict": "",
                "reason": "",
            }
        )
        if len(out) >= n:
            break
    return run_id, out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    run_id, rows = draw(a.data, a.n)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"run {run_id}: {len(rows)} pairs written to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
