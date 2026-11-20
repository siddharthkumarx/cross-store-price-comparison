"""Turn raw Shopify catalog JSON into validated :class:`OfferRow` objects.

Reused from F1 (its D-007, D-018), extended with brand, SKU, options and GTIN:

* Prices: decimal strings to integer cents (no floats anywhere).
* Times: one UTC ``observed_at`` per retailer fetch.
* ``compare_at_price`` below the price is a stale merchant value: dropped and counted.
* $0 variants (free gifts, samples, add-ons) are out of scope and counted as ``free``.
* GTINs come from the cache (product ``.js`` barcodes), never from ``/products.json``.
* Rows that still fail validation are rejected and counted, never repaired.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from crossprice.models import OfferRow
from crossprice.screen import is_excluded
from crossprice.witness import price_to_cents

MAX_EXAMPLES = 5

# Fields kept from /products.json. Everything else (body_html, images, media,
# timestamps) is discarded as soon as the page is parsed.
PRODUCT_FIELDS = ("id", "handle", "title", "vendor", "product_type", "tags")
VARIANT_FIELDS = (
    "id",
    "title",
    "option1",
    "option2",
    "option3",
    "sku",
    "price",
    "compare_at_price",
    "available",
)


def slim_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields the pipeline uses (no descriptions, no images)."""
    product = {k: raw.get(k) for k in PRODUCT_FIELDS}
    product["variants"] = [
        {k: v.get(k) for k in VARIANT_FIELDS}
        for v in raw.get("variants") or []
        if isinstance(v, dict)
    ]
    return product


@dataclass
class NormalizeStats:
    rows: int = 0
    free: int = 0
    excluded: int = 0
    rejected: int = 0
    compare_at_ignored: int = 0
    examples: list[str] = field(default_factory=list)

    def reject(self, message: str) -> None:
        self.rejected += 1
        if len(self.examples) < MAX_EXAMPLES:
            self.examples.append(message[:200])


_AVAILABILITY: dict[object, str] = {True: "in_stock", False: "out_of_stock"}


def _text(value: Any, limit: int = 255) -> str:
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


def _options(variant: dict[str, Any]) -> tuple[str, ...]:
    values = [_text(variant.get(k)) for k in ("option1", "option2", "option3")]
    return tuple(v for v in values if v and v.lower() != "default title")


def normalize_products(
    retailer_id: str,
    products: list[dict[str, Any]],
    observed_at: datetime,
    gtins: Mapping[int, str] | None = None,
    reviewed_titles: frozenset[str] = frozenset(),
) -> tuple[list[OfferRow], NormalizeStats]:
    """Validated offers for one retailer. ``gtins`` maps variant id to a cached GTIN-14."""
    gtins = gtins or {}
    stats = NormalizeStats()
    rows: list[OfferRow] = []
    seen: set[int] = set()
    for product in products:
        if is_excluded(product, reviewed_titles):
            stats.excluded += len(product.get("variants") or [])
            continue
        for variant in product.get("variants") or []:
            price = price_to_cents(variant.get("price"))
            if price == 0:
                stats.free += 1
                continue
            compare_at = price_to_cents(variant.get("compare_at_price"))
            if compare_at is not None and price is not None and compare_at < price:
                compare_at = None
                stats.compare_at_ignored += 1
            if compare_at == 0:
                compare_at = None
            available = variant.get("available")
            vid = variant.get("id")
            try:
                row = OfferRow.model_validate(
                    {
                        "retailer_id": retailer_id,
                        "product_id": product.get("id"),
                        "variant_id": vid,
                        "handle": product.get("handle"),
                        "brand": _text(product.get("vendor")),
                        "product_type": _text(product.get("product_type")),
                        "product_title": _text(product.get("title")),
                        "variant_title": _text(variant.get("title")),
                        "options": _options(variant),
                        "sku": _text(variant.get("sku")),
                        "gtin14": gtins.get(vid) if isinstance(vid, int) else None,
                        "price_cents": price,
                        "compare_at_cents": compare_at,
                        "availability": _AVAILABILITY.get(available, available),
                        "observed_at": observed_at,
                    }
                )
            except ValidationError as exc:
                first = exc.errors()[0]
                where = ".".join(str(p) for p in first["loc"]) or "row"
                stats.reject(f"variant {vid}: {where}: {first['msg']}")
                continue
            if row.variant_id in seen:
                stats.reject(f"variant {row.variant_id}: duplicate variant id")
                continue
            seen.add(row.variant_id)
            rows.append(row)
    stats.rows = len(rows)
    return rows, stats
