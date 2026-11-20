"""Overlap and GTIN coverage of a vertical, from committed stage-2 recon results.

    python -m crossprice.overlap checks/results/recon-002 [--probes checks/results/recon-003]

Reads ``catalogs/*.csv.gz`` and the ``.js`` probes in ``recon.json``, runs the
matchers with provisional recon cut-offs (``RECON_CUTOFF``; the daily run uses
thresholds measured blind instead, D-011) and reports per retailer:

* products, and the share of its products also sold by at least one other
  retailer of the vertical (the D-002 overlap measure);
* products sold by 3 or more retailers;
* sampled variants with a valid GTIN, and how many candidate pairs the probes
  could verify by GTIN.

It also lists, per retailer, the handles of overlap candidates without a probed
GTIN, for a confirming probe run (``handles`` in ``checks/request.yml``).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crossprice.match import Offer, Pair, candidate_pairs, gtin_pairs, to_offer
from crossprice.models import OfferRow

RECON_CUTOFF = {"mpn": 0.85, "fuzzy": 0.8}
OBSERVED = datetime(2026, 1, 1, tzinfo=UTC)


def load_catalog(path: Path, retailer_id: str) -> list[OfferRow]:
    rows: list[OfferRow] = []
    text = gzip.decompress(path.read_bytes()).decode("utf-8")
    for r in csv.DictReader(io.StringIO(text)):
        price = int(r["price_cents"]) if r["price_cents"] else 0
        if price <= 0:
            continue
        compare = int(r["compare_at_cents"]) if r["compare_at_cents"] else None
        opts = tuple(
            o for o in (r["option1"], r["option2"], r["option3"]) if o and o != "Default Title"
        )
        rows.append(
            OfferRow(
                retailer_id=retailer_id,
                product_id=int(r["product_id"]),
                variant_id=int(r["variant_id"]),
                handle=r["handle"],
                brand=r["vendor"][:255],
                product_type=r["product_type"][:255],
                product_title=r["title"][:255],
                variant_title=r["variant_title"][:255],
                options=opts,
                sku=r["sku"][:255],
                gtin14=None,
                price_cents=price,
                compare_at_cents=compare if compare and compare >= price else None,
                availability="in_stock" if r["available"] == "True" else "out_of_stock",
                observed_at=OBSERVED,
            )
        )
    return rows


def probe_gtins(results: list[dict[str, Any]]) -> dict[str, dict[int, str]]:
    out: dict[str, dict[int, str]] = defaultdict(dict)
    for r in results:
        for p in r.get("js_probes") or []:
            for vid, g in (p.get("gtins") or {}).items():
                out[r["store_id"]][int(vid)] = g
    return out


def analyse(result_dirs: list[Path], verticals: set[str] | None = None) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for d in result_dirs:
        results += json.loads((d / "recon.json").read_text(encoding="utf-8"))["results"]
    latest: dict[str, dict[str, Any]] = {}
    for r in results:  # later directories win
        latest[r["store_id"]] = r
    gtins = probe_gtins(results)
    catalogs: dict[str, Path] = {}
    for d in result_dirs:
        for path in sorted((d / "catalogs").glob("*.csv.gz")):
            catalogs[path.name.removesuffix(".csv.gz")] = path
    by_vertical: dict[str, list[str]] = defaultdict(list)
    for sid, r in latest.items():
        if sid in catalogs and (not verticals or r["vertical"] in verticals):
            by_vertical[r["vertical"]].append(sid)
    report: dict[str, Any] = {}
    for vertical, sids in sorted(by_vertical.items()):
        rows: list[OfferRow] = []
        for sid in sorted(sids):
            known = gtins.get(sid, {})
            rows += [
                r.model_copy(update={"gtin14": known.get(r.variant_id)})
                for r in load_catalog(catalogs[sid], sid)
            ]
        report[vertical] = vertical_report(rows, latest, gtins)
    return report


def _accepted(p: Pair) -> bool:
    if p.tier == "gtin":
        return True
    return p.reason == "mutual best" and p.score >= RECON_CUTOFF[p.tier]


def vertical_report(
    rows: list[OfferRow], latest: dict[str, dict[str, Any]], gtins: dict[str, dict[int, str]]
) -> dict[str, Any]:
    offers = [to_offer(r) for r in rows]
    by_key: dict[tuple[str, int], Offer] = {o.key: o for o in offers}
    gp, _ = gtin_pairs(offers)
    cands = candidate_pairs(offers)
    pairs = gp + [p for p in cands if _accepted(p)]
    sold_at: dict[tuple[str, int], set[str]] = defaultdict(set)  # product -> other retailers
    for p in pairs:
        a, b = by_key[p.a], by_key[p.b]
        sold_at[(a.retailer_id, a.product_id)].add(b.retailer_id)
        sold_at[(b.retailer_id, b.product_id)].add(a.retailer_id)
    retailers: dict[str, Any] = {}
    products_by_retailer: dict[str, set[int]] = defaultdict(set)
    for o in offers:
        products_by_retailer[o.retailer_id].add(o.product_id)
    verify_ok = verify_bad = 0
    for p in cands:
        if not _accepted(p):
            continue
        ga, gb = by_key[p.a].gtin14, by_key[p.b].gtin14
        if ga and gb:
            verify_ok += ga == gb
            verify_bad += ga != gb
    todo: dict[str, list[str]] = defaultdict(list)
    handle = {(r.retailer_id, r.product_id): r.handle for r in rows}
    has_gtin = {(o.retailer_id, o.product_id) for o in offers if o.gtin14}
    for rid, pid in sorted(sold_at, key=lambda k: (-len(sold_at[k]), k)):
        if (rid, pid) not in has_gtin:
            todo[rid].append(handle[(rid, pid)])
    for rid, pids in sorted(products_by_retailer.items()):
        shared = [pid for pid in pids if sold_at.get((rid, pid))]
        three = [pid for pid in pids if len(sold_at.get((rid, pid), ())) >= 2]
        rec = latest.get(rid, {})
        probes = [p for p in rec.get("js_probes") or [] if p.get("status") == "ok"]
        sampled = sum(p["variants"] for p in probes)
        valid = sum(p["gtins_valid"] for p in probes)
        retailers[rid] = {
            "store": rec.get("store"),
            "passed": rec.get("passed"),
            "fail_reasons": rec.get("fail_reasons"),
            "catalog_complete": rec.get("catalog_complete"),
            "products": len(pids),
            "variants": sum(1 for o in offers if o.retailer_id == rid),
            "overlap_share": round(len(shared) / len(pids), 3) if pids else 0.0,
            "products_shared": len(shared),
            "products_at_3_plus": len(three),
            "sampled_variants": sampled,
            "sampled_with_gtin": valid,
            "gtin_share": round(valid / sampled, 3) if sampled else None,
        }
    passing = [r for r in retailers.values() if r["passed"]]
    at30 = [r for r in passing if r["overlap_share"] >= 0.30]
    sampled = sum(r["sampled_variants"] for r in passing)
    with_gtin = sum(r["sampled_with_gtin"] for r in passing)
    return {
        "retailers_passing": len(passing),
        "retailers_at_30pct_overlap": len(at30),
        "gtin_share_passing": round(with_gtin / sampled, 3) if sampled else None,
        "sampled_variants_passing": sampled,
        "pairs_by_tier": {
            t: sum(1 for p in pairs if p.tier == t) for t in ("gtin", "mpn", "fuzzy")
        },
        "candidates_verified_by_gtin": {"equal": verify_ok, "different": verify_bad},
        "retailers": retailers,
        "probe_handles": {k: v[:40] for k, v in todo.items()},
    }


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Overlap by vertical", ""]
    lines.append(
        f"Provisional recon cut-offs: MPN/SKU score >= {RECON_CUTOFF['mpn']}, fuzzy >= "
        f"{RECON_CUTOFF['fuzzy']}, mutual best; GTIN pairs exact."
    )
    for vertical, v in report.items():
        lines += [
            "",
            f"## {vertical}",
            "",
            f"- retailers passing recon: {v['retailers_passing']}; with overlap >= 30 %: "
            f"{v['retailers_at_30pct_overlap']}",
            f"- sampled variants with a valid GTIN (passing retailers): "
            f"{v['gtin_share_passing']} of {v['sampled_variants_passing']}",
            f"- pairs: {v['pairs_by_tier']}; candidate pairs checked by GTIN: "
            f"{v['candidates_verified_by_gtin']}",
            "",
            "| retailer | passed | products | overlap | at 3+ retailers | GTIN (sampled) |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for r in sorted(v["retailers"].values(), key=lambda x: -x["overlap_share"]):
            g = (
                f"{r['sampled_with_gtin']}/{r['sampled_variants']}"
                if r["sampled_variants"]
                else "-"
            )
            lines.append(
                f"| {r['store']} | {'yes' if r['passed'] else 'no'} | {r['products']} "
                f"| {r['overlap_share']:.0%} | {r['products_at_3_plus']} | {g} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dirs", nargs="+", type=Path)
    p.add_argument("--vertical", action="append", default=[])
    p.add_argument("--json", type=Path)
    p.add_argument("--md", type=Path)
    a = p.parse_args(argv)
    report = analyse(a.dirs, set(a.vertical) or None)
    if a.json:
        a.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = render_md(report)
    if a.md:
        a.md.write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
