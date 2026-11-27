"""End to end: three fake retailers through collect, match, compare, store and outputs."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

import crossprice.run as run_mod
from crossprice.polite import PoliteConfig
from crossprice.run import EXIT_OK, RunConfig, run
from tests.fakes import ROBOTS_SHOPIFY

T0 = datetime(2026, 11, 20, 7, 43, tzinfo=UTC)
G1, G2, G3 = "012345678905", "4006381333931", "00000096385074"

# retailer -> list of (product id, title, vendor, sku, price, barcode, available)
CATALOGS: dict[str, list[tuple[int, str, str, str, str, str, bool]]] = {
    "alpha.example": [
        (101, "Encore ESP Grinder", "Baratza", "1ZB-ESP", "169.95", G1, True),
        (102, "V60 Dripper 02 Ceramic", "Hario", "VDC-02W", "26.00", G2, True),
        (103, "Stagg EKG Kettle", "Fellow", "1150", "165.00", "", True),
    ],
    "beta.example": [
        (201, "Baratza Encore ESP", "Baratza", "ESP-BLK", "179.95", G1, True),
        (202, "Hario V60 Ceramic Dripper 02", "Hario USA", "HAR-9", "28.00", G2, False),
        (203, "Stagg EKG Electric Kettle", "Fellow", "1150", "159.00", "", True),
    ],
    "gamma.example": [
        (301, "Encore ESP", "BARATZA", "x", "169.95", G1, True),
        (302, "Opus Grinder", "Fellow", "OPUS-1", "195.00", G3, True),
    ],
}


def shop(host: str, prices: dict[int, str]) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        items = CATALOGS[host]
        if path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_SHOPIFY)
        if path == "/products.json":
            page = int(request.url.params.get("page", "1"))
            products = [
                {
                    "id": pid,
                    "handle": f"h{pid}",
                    "title": title,
                    "vendor": vendor,
                    "product_type": "Coffee",
                    "tags": [],
                    "body_html": "<p>never stored</p>",
                    "variants": [
                        {
                            "id": pid * 10,
                            "title": "Default Title",
                            "option1": "Default Title",
                            "sku": sku,
                            "price": prices.get(pid, price),
                            "compare_at_price": None,
                            "available": avail,
                        }
                    ],
                }
                for pid, title, vendor, sku, price, _, avail in items
            ]
            return httpx.Response(200, json={"products": products if page == 1 else []})
        if path.endswith(".js"):
            pid = int(path.removeprefix("/products/h").removesuffix(".js"))
            (item,) = [i for i in items if i[0] == pid]
            body = {
                "id": pid,
                "variants": [
                    {"id": pid * 10, "price": round(float(prices.get(pid, item[4])) * 100),
                     "barcode": item[5]}
                ],
            }  # fmt: skip
            return httpx.Response(
                200, content=json.dumps(body).encode(), headers={"content-type": "text/javascript"}
            )
        if path.startswith("/products/"):
            html = (
                '<script type="application/ld+json">{"@type":"Product","offers":'
                '{"@type":"Offer","price":"1.00","priceCurrency":"USD"}}</script>'
            )
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})
        return httpx.Response(404)

    return handler


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = {
        "retailers": [
            {
                "id": h.split(".")[0],
                "name": h.split(".")[0].title(),
                "vertical": "coffee",
                "host": h,
            }
            for h in CATALOGS
        ]
    }
    (tmp_path / "retailers.yml").write_text(yaml.safe_dump(cfg))
    (tmp_path / "public.yml").write_text(Path("config/public.yml").read_text())
    return tmp_path


def _client_for(prices: dict[str, dict[int, str]]) -> Any:
    handlers = {h: shop(h, prices.get(h, {})) for h in CATALOGS}

    def route(request: httpx.Request) -> httpx.Response:
        response: httpx.Response = handlers[request.url.host](request)
        return response

    return lambda timeout_s=30.0: httpx.AsyncClient(
        transport=httpx.MockTransport(route), follow_redirects=True
    )


async def _no_sleep(_: float) -> None:
    return None


def _cfg(workdir: Path) -> RunConfig:
    return RunConfig(
        retailers=workdir / "retailers.yml",
        data=workdir / "data",
        aliases=workdir / "none.yml",
        public=workdir / "public.yml",
        history_out=workdir / "work" / "m.parquet",
        polite=PoliteConfig(delay_s=3.0, jitter_s=0.0),
        sleep=_no_sleep,
    )


def test_two_runs_end_to_end(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_mod, "make_client", _client_for({}))
    assert run(_cfg(workdir), now=T0) == EXIT_OK
    data = workdir / "data"
    with (data / "latest" / "comparison.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    by_key = {r["product_key"]: r for r in rows}
    # Encore ESP is at 3 retailers by GTIN; the V60 at 2 (beta out of stock).
    encore = by_key["00012345678905"]
    assert encore["retailers"] == "3"
    assert encore["lowest_price_usd"] == "169.95"
    assert encore["lowest_price_retailers"] == "alpha gamma"
    assert encore["spread_pct"] == "5.9"
    v60 = by_key["04006381333931"]
    assert v60["retailers_in_stock"] == "1"
    assert v60["spread_pct"] == ""
    assert "Opus" not in json.dumps(rows)  # only one retailer sells it
    # First run: no thresholds yet, so the kettle (no GTIN) is only a possible match.
    with (data / "latest" / "possible_matches.csv").open() as fh:
        assert any("Kettle" in r["product_a"] for r in csv.DictReader(fh))
    record = json.loads((data / "runs.jsonl").read_text().splitlines()[-1])
    assert record["status"] == "ok"
    assert record["comparison"]["products_matched"] == 2
    assert "never stored" not in (data / "latest" / "offers.csv").read_text()
    feed = json.loads((data / "public" / "feed.json").read_text())
    assert feed["schema"] == "steadydata.feed/v1"
    assert feed["comparison"]["products_matched"] == 2
    assert {c["id"] for c in feed["checks"]} >= {"currency", "matching_precision"}
    badge = json.loads((data / "badges" / "matched-products.json").read_text())
    assert badge["message"] == "2"
    assert (data / "gtin" / "cache.csv").read_text().count("\n") > 5

    # Second run: beta cuts the Encore below the others.
    monkeypatch.setattr(run_mod, "make_client", _client_for({"beta.example": {201: "159.95"}}))
    assert run(_cfg(workdir), now=T0 + timedelta(days=1)) == EXIT_OK
    day2 = data / "changes" / "2026" / "2026-11-21.csv"
    with day2.open() as fh:
        events = {(e["event"], e["retailer_id"]) for e in csv.DictReader(fh)}
    assert ("price_down", "beta") in events
    assert ("new_lowest", "beta") in events
    status = json.loads((data / "status.json").read_text())
    assert status["runs_good"] == 2


def test_dashboard_builds_from_run_files(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from crossprice.site import build

    monkeypatch.setattr(run_mod, "make_client", _client_for({}))
    run(_cfg(workdir), now=T0)
    monkeypatch.setattr(run_mod, "make_client", _client_for({"beta.example": {201: "159.95"}}))
    run(_cfg(workdir), now=T0 + timedelta(days=1))
    index = build(
        workdir / "data", workdir / "retailers.yml", workdir / "public.yml", workdir / "site"
    )
    html = index.read_text()
    assert "Where is each product cheapest today?" in html
    assert "Demo on public data" in html
    assert "https://steadydata.co/contact/" in html
    assert '<script src="http' not in html  # no external scripts
    assert (workdir / "site" / "assets" / "fonts" / "plus-jakarta-sans-400.woff2").exists()
    assert (workdir / "site" / "data" / "comparison.csv").exists()
    # The SteadyData icon set and theme colour, as on steadydata.co.
    assert '<meta name="theme-color" content="#FFFFFF">' in html
    assert '<link rel="manifest" href="assets/site.webmanifest">' in html
    for name in ("favicon.ico", "icon.svg", "apple-touch-icon.png", "site.webmanifest"):
        assert (workdir / "site" / "assets" / name).exists()
    for word in ("overpriced", "MAP violation", "too expensive"):
        assert word.lower() not in html.lower()
    assert '/LICENSE">PolyForm Noncommercial 1.0.0</a>' in html
    assert '/LICENSE-DATA.md">CC BY-NC 4.0</a>' in html


def test_manual_check_sample_is_drawn_from_the_run(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from crossprice.precision_sample import draw

    monkeypatch.setattr(run_mod, "make_client", _client_for({}))
    run(_cfg(workdir), now=T0)
    run_id, pairs = draw(workdir / "data", n=10)
    assert run_id == "20261120T074300Z"
    assert len(pairs) == 2
    assert {p["retailer_a"] for p in pairs} == {"alpha"}
    assert all(p["title_a"] and p["title_b"] and p["verdict"] == "" for p in pairs)
    assert draw(workdir / "data", n=10)[1] == pairs
