from __future__ import annotations

from datetime import date
from pathlib import Path

from crossprice.compare import build, changes, price_index, read_csv, to_csv_rows, write_csv
from crossprice.gtincache import GtinCache, plan_probes
from crossprice.match import Product
from crossprice.retailers import Retailer
from tests.test_match import row

RETAILERS = [Retailer(i, i.upper(), "coffee", f"{i}.example") for i in ("a", "b", "c")]


def _products() -> tuple[list[Product], dict[tuple[str, int], object]]:
    offers = {
        ("a", 10): row("a", 10, "Encore ESP", price_cents=17000),
        ("b", 20): row("b", 20, "Encore ESP", price_cents=18000),
        ("c", 30): row("c", 30, "Encore ESP", price_cents=16000, availability="out_of_stock"),
    }
    p = Product(
        key="00012345678905",
        members={"a": ("a", 10), "b": ("b", 20), "c": ("c", 30)},
        tier="gtin",
        confidence=1.0,
        gtin14="00012345678905",
    )
    return [p], offers  # type: ignore[return-value]


def test_lowest_price_uses_in_stock_offers_and_spread_is_a_number() -> None:
    products, offers = _products()
    (r,) = build(products, offers)  # type: ignore[arg-type]
    assert r.lowest_cents == 17000  # c is cheaper but out of stock
    assert r.lowest_retailers == ["a"]
    assert r.spread_pct == round(1000 / 17000 * 100, 1)
    csv_row = to_csv_rows([r], RETAILERS)[0]
    assert csv_row["c_in_stock"] == "no"
    assert csv_row["a_url"] == "https://a.example/products/encore-esp?variant=10"
    assert csv_row["lowest_price_usd"] == "170.00"


def test_changes_report_moves_stock_and_new_lowest(tmp_path: Path) -> None:
    products, offers = _products()
    rows = build(products, offers)  # type: ignore[arg-type]
    write_csv(rows, RETAILERS, tmp_path / "c.csv")
    prev = read_csv(tmp_path / "c.csv")
    offers[("b", 20)] = row("b", 20, "Encore ESP", price_cents=16500)
    offers[("a", 10)] = row("a", 10, "Encore ESP", price_cents=17000, availability="out_of_stock")
    events = changes(prev, build(products, offers), "2026-11-21T07:41:00Z")  # type: ignore[arg-type]
    kinds = sorted((e["event"], e["retailer_id"]) for e in events)
    assert kinds == [("new_lowest", "b"), ("out_of_stock", "a"), ("price_down", "b")]


def test_a_retailer_not_read_today_is_not_a_new_lowest(tmp_path: Path) -> None:
    products, offers = _products()
    offers[("b", 20)] = row("b", 20, "Encore ESP", price_cents=17000)  # a and b tie
    write_csv(build(products, offers), RETAILERS, tmp_path / "c.csv")  # type: ignore[arg-type]
    prev = read_csv(tmp_path / "c.csv")
    assert prev[0]["lowest_price_retailers"] == "a b"
    del offers[("b", 20)]  # b failed today: its offer is not in the comparison
    events = changes(prev, build(products, offers), "2026-11-22T15:41:00Z")  # type: ignore[arg-type]
    assert events == []
    offers[("a", 10)] = row("a", 10, "Encore ESP", price_cents=17500)  # a real move
    events = changes(prev, build(products, offers), "2026-11-22T15:41:00Z")  # type: ignore[arg-type]
    assert [e["event"] for e in events] == ["price_up"]


def test_price_index_demo() -> None:
    products, offers = _products()
    rows = build(products, offers)  # type: ignore[arg-type]
    idx = price_index(rows, "b")
    assert idx["products_shared"] == 1
    assert idx["index"] == round(18000 / 17000 * 100, 1)
    assert idx["above"][0]["difference_pct"] == 5.9
    assert price_index(rows, "c")["products_shared"] == 0  # out of stock: not compared


def test_cache_round_trip_and_probe_priorities(tmp_path: Path) -> None:
    cache = GtinCache()
    day = date(2026, 11, 20)
    cache.update("a", 1, {11: "00012345678905", 12: None}, "js", date(2026, 11, 1))
    cache.update("a", 2, {21: "04006381333931"}, "js", day)
    cache.save(tmp_path / "cache.csv")
    again = GtinCache.load(tmp_path / "cache.csv")
    assert again.gtins("a") == {11: "00012345678905", 21: "04006381333931"}
    plan = plan_probes(
        "a",
        product_ids=[1, 2, 3, 4, 5],
        candidate_scores={5: 0.9, 4: 0.6},
        compared={1},
        shared_brand={3},
        cache=again,
        day=day,
        budget=4,
    )
    assert plan == [5, 4, 1, 3]  # candidates, stale compared, shared brand
