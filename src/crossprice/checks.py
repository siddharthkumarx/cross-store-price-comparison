"""Live-checks runner for .github/workflows/checks.yml.

The development sandbox cannot reach stores, so every live check is described in
``checks/request.yml`` and executed on one GitHub Actions runner, started by hand
(``workflow_dispatch``). Results go to ``checks/results/<id>/`` and are committed
by the workflow as evidence.

Usage::

    python -m crossprice.checks checks/request.yml
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import hashlib
import io
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from crossprice.polite import USER_AGENT, EdgeGuard, PoliteConfig
from crossprice.recon import Candidate, CatalogResult, ReconResult, run_all
from crossprice.witness import price_to_cents

RESULTS_DIR = Path("checks/results")
CATALOG_COLUMNS = (
    "product_id",
    "handle",
    "vendor",
    "product_type",
    "title",
    "variant_id",
    "variant_title",
    "option1",
    "option2",
    "option3",
    "sku",
    "price_cents",
    "compare_at_cents",
    "available",
)


def load_candidates(path: Path) -> list[Candidate]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[Candidate] = []
    for vertical, stores in raw["verticals"].items():
        for item in stores:
            out.append(Candidate(store=item["store"], domain=item["domain"], vertical=vertical))
    return out


def run_meta(request: dict[str, Any], started: datetime) -> dict[str, Any]:
    return {
        "id": request["id"],
        "check": request["check"],
        "purpose": request.get("purpose"),
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": os.environ.get("GITHUB_SHA"),
        "run_url": (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
            if "GITHUB_RUN_ID" in os.environ
            else None
        ),
        "runner": f"{platform.system()} {platform.machine()} / Python {platform.python_version()}",
        "user_agent": USER_AGENT,
    }


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.0%}"
    if isinstance(value, list):
        return ",".join(str(v) for v in value) or "-"
    return str(value)


def render_md(meta: dict[str, Any], results: list[ReconResult]) -> str:
    passed = [r for r in results if r.verdict()[0]]
    lines = [
        f"# Recon `{meta['id']}` ({meta['check']})",
        "",
        f"- purpose: {meta.get('purpose') or '-'}",
        f"- started: {meta['started_utc']}, finished: {meta['finished_utc']}",
        f"- run: {meta['run_url'] or 'local'}",
        f"- retailers: {len(results)}, passed: {len(passed)}",
        f"- requests: {sum(r.requests for r in results)}; run-wide interval "
        f"{meta.get('edge_interval_s')} s + jitter; per host {meta.get('delay_s')} s + jitter; "
        f"halted: {meta.get('halted_reason') or 'no'}",
        "",
        "| retailer | vertical | host | country | products (meta) | vendors | top vendor "
        "| SKU | GTIN (sampled variants) | JSON-LD GTIN | currency | reqs | result |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|",
    ]
    for r in sorted(results, key=lambda x: (x.vertical, x.store.lower())):
        ok, fails = r.verdict()
        sampled = sum(p.variants for p in r.js_probes if p.status == "ok")
        valid = sum(p.gtins_valid for p in r.js_probes if p.status == "ok")
        gtin = f"{valid}/{sampled}" if sampled else "-"
        theme = {r.shopify_currency} if r.shopify_currency else set()
        cur = sorted(set(r.jsonld_currency) | theme)
        lines.append(
            f"| {r.store} | {r.vertical} | {r.host or r.domain} | {_fmt(r.meta_country)} "
            f"| {_fmt(r.meta_products)} | {r.vendor_count or '-'} | {_fmt(r.top_vendor_share)} "
            f"| {_fmt(r.sku_share)} | {gtin} | {r.jsonld_gtin_fields} | {_fmt(cur)} "
            f"| {r.requests} | {'PASS' if ok else 'fail: ' + ', '.join(fails)} |"
        )
    notes = [r for r in results if r.notes or r.stopped_reason or r.content_flags]
    if notes:
        lines += ["", "## Notes", ""]
        for r in sorted(notes, key=lambda x: x.store.lower()):
            bits = [f"stopped: {r.stopped_reason}"] if r.stopped_reason else []
            bits += r.notes
            if r.content_flags:
                bits.append(
                    f"screen ({r.excluded_share:.1%} of products): "
                    + "; ".join(f"{k}: {', '.join(v)}" for k, v in r.content_flags.items())
                )
            lines.append(f"- **{r.store}**: " + "; ".join(bits))
    return "\n".join(lines) + "\n"


def catalog_csv(products: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CATALOG_COLUMNS)
    for p in sorted(products, key=lambda x: int(x.get("id") or 0)):
        for v in sorted(p["variants"], key=lambda x: int(x.get("id") or 0)):
            writer.writerow(
                [
                    p.get("id"),
                    p.get("handle"),
                    (p.get("vendor") or "").strip(),
                    (p.get("product_type") or "").strip(),
                    (p.get("title") or "").strip(),
                    v.get("id"),
                    (v.get("title") or "").strip(),
                    v.get("option1") or "",
                    v.get("option2") or "",
                    v.get("option3") or "",
                    (str(v.get("sku") or "")).strip(),
                    price_to_cents(v.get("price")),
                    price_to_cents(v.get("compare_at_price")),
                    v.get("available"),
                ]
            )
    # mtime=0 keeps the gzip bytes reproducible for identical content.
    return gzip.compress(buf.getvalue().encode("utf-8"), mtime=0)


def run_request(request_path: Path) -> int:
    request = yaml.safe_load(request_path.read_text(encoding="utf-8"))
    check = request["check"]
    if check not in ("recon", "catalog"):
        print(f"unknown check: {check}", file=sys.stderr)
        return 2
    out_dir = RESULTS_DIR / str(request["id"])
    if out_dir.exists():
        print(f"{out_dir} exists: give the request a new id", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True)
    started = datetime.now(UTC)

    candidates = load_candidates(Path(request.get("candidates", "checks/candidates.yml")))
    only = set(request.get("only") or [])
    verticals = set(request.get("verticals") or [])
    if only:
        candidates = [c for c in candidates if c.store in only or c.store_id in only]
    if verticals:
        candidates = [c for c in candidates if c.vertical in verticals]
    # Interleave verticals in a stable order, so a halted run does not lose one vertical.
    candidates.sort(key=lambda c: hashlib.sha256(c.store_id.encode()).hexdigest())
    config = PoliteConfig(
        delay_s=float(request.get("delay_s", 4.0)), jitter_s=float(request.get("jitter_s", 3.0))
    )
    edge = EdgeGuard(
        interval_s=float(request.get("edge_interval_s", 3.0)),
        jitter_s=float(request.get("edge_jitter_s", 1.5)),
        trip_after=int(request.get("trip_after", 4)),
    )
    print(f"{check}: {len(candidates)} retailers", flush=True)
    results: list[CatalogResult] = asyncio.run(
        run_all(
            candidates,
            config,
            edge,
            int(request.get("concurrency", 4)),
            stage=check,
            max_pages=int(request.get("max_pages", 12)),
            random_probes=int(request.get("random_probes", 8)),
            handles=request.get("handles") or {},
        )
    )
    meta = run_meta(request, started)
    meta.update(
        edge_interval_s=edge.interval_s,
        delay_s=config.delay_s,
        halted_reason=edge.halted_reason,
        throttle_events=edge.throttle_events,
        requests=sum(r.recon.requests for r in results),
    )
    payload: dict[str, Any] = {"meta": meta, "results": []}
    for r in results:
        item = r.recon.to_dict()
        if check == "catalog":
            item["pages"] = r.pages
            item["catalog_complete"] = r.complete
            item["catalog_products"] = len(r.products)
            if r.products:
                cat_dir = out_dir / "catalogs"
                cat_dir.mkdir(exist_ok=True)
                (cat_dir / f"{r.recon.store_id}.csv.gz").write_bytes(catalog_csv(r.products))
        payload["results"].append(item)
    (out_dir / "recon.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out_dir / "recon.md").write_text(render_md(meta, [r.recon for r in results]), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="path to checks/request.yml")
    args = parser.parse_args(argv)
    return run_request(args.request)


if __name__ == "__main__":
    raise SystemExit(main())
