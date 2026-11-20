"""Recon: which US multi-brand Shopify retailers can be compared, and in which vertical.

Two check types, both run on GitHub Actions (docs/decisions.md D-003):

``recon`` (stage 1, at most 6 requests per candidate)
    robots.txt, ``/products.json`` page 1, ``/meta.json`` (shop country, currency,
    published product count), the product ``.js`` of 2 sampled products (barcodes)
    and one product page (JSON-LD currency proof and GTIN fields).

``catalog`` (stage 2, a fixed page cap per retailer)
    robots.txt, every ``/products.json`` page up to ``max_pages``, product ``.js``
    probes (a stable random sample per retailer plus named handles) and one
    product page. Writes the catalog identifiers (no descriptions, no images) so
    overlap and GTIN coverage can be measured offline.

Nothing but identifiers, prices and availability is kept.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from crossprice.gtin import gtin_problem, normalize_gtin
from crossprice.polite import (
    EdgeGuard,
    PoliteConfig,
    RobotsDisallowed,
    StoreSession,
    StoreStopped,
    make_client,
)
from crossprice.screen import STORE_DROP_SHARE, is_excluded, screen_content
from crossprice.witness import (
    is_products_payload,
    jsonld_currencies,
    jsonld_gtins,
    price_to_cents,
    shopify_active_currency,
)

PAGE_LIMIT = 250
JS_SAMPLES = 2
TOP_VENDORS = 60
# A retailer counts as multi-brand when page 1 shows at least this many vendors
# and no single vendor holds more than MAX_VENDOR_SHARE of its products.
MIN_VENDORS = 5
MAX_VENDOR_SHARE = 0.5


@dataclass(frozen=True)
class Candidate:
    store: str
    domain: str
    vertical: str

    @property
    def store_id(self) -> str:
        return slug(self.store)


def slug(text: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def stable_pick(items: list[dict[str, Any]], salt: str, n: int) -> list[dict[str, Any]]:
    """A reproducible pseudo-random sample (no RNG state, same input gives same output)."""

    def key(p: dict[str, Any]) -> str:
        return hashlib.sha256(f"{salt}|{p.get('id')}".encode()).hexdigest()

    eligible = [p for p in items if p.get("variants") and p.get("handle") and p.get("id")]
    return sorted(eligible, key=key)[:n]


@dataclass
class JsProbe:
    handle: str
    variants: int = 0
    barcodes_present: int = 0
    gtins_valid: int = 0
    problems: dict[str, int] = field(default_factory=dict)
    price_match: bool | None = None
    status: str = "ok"  # ok | http <code> | robots | not json
    gtins: dict[str, str] = field(default_factory=dict)  # variant id -> GTIN-14


@dataclass
class ReconResult:
    store: str
    domain: str
    vertical: str
    store_id: str = ""
    host: str = ""
    robots_status: str = "not-fetched"
    robots_products_json: bool | None = None
    robots_product_js: bool | None = None
    robots_product_page: bool | None = None
    crawl_delay_s: float | None = None
    reachable: bool = False
    stopped_reason: str | None = None
    shopify: bool = False
    meta_country: str | None = None
    meta_currency: str | None = None
    meta_products: int | None = None
    page1_products: int = 0
    page1_variants: int = 0
    vendor_count: int = 0
    top_vendor_share: float | None = None
    vendors: dict[str, int] = field(default_factory=dict)
    sku_share: float | None = None
    excluded_share: float | None = None
    content_flags: dict[str, list[str]] = field(default_factory=dict)
    js_probes: list[JsProbe] = field(default_factory=list)
    jsonld_currency: list[str] = field(default_factory=list)
    jsonld_gtin_fields: int = 0
    shopify_currency: str | None = None
    requests: int = 0
    retries: int = 0
    retry_causes: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def currency_usd(self) -> bool:
        seen = set(self.jsonld_currency)
        if self.shopify_currency:
            seen.add(self.shopify_currency)
        return seen == {"USD"}

    @property
    def gtin_variant_share(self) -> float | None:
        total = sum(p.variants for p in self.js_probes if p.status == "ok")
        if not total:
            return None
        return round(sum(p.gtins_valid for p in self.js_probes if p.status == "ok") / total, 3)

    def verdict(self) -> tuple[bool, list[str]]:
        """Whether the retailer passes stage 1, with every reason it fails."""
        fails: list[str] = []
        if self.stopped_reason and self.stopped_reason.startswith("run halted"):
            fails.append("not checked (run halted)")
        elif self.stopped_reason and not self.reachable:
            fails.append("blocked or challenged")
        elif self.robots_status == "unreachable":
            fails.append("robots.txt unreachable")
        elif not (self.robots_products_json and self.robots_product_js):
            fails.append("robots disallows a path we use")
        elif not self.reachable:
            fails.append("unreachable")
        elif not self.shopify:
            fails.append("not shopify")
        else:
            if self.stopped_reason:
                fails.append("blocked mid-recon")
            if not self.page1_products:
                fails.append("empty catalog")
            if self.meta_country and self.meta_country != "US":
                fails.append(f"shop country {self.meta_country}")
            if not self.currency_usd:
                fails.append("currency not proven USD")
            if self.vendor_count < MIN_VENDORS or (self.top_vendor_share or 0) > MAX_VENDOR_SHARE:
                fails.append("single-brand store")
            if self.excluded_share is not None and self.excluded_share > STORE_DROP_SHARE:
                fails.append("excluded category: " + ", ".join(sorted(self.content_flags)))
            if any(p.price_match is False for p in self.js_probes):
                fails.append("witness mismatch")
        if any(cause.startswith("http 429") for cause in self.retry_causes):
            fails.append("needed 429 retries")
        return (not fails, fails)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        passed, fails = self.verdict()
        data["gtin_variant_share"] = self.gtin_variant_share
        data["passed"] = passed
        data["fail_reasons"] = fails
        return data


def _json_or_none(resp: httpx.Response, *, any_type: bool = False) -> Any:
    """Decode JSON; ``any_type`` also accepts product ``.js`` (served as JavaScript)."""
    if not any_type and "json" not in resp.headers.get("content-type", ""):
        return None
    try:
        return json.loads(resp.content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


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


def slim(raw: dict[str, Any]) -> dict[str, Any]:
    """Identifiers, prices and availability only (no body_html, no images)."""
    product = {k: raw.get(k) for k in PRODUCT_FIELDS}
    product["variants"] = [
        {k: v.get(k) for k in VARIANT_FIELDS}
        for v in raw.get("variants") or []
        if isinstance(v, dict)
    ]
    return product


def catalog_stats(res: ReconResult, products: list[dict[str, Any]]) -> None:
    """Vendor mix, SKU coverage and content screen over the slim products."""
    vendors = Counter(
        (p.get("vendor") or "").strip() for p in products if (p.get("vendor") or "").strip()
    )
    res.vendor_count = len(vendors)
    res.vendors = dict(vendors.most_common(TOP_VENDORS))
    res.top_vendor_share = (
        round(vendors.most_common(1)[0][1] / len(products), 3) if vendors and products else None
    )
    variants = [v for p in products for v in p["variants"]]
    if variants:
        with_sku = sum(1 for v in variants if str(v.get("sku") or "").strip())
        res.sku_share = round(with_sku / len(variants), 3)
    res.content_flags = screen_content(products)
    if products:
        res.excluded_share = round(sum(1 for p in products if is_excluded(p)) / len(products), 3)


async def probe_js(session: StoreSession, product: dict[str, Any] | None, handle: str) -> JsProbe:
    """Fetch ``/products/<handle>.js``: barcodes and the price cross-check."""
    probe = JsProbe(handle=handle)
    try:
        resp = await session.get(f"/products/{handle}.js")
    except RobotsDisallowed:
        probe.status = "robots"
        return probe
    data = _json_or_none(resp, any_type=True)
    if resp.status_code != 200 or not isinstance(data, dict):
        probe.status = f"http {resp.status_code}" if resp.status_code != 200 else "not json"
        return probe
    variants = [v for v in data.get("variants") or [] if isinstance(v, dict)]
    probe.variants = len(variants)
    problems: Counter[str] = Counter()
    for v in variants:
        raw = v.get("barcode")
        if raw not in (None, ""):
            probe.barcodes_present += 1
        problem = gtin_problem(raw)
        problems[problem] += 1
        gtin = normalize_gtin(raw)
        if gtin and "id" in v:
            probe.gtins_valid += 1
            probe.gtins[str(v["id"])] = gtin
    probe.problems = dict(problems)
    if product is not None:
        catalog = {
            int(v["id"]): price_to_cents(v.get("price")) for v in product["variants"] if v.get("id")
        }
        js = {int(v["id"]): v.get("price") for v in variants if "id" in v}
        shared = catalog.keys() & js.keys()
        if shared:
            probe.price_match = all(catalog[k] == js[k] for k in shared)
    return probe


async def product_page(session: StoreSession, res: ReconResult, handle: str) -> None:
    if not session.allowed(f"/products/{handle}"):
        res.notes.append("robots disallows product page")
        return
    resp = await session.get(f"/products/{handle}", expect="html")
    if resp.status_code != 200:
        res.notes.append(f"product page: http {resp.status_code}")
        return
    html = resp.text
    res.jsonld_currency = sorted(jsonld_currencies(html))
    res.shopify_currency = shopify_active_currency(html)
    res.jsonld_gtin_fields = len(jsonld_gtins(html))


async def meta(session: StoreSession, res: ReconResult) -> None:
    try:
        resp = await session.get("/meta.json")
    except RobotsDisallowed:
        return
    data = _json_or_none(resp)
    if resp.status_code == 200 and isinstance(data, dict):
        country, currency = data.get("country"), data.get("currency")
        count = data.get("published_products_count")
        res.meta_country = country if isinstance(country, str) else None
        res.meta_currency = currency if isinstance(currency, str) else None
        res.meta_products = count if isinstance(count, int) else None


async def _robots(session: StoreSession, res: ReconResult) -> bool:
    robots = await session.load_robots()
    res.robots_status = robots.status
    res.crawl_delay_s = robots.crawl_delay_s
    if session.stopped_reason:
        res.stopped_reason = session.stopped_reason
        return False
    res.robots_products_json = session.allowed("/products.json", {"limit": PAGE_LIMIT, "page": 1})
    res.robots_product_js = session.allowed("/products/sample-handle.js")
    res.robots_product_page = session.allowed("/products/sample-handle")
    return bool(res.robots_products_json and res.robots_product_js)


async def _page(session: StoreSession, page: int) -> tuple[int, list[dict[str, Any]] | None, str]:
    resp = await session.get("/products.json", {"limit": PAGE_LIMIT, "page": page})
    payload = _json_or_none(resp)
    if resp.status_code != 200 or not is_products_payload(payload):
        return resp.status_code, None, resp.headers.get("content-type", "?")
    assert isinstance(payload, dict)
    return 200, [slim(p) for p in payload["products"] if isinstance(p, dict)], ""


async def _stage1(session: StoreSession, res: ReconResult) -> None:
    if not await _robots(session, res):
        return
    status, products, ctype = await _page(session, 1)
    res.reachable = True
    if products is None:
        res.notes.append(f"/products.json: http {status}, {ctype}")
        return
    res.shopify = True
    res.page1_products = len(products)
    res.page1_variants = sum(len(p["variants"]) for p in products)
    catalog_stats(res, products)
    await meta(session, res)
    clean = [p for p in products if not is_excluded(p)]
    for product in stable_pick(clean, res.store_id, JS_SAMPLES):
        res.js_probes.append(await probe_js(session, product, str(product["handle"])))
    sample = stable_pick(clean, res.store_id, 1)
    if sample:
        await product_page(session, res, str(sample[0]["handle"]))


@dataclass
class CatalogResult:
    recon: ReconResult
    products: list[dict[str, Any]] = field(default_factory=list)
    pages: int = 0
    complete: bool = False


async def _stage2(
    session: StoreSession,
    out: CatalogResult,
    max_pages: int,
    random_probes: int,
    handles: list[str],
) -> None:
    res = out.recon
    if not await _robots(session, res):
        return
    for page in range(1, max_pages + 1):
        status, products, ctype = await _page(session, page)
        res.reachable = True
        out.pages = page
        if products is None:
            res.notes.append(f"/products.json page {page}: http {status}, {ctype}")
            return
        res.shopify = True
        out.products.extend(products)
        if len(products) < PAGE_LIMIT:
            out.complete = True
            break
    else:
        res.notes.append(f"stopped at the page cap ({max_pages} pages)")
    kept = [p for p in out.products if not is_excluded(p)]
    catalog_stats(res, out.products)
    out.products = kept
    res.page1_products = len(kept)
    res.page1_variants = sum(len(p["variants"]) for p in kept)
    by_handle = {str(p["handle"]): p for p in kept if p.get("handle")}
    targets = [by_handle[h] for h in handles if h in by_handle]
    targets += [p for p in stable_pick(kept, res.store_id, random_probes) if p not in targets]
    for product in targets:
        res.js_probes.append(await probe_js(session, product, str(product["handle"])))
    if kept:
        await product_page(session, res, str(stable_pick(kept, res.store_id, 1)[0]["handle"]))
    await meta(session, res)


def _finish(session: StoreSession, res: ReconResult, started: float) -> None:
    res.host = session.host
    res.requests = session.requests_made
    res.retries = session.retries_made
    res.retry_causes = list(session.retry_causes)
    res.elapsed_s = round(time.monotonic() - started, 1)
    if session.stopped_reason and not res.stopped_reason:
        res.stopped_reason = session.stopped_reason


async def recon_store(session: StoreSession, cand: Candidate) -> ReconResult:
    started = time.monotonic()
    res = ReconResult(
        store=cand.store, domain=cand.domain, vertical=cand.vertical, store_id=cand.store_id
    )
    try:
        await _stage1(session, res)
    except StoreStopped as exc:
        res.stopped_reason = exc.reason
    except Exception as exc:  # recon must never crash the whole run
        res.notes.append(f"error: {type(exc).__name__}: {exc}"[:300])
    _finish(session, res, started)
    return res


async def catalog_store(
    session: StoreSession,
    cand: Candidate,
    max_pages: int,
    random_probes: int,
    handles: list[str],
) -> CatalogResult:
    started = time.monotonic()
    res = ReconResult(
        store=cand.store, domain=cand.domain, vertical=cand.vertical, store_id=cand.store_id
    )
    out = CatalogResult(recon=res)
    try:
        await _stage2(session, out, max_pages, random_probes, handles)
    except StoreStopped as exc:
        res.stopped_reason = exc.reason
    except Exception as exc:
        res.notes.append(f"error: {type(exc).__name__}: {exc}"[:300])
    _finish(session, res, started)
    return out


async def run_all(
    candidates: list[Candidate],
    config: PoliteConfig,
    edge: EdgeGuard,
    concurrency: int,
    *,
    stage: str = "recon",
    max_pages: int = 12,
    random_probes: int = 8,
    handles: dict[str, list[str]] | None = None,
) -> list[CatalogResult]:
    """Run one stage for every candidate.

    Retailers overlap only to hide latency: requests within a retailer are
    sequential (at least ``config.delay_s`` apart) and every request in the run
    passes the shared ``edge`` pacer, so the run as a whole stays at one pace.
    """
    gate = asyncio.Semaphore(concurrency)
    handles = handles or {}

    async with make_client() as client:

        async def one(cand: Candidate) -> CatalogResult:
            async with gate:
                session = StoreSession(
                    client=client, base_url=f"https://{cand.domain}", config=config, edge=edge
                )
                if stage == "recon":
                    out = CatalogResult(recon=await recon_store(session, cand))
                else:
                    out = await catalog_store(
                        session, cand, max_pages, random_probes, handles.get(cand.store_id, [])
                    )
                passed, fails = out.recon.verdict()
                print(
                    f"{cand.store:<30} {'PASS' if passed else 'fail':<4} "
                    f"reqs={out.recon.requests} {', '.join(fails)}",
                    flush=True,
                )
                return out

        return list(await asyncio.gather(*(one(c) for c in candidates)))
