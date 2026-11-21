"""The daily pipeline: collect, validate, match, compare, store, outputs.

    python -m crossprice.run --retailers config/retailers.yml --data data \\
        --history-in work/offer_history_2026-11.parquet \\
        --history-out work/offer_history_2026-11.parquet

Exit codes: 0 ok, 2 partial (some retailers not updated), 3 held (nothing
published, the last good data stays live), 1 crashed. ``runs.jsonl`` and
``status.json`` are written for every code.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import sys
import time
import traceback
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from crossprice import __version__
from crossprice.collect import RetailerFetch, fetch_catalog, fetch_probes
from crossprice.compare import (
    ComparisonRow,
    avg_spread,
    build,
    changes,
    price_index,
    read_csv,
    write_csv,
)
from crossprice.gtincache import GTIN_BUDGET, GtinCache, plan_probes
from crossprice.guard import PrevVersion, accept_repeat, check_batch
from crossprice.history import (
    connect,
    load_snapshot,
    merge,
    previous_versions,
    update_month_parquet,
    write_snapshot,
)
from crossprice.match import (
    POSSIBLE_MIN,
    MatchResult,
    Offer,
    Pair,
    Thresholds,
    candidate_pairs,
    match,
    to_offer,
)
from crossprice.models import OfferRow
from crossprice.normalize import NormalizeStats, normalize_products
from crossprice.outputs import (
    append_changes,
    append_run,
    build_feed,
    build_status,
    iso,
    parse_iso,
    read_runs,
    write_json,
    write_status,
)
from crossprice.polite import EdgeGuard, PoliteConfig, StoreSession, make_client
from crossprice.precision import Evaluation, evaluate
from crossprice.retailers import Retailer, load_retailers
from crossprice.schedule import dispatch_slot

EXIT_OK, EXIT_CRASHED, EXIT_PARTIAL, EXIT_HELD = 0, 1, 2, 3
RETAILERS_OK_SHARE = 0.8


@dataclass
class RunConfig:
    retailers: Path = Path("config/retailers.yml")
    data: Path = Path("data")
    aliases: Path = Path("config/brand-aliases.yml")
    public: Path = Path("config/public.yml")
    history_in: Path | None = None
    history_out: Path | None = None
    concurrency: int = 5
    polite: PoliteConfig = field(default_factory=lambda: PoliteConfig(delay_s=4.0, jitter_s=3.0))
    edge_interval_s: float = 3.0
    edge_jitter_s: float = 1.5
    gtin_budget: int = GTIN_BUDGET
    # No new request after 38 minutes: with setup, upload and commit the job stays
    # under the 45-minute limit (D-005).
    budget_s: float = 38 * 60
    slot: str | None = None
    only: set[str] = field(default_factory=set)
    # Injected by tests; the real run sleeps for real.
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


def load_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}


def load_thresholds(data: Path) -> Thresholds:
    """The thresholds chosen by the previous evaluation (D-011)."""
    path = data / "precision" / "latest.json"
    if not path.exists():
        return Thresholds()
    nxt = json.loads(path.read_text(encoding="utf-8")).get("next_thresholds") or {}
    return Thresholds(mpn=nxt.get("mpn"), fuzzy=nxt.get("fuzzy"))


def _offers(
    fetches: list[RetailerFetch],
    retailers: dict[str, Retailer],
    cache: GtinCache,
) -> tuple[dict[str, list[OfferRow]], dict[str, NormalizeStats]]:
    rows: dict[str, list[OfferRow]] = {}
    stats: dict[str, NormalizeStats] = {}
    for f in fetches:
        if f.status not in ("ok", "mismatch"):
            continue
        r, s = normalize_products(
            f.retailer_id,
            f.products,
            f.observed_at,
            cache.gtins(f.retailer_id),
            retailers[f.retailer_id].screen_reviewed,
        )
        rows[f.retailer_id], stats[f.retailer_id] = r, s
    return rows, stats


def probe_plan(
    rows: dict[str, list[OfferRow]],
    aliases: dict[str, str],
    thresholds: Thresholds,
    cache: GtinCache,
    day: date,
    budget: int,
) -> dict[str, list[int]]:
    """Which products each retailer should probe for GTINs today."""
    all_rows = [r for lst in rows.values() for r in lst]
    offers = [to_offer(r, aliases) for r in all_rows]
    by_key = {o.key: o for o in offers}
    pairs = candidate_pairs(offers)
    res = match(offers, thresholds)
    compared = {k for p in res.products for k in p.members.values()}
    scores: dict[str, dict[int, float]] = defaultdict(dict)
    for p in pairs:
        if p.score < POSSIBLE_MIN:
            continue
        for k in (p.a, p.b):
            pid = by_key[k].product_id
            scores[k[0]][pid] = max(scores[k[0]].get(pid, 0.0), p.score)
    brand_retailers: dict[str, set[str]] = defaultdict(set)
    for o in offers:
        if o.brand_key:
            brand_retailers[o.brand_key].add(o.retailer_id)
    plan: dict[str, list[int]] = {}
    for rid, lst in rows.items():
        shared = {
            by_key[r.key].product_id
            for r in lst
            if len(brand_retailers.get(by_key[r.key].brand_key, set())) >= 2
        }
        plan[rid] = plan_probes(
            rid,
            [r.product_id for r in lst],
            scores.get(rid, {}),
            {by_key[k].product_id for k in compared if k[0] == rid},
            shared,
            cache,
            day,
            budget,
        )
    return plan


async def collect(
    retailers: list[Retailer],
    cfg: RunConfig,
    edge: EdgeGuard,
    cache: GtinCache,
    aliases: dict[str, str],
    thresholds: Thresholds,
    day: date,
) -> list[RetailerFetch]:
    gate = asyncio.Semaphore(cfg.concurrency)
    by_id = {r.id: r for r in retailers}
    # A daily rotating start order, so a budget cut never hits the same retailers daily.
    order = sorted(retailers, key=lambda r: hashlib.sha256(f"{day}|{r.id}".encode()).hexdigest())
    async with make_client() as client:
        sessions = {
            r.id: StoreSession(
                client=client, base_url=r.base_url, config=cfg.polite, edge=edge, sleep=cfg.sleep
            )
            for r in retailers
        }

        async def catalog(r: Retailer) -> RetailerFetch:
            async with gate:
                f = await fetch_catalog(sessions[r.id], r)
                print(f"catalog {r.id:<28} {f.status:<8} products={len(f.products):<5} "
                      f"reqs={f.requests:<3} {f.reason or ''}", flush=True)  # fmt: skip
                return f

        fetched = {f.retailer_id: f for f in await asyncio.gather(*(catalog(r) for r in order))}
        rows, _ = _offers(list(fetched.values()), by_id, cache)
        plan = probe_plan(rows, aliases, thresholds, cache, day, cfg.gtin_budget)

        async def probes(r: Retailer) -> None:
            f = fetched[r.id]
            if not f.complete:
                return
            ids = plan.get(r.id, [])
            proof = next((p for p in f.products if int(p["id"]) in set(ids[:1])), None)
            proof = proof or min(f.products, key=lambda p: int(p["id"]), default=None)
            async with gate:
                await fetch_probes(sessions[r.id], f, ids, str(proof["handle"]) if proof else None)
            print(f"probes  {r.id:<28} {f.status:<8} probes={len(f.probes):<3} "
                  f"reqs={f.requests:<3} {f.reason or ''}", flush=True)  # fmt: skip

        await asyncio.gather(*(probes(r) for r in order))
        return [fetched[r.id] for r in retailers]


def _env_run_meta() -> dict[str, Any]:
    server, repo, run_id = (
        os.environ.get("GITHUB_SERVER_URL"),
        os.environ.get("GITHUB_REPOSITORY"),
        os.environ.get("GITHUB_RUN_ID"),
    )
    meta: dict[str, Any] = {
        "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "git_sha": os.environ.get("GITHUB_SHA"),
        "run_url": f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else None,
        "version": __version__,
    }
    # A dispatch that named its slot: the on-time trigger, or the watchdog (F1 INC-009).
    slot = dispatch_slot(os.environ.get("DISPATCH_SLOT", ""))
    if meta["trigger"] == "workflow_dispatch" and slot:
        meta["dispatch"] = {"slot": slot, "by": os.environ.get("DISPATCH_BY") or "trigger"}
    return meta


POSSIBLE_COLUMNS = [
    "score",
    "tier",
    "reason",
    "brand",
    "retailer_a",
    "product_a",
    "sku_a",
    "price_a_usd",
    "retailer_b",
    "product_b",
    "sku_b",
    "price_b_usd",
]


def write_possible(path: Path, pairs: list[Pair], rows: dict[tuple[str, int], OfferRow]) -> None:
    from crossprice.compare import display_name, dollars

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=POSSIBLE_COLUMNS, lineterminator="\n")
        w.writeheader()
        for p in sorted(pairs, key=lambda x: (-x.score, x.ordered)):
            a, b = rows[p.a], rows[p.b]
            w.writerow(
                {
                    "score": f"{p.score:.3f}",
                    "tier": p.tier,
                    "reason": p.reason,
                    "brand": a.brand,
                    "retailer_a": a.retailer_id,
                    "product_a": display_name(a),
                    "sku_a": a.sku,
                    "price_a_usd": dollars(a.price_cents),
                    "retailer_b": b.retailer_id,
                    "product_b": display_name(b),
                    "sku_b": b.sku,
                    "price_b_usd": dollars(b.price_cents),
                }
            )


def precision_block(ev: Evaluation, run_at: datetime, run_id: str) -> dict[str, Any]:
    nxt = ev.next_thresholds()
    return {
        "measured_at": iso(run_at),
        "run_id": run_id,
        **ev.to_dict(),
        "next_thresholds": {"mpn": nxt.mpn, "fuzzy": nxt.fuzzy},
    }


def _checks(
    fetches: list[RetailerFetch],
    rejected: int,
    rows: int,
    ev: Evaluation | None,
    gtin_share: float | None,
) -> list[dict[str, Any]]:
    ok_n = sum(1 for f in fetches if f.complete)
    compared = sum(p.compared for f in fetches for p in f.probes)
    diffs = sum(p.price_diffs for f in fetches for p in f.probes)
    currencies = sorted({c for f in fetches for c in f.currencies})
    checks: list[dict[str, Any]] = [
        {
            "id": "retailers_read",
            "label": "Stores read completely",
            "value": f"{ok_n}/{len(fetches)}",
            "ok": ok_n >= RETAILERS_OK_SHARE * len(fetches),
        },
        {
            "id": "validation_rejects",
            "label": "Rows rejected by validation",
            "value": rejected,
            "ok": rows == 0 or rejected / max(1, rows + rejected) <= 0.02,
        },
        {
            "id": "currency",
            "label": "Prices proven to be US dollars",
            "value": ",".join(currencies) or "none",
            "ok": currencies == ["USD"],
        },
        {
            "id": "second_source",
            "label": "Prices confirmed by a second source",
            "value": f"{compared - diffs}/{compared}",
            "ok": compared == 0 or diffs <= 0.05 * compared,
        },
        {
            "id": "gtin_coverage",
            "label": "Product options whose barcode has been read so far",
            "value": gtin_share,
            "ok": True,
        },
    ]
    prec = ev.combined_precision if ev else None
    checks.append(
        {
            "id": "matching_precision",
            "label": "Matching precision (blind, against barcodes)",
            "value": prec,
            "ok": prec is None or prec >= 0.98,
        }
    )
    return checks


def process(
    cfg: RunConfig,
    retailers: list[Retailer],
    fetches: list[RetailerFetch],
    cache: GtinCache,
    aliases: dict[str, str],
    thresholds: Thresholds,
    run_at: datetime,
    started: float,
    edge: EdgeGuard | None = None,
) -> tuple[int, dict[str, Any]]:
    """Validate, guard, match, compare, merge and write outputs."""
    data = cfg.data
    run_id = run_at.strftime("%Y%m%dT%H%M%SZ")
    by_id = {r.id: r for r in retailers}
    for f in fetches:
        for p in f.probes:
            if p.status == "ok":
                cache.update(f.retailer_id, p.product_id, p.gtins, "js", run_at.date())
    all_rows, stats = _offers(fetches, by_id, cache)
    per_retailer = {rid: lst for rid, lst in all_rows.items() if by_fetch(fetches, rid).complete}
    rejected = {rid: s.rejected for rid, s in stats.items()}

    snapshot = data / "latest" / "offers.csv"
    con = connect()
    load_snapshot(con, snapshot)
    prev = {
        rid: {vid: PrevVersion(price, compare) for vid, (price, compare) in versions.items()}
        for rid, versions in previous_versions(con).items()
    }
    non_usd = {
        f.retailer_id: sorted(f.currencies)
        for f in fetches
        if f.status in ("ok", "mismatch") and f.currencies and f.currencies != {"USD"}
    }
    guard = check_batch(per_retailer, prev, rejected, non_usd)
    history = read_runs(data)
    last = history[-1] if history else None
    accepted_repeat = guard.held and accept_repeat(
        guard.keys, last["status"] if last else None, (last or {}).get("guard", {}).get("keys", [])
    )
    held = guard.held and not accepted_repeat

    rows = [r for lst in per_retailer.values() for r in lst]
    offers: list[Offer] = [to_offer(r, aliases) for r in rows]
    row_by_key = {r.key: r for r in rows}
    result: MatchResult = match(offers, thresholds)
    cands = candidate_pairs(offers)
    ev = evaluate(offers, cands, thresholds)
    comparison: list[ComparisonRow] = build(result.products, row_by_key)
    gtin_share = round(sum(1 for o in offers if o.gtin14) / len(offers), 3) if offers else None
    comp_block = {
        "products_matched": len(comparison),
        "retailers": len({rid for c in comparison for rid in c.offers}),
        "by_tier": dict(Counter(c.match_tier for c in comparison)),
        "matching_precision": {
            "value": ev.combined_precision,
            "recall": ev.combined_recall,
            "pairs": ev.combined_evaluated,
            "gtin_pairs": ev.gtin_pairs,
            "measured_at": iso(run_at),
            "thresholds": {"mpn": thresholds.mpn, "fuzzy": thresholds.fuzzy},
        },
        "avg_spread_pct": avg_spread(comparison),
        "possible_matches": len(result.possible),
        "gtin_share": gtin_share,
    }

    n_changes = 0
    offers_live = sum(len(v) for v in prev.values())
    parquet_rows = None
    if not held:
        latest = data / "latest"
        prev_comparison = read_csv(latest / "comparison.csv")
        events = changes(prev_comparison, comparison, iso(run_at))
        n_changes = len(events)
        append_changes(data, events, run_at)
        write_csv(comparison, retailers, latest / "comparison.csv")
        write_possible(latest / "possible_matches.csv", result.possible, row_by_key)
        write_json(
            latest / "price-index.json",
            {
                "generated_at": iso(run_at),
                "label": "Demo on public data",
                "retailers": [price_index(comparison, r.id) for r in retailers],
            },
        )
        block = precision_block(ev, run_at, run_id)
        write_json(data / "precision" / "latest.json", block)
        write_json(data / "precision" / f"{run_at:%Y}" / f"{run_at:%Y-%m-%d}.json", block)
        merged = merge(con, rows, set(per_retailer), run_at)
        write_snapshot(con, merged.open_versions, snapshot)
        offers_live = len(merged.open_versions)
        cache.save(data / "gtin" / "cache.csv", keep_retailers=by_id)
        if cfg.history_out is not None:
            month_start = run_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            parquet_rows = update_month_parquet(
                con,
                cfg.history_in,
                merged.open_versions,
                merged.closed_versions,
                month_start,
                run_at,
                cfg.history_out,
                committed_runs=[
                    parse_iso(r["started_at"]) for r in history if r["status"] in ("ok", "partial")
                ],
            )

    failed = [f for f in fetches if not f.complete]
    status = "held" if held else ("partial" if failed else "ok")
    record: dict[str, Any] = {
        "run_id": run_id,
        "started_at": iso(run_at),
        "finished_at": iso(datetime.now(UTC)),
        "duration_s": round(time.monotonic() - started, 1),
        "status": status,
        "slot": cfg.slot,
        **_env_run_meta(),
        "retailers_total": len(fetches),
        "retailers_ok": len(fetches) - len(failed),
        "retailers_not_updated": [
            {"retailer_id": f.retailer_id, "status": f.status, "reason": f.reason} for f in failed
        ],
        "offers_observed": len(rows),
        "offers_live": offers_live,
        "rows_rejected": sum(rejected.values()),
        "reject_examples": {rid: s.examples for rid, s in stats.items() if s.examples},
        "compare_at_ignored": sum(s.compare_at_ignored for s in stats.values()),
        "free_variants": sum(s.free for s in stats.values()),
        "excluded_variants": sum(s.excluded for s in stats.values()),
        "changes_total": n_changes,
        "comparison": comp_block,
        "gtin_cache": cache.stats(),
        "match": {
            "gtin_duplicates": result.gtin_duplicates,
            "conflicts": result.conflicts,
            "candidate_pairs": len(cands),
        },
        "parquet_rows": parquet_rows,
        "requests": sum(f.requests for f in fetches),
        "retries": sum(f.retries for f in fetches),
        "retry_causes": dict(Counter(c for f in fetches for c in f.retry_causes)),
        "edge": (
            {
                "throttle_events": edge.throttle_events,
                "cooldown_s": round(edge.cooldown_s, 1),
                "final_interval_s": round(edge.current_interval_s, 2),
                "halted_reason": edge.halted_reason,
            }
            if edge is not None
            else None
        ),
        "guard": {
            "keys": guard.keys,
            "holds": [{"key": h.key, "message": h.message} for h in guard.holds],
            "accepted_after_repeat": accepted_repeat,
            "matched": guard.matched,
            "price_changed": guard.price_changed,
            "suspicious": guard.suspicious,
        },
        "checks": _checks(fetches, sum(rejected.values()), len(rows), ev, gtin_share),
        "retailers": [f.report() for f in fetches],
    }
    append_run(data, record)
    finish_outputs(cfg)
    code = EXIT_HELD if held else (EXIT_PARTIAL if failed else EXIT_OK)
    return code, record


def by_fetch(fetches: list[RetailerFetch], rid: str) -> RetailerFetch:
    return next(f for f in fetches if f.retailer_id == rid)


def finish_outputs(cfg: RunConfig) -> None:
    """status.json, badges and the public feed, from runs.jsonl only."""
    now = datetime.now(UTC)
    runs = read_runs(cfg.data)
    status = build_status(runs, now)
    write_status(cfg.data, status)
    public = yaml.safe_load(cfg.public.read_text(encoding="utf-8")) if cfg.public.exists() else {}
    if public:
        write_json(cfg.data / "public" / "feed.json", build_feed(runs, status, public, now))


def run(cfg: RunConfig, now: datetime | None = None) -> int:
    started = time.monotonic()
    run_at = (now or datetime.now(UTC)).replace(microsecond=0)
    retailers = load_retailers(cfg.retailers)
    if cfg.only:
        retailers = [r for r in retailers if r.id in cfg.only]
    cache = GtinCache.load(cfg.data / "gtin" / "cache.csv")
    aliases = load_aliases(cfg.aliases)
    thresholds = load_thresholds(cfg.data)
    try:
        edge = EdgeGuard(
            interval_s=cfg.edge_interval_s,
            jitter_s=cfg.edge_jitter_s,
            deadline=time.monotonic() + cfg.budget_s,
            sleep=cfg.sleep,
        )
        fetches = asyncio.run(
            collect(retailers, cfg, edge, cache, aliases, thresholds, run_at.date())
        )
        code, record = process(
            cfg, retailers, fetches, cache, aliases, thresholds, run_at, started, edge
        )
    except Exception as exc:
        append_run(
            cfg.data,
            {
                "run_id": run_at.strftime("%Y%m%dT%H%M%SZ"),
                "started_at": iso(run_at),
                "finished_at": iso(datetime.now(UTC)),
                "duration_s": round(time.monotonic() - started, 1),
                "status": "crashed",
                "slot": cfg.slot,
                **_env_run_meta(),
                "error": f"{type(exc).__name__}: {exc}"[:500],
            },
        )
        finish_outputs(cfg)
        traceback.print_exc()
        return EXIT_CRASHED
    c = record["comparison"]
    print(
        f"status={record['status']} retailers_ok={record['retailers_ok']}/"
        f"{record['retailers_total']} offers={record['offers_live']} "
        f"matched={c['products_matched']} precision={c['matching_precision']['value']} "
        f"changes={record['changes_total']} requests={record['requests']} "
        f"duration_s={record['duration_s']}",
        flush=True,
    )
    return code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--retailers", type=Path, default=Path("config/retailers.yml"))
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--history-in", type=Path)
    p.add_argument("--history-out", type=Path)
    p.add_argument("--concurrency", type=int, default=5, help="retailers in flight")
    p.add_argument("--delay", type=float, default=4.0, help="per-host delay, seconds (>= 3)")
    p.add_argument("--jitter", type=float, default=3.0, help="per-host jitter, seconds")
    p.add_argument("--edge-interval", type=float, default=3.0, help="run-wide interval, seconds")
    p.add_argument("--edge-jitter", type=float, default=1.5, help="run-wide jitter, seconds")
    p.add_argument("--gtin-budget", type=int, default=GTIN_BUDGET, help="probes per retailer")
    p.add_argument("--slot", default=None, help="the schedule slot this run fills (ISO, UTC)")
    p.add_argument("--only", action="append", default=[], help="retailer id (repeatable)")
    a = p.parse_args(argv)
    cfg = RunConfig(
        retailers=a.retailers,
        data=a.data,
        history_in=a.history_in,
        history_out=a.history_out,
        concurrency=a.concurrency,
        polite=PoliteConfig(delay_s=a.delay, jitter_s=a.jitter),
        edge_interval_s=a.edge_interval,
        edge_jitter_s=a.edge_jitter,
        gtin_budget=a.gtin_budget,
        slot=a.slot or None,
        only=set(a.only),
    )
    return run(cfg)


if __name__ == "__main__":
    sys.exit(main())
