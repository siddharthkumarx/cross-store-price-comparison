"""Compare matched products across retailers (docs/decisions.md D-012, D-013).

Facts only: prices, stock, lowest price and spread as numbers.
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from crossprice.match import Product
from crossprice.models import OfferRow
from crossprice.retailers import Retailer

DEMO_BAND_PCT = 5.0


@dataclass
class ComparisonRow:
    product_key: str
    brand: str
    product: str
    gtin14: str | None
    match_tier: str
    match_confidence: float
    offers: dict[str, OfferRow]  # retailer id -> offer

    @property
    def in_stock(self) -> dict[str, OfferRow]:
        return {r: o for r, o in self.offers.items() if o.available}

    @property
    def priced(self) -> dict[str, OfferRow]:
        """The offers the lowest price is taken from: in stock, or all when none is."""
        return self.in_stock or self.offers

    @property
    def lowest_cents(self) -> int:
        return min(o.price_cents for o in self.priced.values())

    @property
    def highest_cents(self) -> int:
        return max(o.price_cents for o in self.priced.values())

    @property
    def lowest_retailers(self) -> list[str]:
        low = self.lowest_cents
        return sorted(r for r, o in self.priced.items() if o.price_cents == low)

    @property
    def spread_pct(self) -> float | None:
        """(highest - lowest) / lowest x 100 over in-stock offers; None with fewer than 2."""
        stock = self.in_stock
        if len(stock) < 2:
            return None
        prices = [o.price_cents for o in stock.values()]
        return round((max(prices) - min(prices)) / min(prices) * 100, 1)


def display_name(offer: OfferRow) -> str:
    name = offer.product_title
    if offer.options:
        name += " - " + " / ".join(offer.options)
    return name


def build(
    products: Sequence[Product], offers: Mapping[tuple[str, int], OfferRow]
) -> list[ComparisonRow]:
    rows: list[ComparisonRow] = []
    for p in products:
        members = {rid: offers[key] for rid, key in p.members.items() if key in offers}
        if len(members) < 2:
            continue
        # The name and brand shown come from the first retailer (by id) that lists it.
        first = members[sorted(members)[0]]
        rows.append(
            ComparisonRow(
                product_key=p.key,
                brand=first.brand,
                product=display_name(first),
                gtin14=p.gtin14,
                match_tier=p.tier,
                match_confidence=p.confidence,
                offers=dict(sorted(members.items())),
            )
        )
    rows.sort(key=lambda r: (r.brand.lower(), r.product.lower(), r.product_key))
    return rows


def dollars(cents: int | None) -> str:
    return "" if cents is None else f"{cents / 100:.2f}"


def columns(retailers: Sequence[Retailer]) -> list[str]:
    cols = [
        "product_key",
        "brand",
        "product",
        "gtin",
        "match_tier",
        "match_confidence",
        "retailers",
        "retailers_in_stock",
        "lowest_price_usd",
        "lowest_price_retailers",
        "highest_price_usd",
        "spread_pct",
    ]
    for r in retailers:
        cols += [f"{r.id}_price_usd", f"{r.id}_in_stock", f"{r.id}_url"]
    return cols


def to_csv_rows(
    rows: Sequence[ComparisonRow], retailers: Sequence[Retailer]
) -> list[dict[str, Any]]:
    by_id = {r.id: r for r in retailers}
    out: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {
            "product_key": row.product_key,
            "brand": row.brand,
            "product": row.product,
            "gtin": row.gtin14 or "",
            "match_tier": row.match_tier,
            "match_confidence": f"{row.match_confidence:.2f}",
            "retailers": len(row.offers),
            "retailers_in_stock": len(row.in_stock),
            "lowest_price_usd": dollars(row.lowest_cents),
            "lowest_price_retailers": " ".join(row.lowest_retailers),
            "highest_price_usd": dollars(row.highest_cents),
            "spread_pct": "" if row.spread_pct is None else f"{row.spread_pct:.1f}",
        }
        for rid, o in row.offers.items():
            item[f"{rid}_price_usd"] = dollars(o.price_cents)
            item[f"{rid}_in_stock"] = "yes" if o.available else "no"
            item[f"{rid}_url"] = by_id[rid].product_url(o.handle, o.variant_id)
        out.append(item)
    return out


def write_csv(rows: Sequence[ComparisonRow], retailers: Sequence[Retailer], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns(retailers), lineterminator="\n")
        w.writeheader()
        w.writerows(to_csv_rows(rows, retailers))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def avg_spread(rows: Sequence[ComparisonRow]) -> float | None:
    spreads = [r.spread_pct for r in rows if r.spread_pct is not None]
    return round(statistics.fmean(spreads), 1) if spreads else None


def price_index(rows: Sequence[ComparisonRow], retailer_id: str) -> dict[str, Any]:
    """The demo: one retailer's prices against the median of the others (D-013).

    Uses products where the retailer and at least one other retailer are in stock.
    Index = price / median price of the other retailers x 100.
    """
    ratios: list[tuple[ComparisonRow, float, int, int]] = []
    for row in rows:
        stock = row.in_stock
        mine = stock.get(retailer_id)
        others = [o.price_cents for r, o in stock.items() if r != retailer_id]
        if mine is None or not others:
            continue
        market = statistics.median(others)
        ratios.append((row, mine.price_cents / market, mine.price_cents, round(market)))
    by_brand: dict[str, list[float]] = defaultdict(list)
    for row, ratio, _, _ in ratios:
        by_brand[row.brand].append(ratio)

    def item(row: ComparisonRow, ratio: float, mine: int, market: int) -> dict[str, Any]:
        return {
            "product_key": row.product_key,
            "brand": row.brand,
            "product": row.product,
            "price_usd": dollars(mine),
            "market_median_usd": dollars(market),
            "difference_pct": round((ratio - 1) * 100, 1),
            "retailers": len(row.in_stock),
        }

    above = [item(*r) for r in ratios if (r[1] - 1) * 100 > DEMO_BAND_PCT]
    below = [item(*r) for r in ratios if (r[1] - 1) * 100 < -DEMO_BAND_PCT]
    above.sort(key=lambda x: (-x["difference_pct"], x["product"]))
    below.sort(key=lambda x: (x["difference_pct"], x["product"]))
    return {
        "retailer_id": retailer_id,
        "products_shared": len(ratios),
        "index": round(statistics.median(r[1] for r in ratios) * 100, 1) if ratios else None,
        "within_band": len(ratios) - len(above) - len(below),
        "by_brand": sorted(
            (
                {
                    "brand": brand,
                    "products": len(vals),
                    "index": round(statistics.median(vals) * 100, 1),
                }
                for brand, vals in by_brand.items()
            ),
            key=lambda x: (-x["products"], x["brand"]),
        ),
        "above": above,
        "below": below,
    }


CHANGE_COLUMNS = [
    "observed_at",
    "product_key",
    "brand",
    "product",
    "event",
    "retailer_id",
    "old_value",
    "new_value",
    "change_pct",
]


def changes(
    previous: Sequence[Mapping[str, str]],
    current: Sequence[ComparisonRow],
    observed_at: str,
) -> list[dict[str, Any]]:
    """Changes on compared products since the previous comparison.

    ``price_up`` / ``price_down`` per retailer, ``out_of_stock`` / ``back_in_stock``
    per retailer, and ``new_lowest`` when the set of lowest-price retailers changes.
    Products new to (or gone from) the comparison raise no event.
    """
    prev = {r["product_key"]: r for r in previous}
    out: list[dict[str, Any]] = []
    for row in current:
        old = prev.get(row.product_key)
        if old is None:
            continue
        base = {
            "observed_at": observed_at,
            "product_key": row.product_key,
            "brand": row.brand,
            "product": row.product,
        }
        for rid, o in row.offers.items():
            old_price = old.get(f"{rid}_price_usd") or ""
            if not old_price:
                continue
            old_cents = round(float(old_price) * 100)
            if o.price_cents != old_cents:
                out.append(
                    {
                        **base,
                        "event": "price_up" if o.price_cents > old_cents else "price_down",
                        "retailer_id": rid,
                        "old_value": old_price,
                        "new_value": dollars(o.price_cents),
                        "change_pct": f"{(o.price_cents - old_cents) / old_cents * 100:.1f}",
                    }
                )
            was = old.get(f"{rid}_in_stock")
            now = "yes" if o.available else "no"
            if was in ("yes", "no") and was != now:
                out.append(
                    {
                        **base,
                        "event": "out_of_stock" if now == "no" else "back_in_stock",
                        "retailer_id": rid,
                        "old_value": was,
                        "new_value": now,
                        "change_pct": "",
                    }
                )
        new_low = " ".join(row.lowest_retailers)
        old_low = old.get("lowest_price_retailers", "")
        if old_low and new_low != old_low:
            out.append(
                {
                    **base,
                    "event": "new_lowest",
                    "retailer_id": new_low,
                    "old_value": old_low,
                    "new_value": new_low,
                    "change_pct": "",
                }
            )
    return out
