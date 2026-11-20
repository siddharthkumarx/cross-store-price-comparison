from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from crossprice.history import connect, load_snapshot, merge, update_month_parquet, write_snapshot
from tests.test_match import row

T0 = datetime(2026, 11, 20, 7, 41, tzinfo=UTC)
T1 = T0 + timedelta(days=1)


def test_scd2_merge_opens_closes_and_carries(tmp_path: Path) -> None:
    snap = tmp_path / "offers.csv"
    con = connect()
    load_snapshot(con, snap)
    day0 = [
        row("a", 10, "Encore ESP", gtin14="00012345678905", observed_at=T0),
        row("a", 11, "Sette 30", observed_at=T0),
        row("b", 20, "Encore ESP", observed_at=T0),
    ]
    r0 = merge(con, day0, {"a", "b"}, T0)
    assert (r0.new, r0.changed, r0.removed) == (3, 0, 0)
    write_snapshot(con, r0.open_versions, snap)

    con = connect()
    load_snapshot(con, snap)
    day1 = [
        row("a", 10, "Encore ESP (renamed)", gtin14="00012345678905", price_cents=16000),
    ]
    r1 = merge(con, day1, {"a"}, T1)  # b failed today: carried unchanged
    assert (r1.new, r1.changed, r1.removed) == (0, 1, 1)
    open_keys = {(v.retailer_id, v.variant_id): v for v in r1.open_versions}
    assert set(open_keys) == {("a", 10), ("b", 20)}
    assert open_keys[("a", 10)].valid_from == T1
    assert open_keys[("a", 10)].gtin14 == "00012345678905"
    assert open_keys[("b", 20)].valid_from == T0
    assert {(v.variant_id, v.valid_to) for v in r1.closed_versions} == {(10, T1), (11, T1)}

    out = tmp_path / "m.parquet"
    n = update_month_parquet(
        con, None, r1.open_versions, r1.closed_versions, T0.replace(day=1), T1, out
    )
    assert n == 4
    cols = duckdb.sql(f"SELECT * FROM read_parquet('{out}') LIMIT 0").columns
    assert {"brand", "sku", "gtin14", "valid_from", "valid_to", "exported_at"} <= set(cols)


def test_unchanged_offer_keeps_its_version_and_refreshes_identifiers(tmp_path: Path) -> None:
    snap = tmp_path / "offers.csv"
    con = connect()
    load_snapshot(con, snap)
    write_snapshot(con, merge(con, [row("a", 10, "Old name")], {"a"}, T0).open_versions, snap)
    con = connect()
    load_snapshot(con, snap)
    r = merge(con, [row("a", 10, "New name", sku="X-1001")], {"a"}, T1)
    (v,) = r.open_versions
    assert (v.valid_from, v.product_title, v.sku) == (T0, "New name", "X-1001")
    assert r.closed_versions == []
