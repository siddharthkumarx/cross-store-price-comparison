"""Collect: every compared retailer's catalog, then the day's GTIN probes.

Two phases inside one run, on one runner, sharing one run-wide pacer:

1. **Catalogs.** robots.txt, then every ``/products.json`` page (at most
   ``MAX_PAGES``). Products in an excluded category are dropped here; a retailer
   above the excluded share is stopped (D-007).
2. **Probes.** After all catalogs are in, the matchers say which products are
   worth a GTIN (:func:`crossprice.gtincache.plan_probes`); each probe reads the
   product ``.js`` (variant barcodes, and integer-cent prices that cross-check the
   catalog). One product page per retailer gives the USD currency proof.

Raw bodies are parsed and dropped; only slim product dicts survive.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from crossprice.gtin import normalize_gtin
from crossprice.normalize import slim_product
from crossprice.polite import RobotsDisallowed, StoreSession, StoreStopped
from crossprice.retailers import Retailer
from crossprice.screen import STORE_DROP_SHARE, is_excluded, screen_content
from crossprice.witness import (
    is_products_payload,
    jsonld_currencies,
    jsonld_gtins,
    price_to_cents,
    shopify_active_currency,
)

PAGE_LIMIT = 250
MAX_PAGES = 16
# A retailer's .js prices may differ from its catalog for a product that changed
# between the two requests; more than this share of compared variants is a mismatch.
WITNESS_MAX_DIFF_SHARE = 0.05

Status = Literal["ok", "failed", "mismatch", "excluded"]


@dataclass
class Probe:
    product_id: int
    handle: str
    status: str = "ok"  # ok | missing
    gtins: dict[int, str | None] = field(default_factory=dict)
    compared: int = 0
    price_diffs: int = 0
    jsonld_gtins: int = 0


@dataclass
class RetailerFetch:
    retailer_id: str
    host: str
    observed_at: datetime
    status: Status = "failed"
    reason: str | None = None
    products: list[dict[str, Any]] = field(default_factory=list)
    excluded_products: int = 0
    pages: int = 0
    probes: list[Probe] = field(default_factory=list)
    currencies: set[str] = field(default_factory=set)
    content_flags: dict[str, list[str]] = field(default_factory=dict)
    requests: int = 0
    retries: int = 0
    retry_causes: list[str] = field(default_factory=list)
    request_log: list[tuple[float, str, str]] = field(default_factory=list)
    elapsed_s: float = 0.0

    @property
    def complete(self) -> bool:
        return self.status == "ok"

    def report(self) -> dict[str, Any]:
        """Summary for runs.jsonl (no catalog content)."""
        compared = sum(p.compared for p in self.probes)
        return {
            "retailer_id": self.retailer_id,
            "host": self.host,
            "status": self.status,
            "reason": self.reason,
            "products": len(self.products),
            "variants": sum(len(p["variants"]) for p in self.products),
            "excluded_products": self.excluded_products,
            "pages": self.pages,
            "probes": len(self.probes),
            "probe_variants_with_gtin": sum(1 for p in self.probes for g in p.gtins.values() if g),
            "probe_variants": sum(len(p.gtins) for p in self.probes),
            "witness_compared": compared,
            "witness_price_diffs": sum(p.price_diffs for p in self.probes),
            "currencies": sorted(self.currencies),
            "content_flags": self.content_flags,
            "requests": self.requests,
            "retries": self.retries,
            "retry_causes": self.retry_causes,
            "request_log": [list(e) for e in self.request_log],
            "elapsed_s": self.elapsed_s,
        }


def _json(resp: httpx.Response) -> Any:
    try:
        return json.loads(resp.content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _bookkeeping(session: StoreSession, out: RetailerFetch, started: float) -> None:
    out.requests = session.requests_made
    out.retries = session.retries_made
    out.retry_causes = list(session.retry_causes)
    out.request_log = list(session.request_log)
    out.elapsed_s = round(out.elapsed_s + time.monotonic() - started, 1)


async def fetch_catalog(session: StoreSession, retailer: Retailer) -> RetailerFetch:
    """Phase 1 for one retailer. Never raises for retailer problems."""
    started = time.monotonic()
    out = RetailerFetch(retailer.id, retailer.host, datetime.now(UTC).replace(microsecond=0))
    try:
        await session.load_robots()
        if session.stopped_reason:
            out.reason = session.stopped_reason
        else:
            await _pages(session, retailer, out)
    except StoreStopped as exc:
        out.status, out.reason = "failed", exc.reason
    except RobotsDisallowed as exc:
        out.status, out.reason = "failed", f"robots.txt disallows {exc}"
    if out.status == "failed":
        out.products = []
    _bookkeeping(session, out, started)
    return out


async def _pages(session: StoreSession, retailer: Retailer, out: RetailerFetch) -> None:
    raw: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        resp = await session.get("/products.json", {"limit": PAGE_LIMIT, "page": page})
        out.pages = page
        data = _json(resp)
        if resp.status_code != 200 or not is_products_payload(data):
            out.reason = f"/products.json page {page}: http {resp.status_code}, not a catalog"
            return
        batch = [slim_product(p) for p in data["products"] if isinstance(p, dict)]
        raw.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
    else:
        out.reason = f"/products.json has more than {MAX_PAGES} pages"
        return
    reviewed = retailer.screen_reviewed
    flagged = [p for p in raw if is_excluded(p, reviewed)]
    out.content_flags = screen_content(flagged, reviewed_titles=reviewed)
    out.excluded_products = len(flagged)
    if raw and len(flagged) / len(raw) > STORE_DROP_SHARE:
        out.status = "excluded"
        out.reason = f"{len(flagged)} of {len(raw)} products in excluded categories: " + ", ".join(
            sorted(out.content_flags)
        )
        return
    out.products = [p for p in raw if not is_excluded(p, reviewed)]
    out.status = "ok"


async def _probe(session: StoreSession, product: dict[str, Any]) -> Probe:
    probe = Probe(product_id=int(product["id"]), handle=str(product["handle"]))
    resp = await session.get(f"/products/{probe.handle}.js")
    data = _json(resp)
    if resp.status_code != 200 or not isinstance(data, dict):
        probe.status = "missing"
        return probe
    catalog = {int(v["id"]): v for v in product["variants"] if isinstance(v.get("id"), int)}
    for v in data.get("variants") or []:
        vid = v.get("id")
        if not isinstance(vid, int):
            continue
        probe.gtins[vid] = normalize_gtin(v.get("barcode"))
        if vid in catalog:
            probe.compared += 1
            if v.get("price") != price_to_cents(catalog[vid].get("price")):
                probe.price_diffs += 1
    return probe


async def _currency_page(session: StoreSession, handle: str, out: RetailerFetch) -> None:
    resp = await session.get(f"/products/{handle}", expect="html")
    if resp.status_code != 200:
        return
    html = resp.text
    out.currencies |= jsonld_currencies(html)
    theme = shopify_active_currency(html)
    if theme:
        out.currencies.add(theme)
    if out.probes:
        out.probes[-1].jsonld_gtins = len(jsonld_gtins(html))


async def fetch_probes(
    session: StoreSession, out: RetailerFetch, product_ids: list[int], proof_handle: str | None
) -> None:
    """Phase 2 for one retailer: GTIN probes, the witness check and the currency proof."""
    if not out.complete:
        return
    started = time.monotonic()
    by_id = {int(p["id"]): p for p in out.products if p.get("id") and p.get("handle")}
    try:
        for pid in product_ids:
            if pid in by_id:
                out.probes.append(await _probe(session, by_id[pid]))
        if proof_handle:
            await _currency_page(session, proof_handle, out)
    except StoreStopped as exc:
        out.status, out.reason = "failed", exc.reason
    except RobotsDisallowed as exc:
        out.status, out.reason = "failed", f"robots.txt disallows {exc}"
    if out.status == "ok":
        compared = sum(p.compared for p in out.probes)
        diffs = sum(p.price_diffs for p in out.probes)
        if not out.currencies:
            out.status, out.reason = "failed", "no currency proof on the sampled product page"
        elif compared and diffs > max(1, WITNESS_MAX_DIFF_SHARE * compared):
            out.status = "mismatch"
            out.reason = f"product .js prices differ from the catalog on {diffs} of {compared}"
    if out.status == "failed":
        out.products = []
    _bookkeeping(session, out, started)
