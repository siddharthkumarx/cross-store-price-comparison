from __future__ import annotations

import asyncio
import gzip
import itertools
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from crossprice import checks
from crossprice.polite import EdgeGuard, PoliteConfig
from crossprice.recon import Candidate, catalog_store, recon_store, stable_pick
from tests.fakes import ROBOTS_SHOPIFY, FakeTime, session_for

CAND = Candidate(store="Example Supply", domain="shop.example", vertical="coffee")
PAGE_HTML = """<html><script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"x","gtin13":"4006381333931",
 "offers":[{"@type":"Offer","price":"28.00","priceCurrency":"USD",
 "url":"/products/item-0?variant=50000","gtin12":"012345678905"}]}
</script><script>Shopify.currency = {"active":"USD","rate":"1.0"};</script></html>"""


def _catalog(n: int, vendors: int = 6) -> list[dict[str, Any]]:
    return [
        {
            "id": 1000 + i,
            "handle": f"item-{i}",
            "title": f"Grinder Model {i}",
            "vendor": f"Brand {i % vendors}",
            "product_type": "Grinders",
            "tags": [],
            "body_html": "<p>long description that must never be kept</p>",
            "images": [{"src": "https://cdn.example/x.jpg"}],
            "variants": [
                {
                    "id": 50_000 + i * 10 + v,
                    "title": f"Black / {v}",
                    "option1": "Black",
                    "sku": f"BR-{i}-{v}",
                    "price": "28.00",
                    "compare_at_price": None,
                    "available": True,
                }
                for v in range(2)
            ],
        }
        for i in range(n)
    ]


class FakeShop:
    def __init__(self, n: int = 12, vendors: int = 6, country: str = "US") -> None:
        self.catalog = _catalog(n, vendors)
        self.country = country

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_SHOPIFY)
        if path == "/products.json":
            page = int(request.url.params.get("page", "1"))
            limit = int(request.url.params.get("limit", "30"))
            chunk = self.catalog[(page - 1) * limit : page * limit]
            return httpx.Response(200, json={"products": chunk})
        if path == "/meta.json":
            return httpx.Response(
                200,
                json={
                    "country": self.country,
                    "currency": "USD",
                    "published_products_count": len(self.catalog),
                },
            )
        if path.endswith(".js"):
            handle = path.removeprefix("/products/").removesuffix(".js")
            product = next(p for p in self.catalog if p["handle"] == handle)
            body = {
                "id": product["id"],
                "variants": [
                    {
                        "id": v["id"],
                        "price": 2800,
                        "barcode": "4006381333931" if v["id"] % 2 == 0 else "",
                    }
                    for v in product["variants"]
                ],
            }
            return httpx.Response(
                200, content=json.dumps(body).encode(), headers={"content-type": "text/javascript"}
            )
        if path.startswith("/products/"):
            return httpx.Response(200, text=PAGE_HTML, headers={"content-type": "text/html"})
        return httpx.Response(404)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_stage1_measures_a_multibrand_shop() -> None:
    session, _, seen = session_for(FakeShop(), base_url="https://shop.example")
    res = run(recon_store(session, CAND))
    passed, fails = res.verdict()
    assert passed, fails
    assert res.vendor_count == 6
    assert res.meta_products == 12
    assert res.sku_share == 1.0
    assert res.gtin_variant_share == 0.5  # every second variant has a barcode
    assert res.jsonld_gtin_fields == 2
    assert res.currency_usd
    assert res.requests == len(seen) == 6  # robots, page 1, meta, 2 x .js, 1 page
    assert "body_html" not in json.dumps(res.to_dict())


def test_single_brand_and_foreign_shops_fail() -> None:
    session, _, _ = session_for(FakeShop(vendors=1), base_url="https://shop.example")
    assert "single-brand store" in run(recon_store(session, CAND)).verdict()[1]
    session, _, _ = session_for(FakeShop(country="CA"), base_url="https://shop.example")
    assert "shop country CA" in run(recon_store(session, CAND)).verdict()[1]


def test_challenge_fails_the_candidate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="<title>Just a moment...</title>")

    session, _, _ = session_for(handler, base_url="https://shop.example")
    res = run(recon_store(session, CAND))
    assert res.verdict() == (False, ["blocked or challenged"])


def test_requests_to_one_host_are_at_least_three_seconds_apart() -> None:
    fake = FakeTime()
    edge = EdgeGuard(interval_s=3.0, jitter_s=0.0, sleep=fake.sleep, clock=fake.clock)
    session, _, _ = session_for(
        FakeShop(), base_url="https://shop.example", config=PoliteConfig(delay_s=3.0, jitter_s=0)
    )
    session.sleep, session.clock, session.edge = fake.sleep, fake.clock, edge
    times: list[float] = []
    original = session.client.get

    async def timed(url: str, **kw: Any) -> httpx.Response:
        times.append(fake.now)
        return await original(url, **kw)

    session.client.get = timed  # type: ignore[method-assign,assignment]
    run(recon_store(session, CAND))
    gaps = [b - a for a, b in itertools.pairwise(times)]
    assert gaps
    assert min(gaps) >= 3.0


def test_stage2_pages_the_catalog_and_probes_named_handles() -> None:
    shop = FakeShop(n=40)
    session, _, _ = session_for(shop, base_url="https://shop.example")
    import crossprice.recon as recon

    old = recon.PAGE_LIMIT
    recon.PAGE_LIMIT = 30
    try:
        out = run(catalog_store(session, CAND, max_pages=5, random_probes=2, handles=["item-39"]))
    finally:
        recon.PAGE_LIMIT = old
    assert out.complete
    assert out.pages == 2
    assert len(out.products) == 40
    assert out.recon.js_probes[0].handle == "item-39"
    assert len(out.recon.js_probes) == 3
    assert "images" not in out.products[0]
    assert "body_html" not in out.products[0]


def test_stable_pick_is_reproducible() -> None:
    items = _catalog(20)
    assert stable_pick(items, "a", 3) == stable_pick(list(reversed(items)), "a", 3)
    assert stable_pick(items, "a", 3) != stable_pick(items, "b", 3)


def test_catalog_csv_keeps_identifiers_only() -> None:
    from crossprice.recon import slim

    data = gzip.decompress(checks.catalog_csv([slim(p) for p in _catalog(2)])).decode()
    header = data.splitlines()[0]
    assert header.startswith("product_id,handle,vendor")
    assert "description" not in data
    assert "cdn.example" not in data
    assert data.count("\n") == 5  # header + 2 products x 2 variants


def test_candidates_file_is_well_formed() -> None:
    path = Path("checks/candidates.yml")
    if not path.exists():
        pytest.skip("no candidates yet")
    cands = checks.load_candidates(path)
    domains = [c.domain for c in cands]
    assert len(domains) == len(set(domains))
    banned = ("amazon.", "walmart.", "ebay.", "etsy.", "target.", "google.")
    assert not [d for d in domains if d.startswith(banned) or f".{banned}" in d]
    raw = yaml.safe_load(path.read_text())
    assert set(raw["verticals"])
