"""Render README.md and the dataset card (data/README.md) from the latest real run.

    python -m crossprice.readme [--data data]

Run by the daily workflow after every run, so every number, sample row and
"what changed today" line matches the newest committed data. Templates live in
``templates/``; rendered files never contain template syntax, HTML comments or
placeholders (tests/test_readme.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from crossprice.retailers import load_retailers

ROOT = Path(__file__).resolve().parents[2]
EVENT_WORDS = {
    "price_down": ("price drop", "price drops"),
    "price_up": ("price rise", "price rises"),
    "new_lowest": ("new lowest-price store", "new lowest-price stores"),
    "out_of_stock": ("sold out at a store", "sold out at a store"),
    "back_in_stock": ("back in stock at a store", "back in stock at a store"),
}
COMPARISON_FIELDS = [
    (
        "product_key",
        "text",
        "The product's GTIN-14 barcode, or `M` + a stable id for a non-barcode match",
    ),
    ("brand", "text", "Brand, as the first store lists it"),
    ("product", "text", "Product name and option (shade, size), as the first store lists it"),
    ("gtin", "14 digits or empty", "GTIN-14 barcode when the match is barcode-verified"),
    (
        "match_tier",
        "text",
        "`gtin` (barcode), `mpn` (brand + part number) or `fuzzy` (brand + name)",
    ),
    ("match_confidence", "0 to 1", "Score of the weakest link in the match; 1.00 for barcode"),
    ("retailers", "integer", "Stores that sell the product"),
    ("retailers_in_stock", "integer", "Stores that have it in stock"),
    ("lowest_price_usd", "USD", "Lowest in-stock price (lowest of all when none is in stock)"),
    ("lowest_price_retailers", "text", "Store id(s) at the lowest price"),
    ("highest_price_usd", "USD", "Highest in-stock price"),
    (
        "spread_pct",
        "percent or empty",
        "(highest - lowest) / lowest x 100, in-stock prices, 2+ stores",
    ),
    ("<store>_price_usd", "USD or empty", "That store's price (one column per store)"),
    ("<store>_in_stock", "yes / no / empty", "That store's stock"),
    ("<store>_url", "URL or empty", "The product page at that store"),
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def incidents(path: Path) -> list[dict[str, str]]:
    """Headings and fix lines of docs/incidents.md."""
    if not path.exists():
        return []
    out: list[dict[str, str]] = []
    for block in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.MULTILINE)[1:]:
        head = block.splitlines()[0].strip()
        fix = re.search(r"\*\*Fix:\*\*\s*(.+?)(?:\n- \*\*|\Z)", block, re.DOTALL)
        what = re.search(r"\*\*What happened:\*\*\s*(.+?)(?:\n- \*\*|\Z)", block, re.DOTALL)
        out.append(
            {
                "id": head.split(" - ")[0],
                "title": head.split(" - ", 1)[-1],
                "what": " ".join(what.group(1).split()) if what else "",
                "fix": " ".join(fix.group(1).split()) if fix else "",
            }
        )
    return out


def change_summary(rows: list[dict[str, str]]) -> str:
    counts = Counter(r["event"] for r in rows)
    parts = []
    for key, (one, many) in EVENT_WORDS.items():
        n = counts.get(key, 0)
        if n:
            parts.append(f"{n:,} {one if n == 1 else many}")
    return ", ".join(parts) if parts else "no changes on the compared products"


def sample_rows(
    rows: list[dict[str, str]], names: dict[str, str], n: int = 5
) -> list[dict[str, Any]]:
    """Real rows for the README: most stores first, barcode matches first, then the widest gaps."""

    def key(r: dict[str, str]) -> tuple[int, bool, float]:
        return (
            int(r["retailers_in_stock"]),
            r["match_tier"] == "gtin",
            float(r["spread_pct"] or 0),
        )

    picked = sorted((r for r in rows if r["spread_pct"]), key=key, reverse=True)[:n]
    out = []
    for r in picked:
        lows = [names.get(x, x) for x in r["lowest_price_retailers"].split()]
        out.append({**r, "lowest_names": ", ".join(lows)})
    return out


def context(data: Path, root: Path = ROOT) -> dict[str, Any]:
    public = yaml.safe_load((root / "config" / "public.yml").read_text(encoding="utf-8"))
    retailers = load_retailers(root / "config" / "retailers.yml")
    names = {r.id: r.name for r in retailers}
    runs = [json.loads(x) for x in (data / "runs.jsonl").read_text().splitlines() if x]
    good = [r for r in runs if r["status"] in ("ok", "partial")]
    last, last_good = runs[-1], good[-1]
    status = json.loads((data / "status.json").read_text())
    comparison = _read_csv(data / "latest" / "comparison.csv")
    day = last_good["started_at"][:10]
    changes = _read_csv(data / "changes" / day[:4] / f"{day}.csv")
    precision_path = data / "precision" / "latest.json"
    precision = json.loads(precision_path.read_text()) if precision_path.exists() else None
    comp = last_good["comparison"]
    repo_url = f"https://github.com/{public['repo']}"
    blob = f"{repo_url}/blob/{public['branch']}"
    first = runs[0]["started_at"][:10]
    vertical = retailers[0].vertical.replace("-", " ") if retailers else ""
    return {
        "pub": public,
        "repo_url": repo_url,
        "blob": blob,
        "badge": f"https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/{public['repo']}/{public['branch']}/data/badges",
        "last": last,
        "lg": last_good,
        "status": status,
        "comp": comp,
        "precision": precision,
        "precision_file": f"{blob}/data/precision/{day[:4]}/{day}.json",
        "retailers": retailers,
        "names": names,
        "vertical": vertical,
        "day": day,
        "first_day": first,
        "rows": sample_rows(comparison, names),
        "changes": changes[:6],
        "change_count": len(changes),
        "change_summary": change_summary(changes),
        "checks": last_good.get("checks", []),
        "incidents": incidents(root / "docs" / "incidents.md"),
        "fields": COMPARISON_FIELDS,
        "example": comparison[0] if comparison else {},
    }


def render(template: Path, ctx: dict[str, Any]) -> str:
    # Markdown, not HTML: autoescaping would corrupt it. Table cells use the `md` filter.
    env = Environment(
        loader=FileSystemLoader(str(template.parent)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701  (Markdown output, see above)
    )
    env.filters["md"] = lambda v: str(v).replace("|", "\\|")
    env.filters["usd"] = lambda v: f"${float(v):,.2f}" if v not in ("", None) else ""
    env.filters["n"] = lambda v: f"{int(v):,}"
    text = env.get_template(template.name).render(**ctx)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=ROOT / "data")
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args(argv)
    ctx = context(a.data, a.root)
    out = a.out or a.root
    targets = {"README.md.j2": out / "README.md", "DATASET_CARD.md.j2": a.data / "README.md"}
    for name, target in targets.items():
        source = a.root / "templates" / name
        if source.exists():
            target.write_text(render(source, ctx), encoding="utf-8")
            print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
