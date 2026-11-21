"""Static dashboard in ``site/`` (GitHub Pages), built from ``data/`` only.

    python -m crossprice.site --data data --retailers config/retailers.yml --out site

No external scripts, fonts or styles: everything is served from the site itself.
Every number on the page comes from the committed run files.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, select_autoescape

from crossprice.match import strip_brand
from crossprice.outputs import parse_iso, read_runs
from crossprice.precision import held_back
from crossprice.retailers import Retailer, load_retailers

ASSETS = Path(__file__).parent / "site_assets"
TABLE_FIRST = 40
CHART_BRANDS = 12


def _num(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_comparison(path: Path, retailers: list[Retailer]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            offers = []
            for ret in retailers:
                price = _num(r.get(f"{ret.id}_price_usd", ""))
                if price is None:
                    continue
                offers.append(
                    {
                        "r": ret.id,
                        "p": price,
                        "s": r.get(f"{ret.id}_in_stock") == "yes",
                        "u": r.get(f"{ret.id}_url", ""),
                    }
                )
            out.append(
                {
                    "k": r["product_key"],
                    "b": r["brand"],
                    "n": strip_brand(r["brand"], r["product"]),
                    "g": r["gtin"],
                    "t": r["match_tier"],
                    "lo": _num(r["lowest_price_usd"]),
                    "lr": r["lowest_price_retailers"].split(),
                    "sp": _num(r["spread_pct"]),
                    "o": offers,
                }
            )
    out.sort(key=lambda x: (-(x["sp"] or -1), x["b"].lower(), x["n"].lower()))
    return out


def chart_svg(by_brand: list[dict[str, Any]]) -> str:
    """Diverging bars (HTML, so text keeps its size on a phone): brand index minus 100.

    Lower than the market median grows left in the "lower" colour, higher grows
    right in the "higher" colour; every bar carries its value as text.
    """
    rows = by_brand[:CHART_BRANDS]
    if not rows:
        return ""
    span = max(5.0, max(abs(r["index"] - 100) for r in rows))
    parts = [
        '<div class="dchart" role="table" aria-label="Price index by brand, 100 is the market median">',
        '<div class="drow dhead" role="row"><span role="columnheader">Brand</span>'
        '<span role="columnheader" class="dmid">vs market median</span>'
        '<span role="columnheader" class="dn">Products</span></div>',
    ]
    for r in rows:
        d = r["index"] - 100
        width = max(1.5, abs(d) / span * 100)
        sign = "+" if d > 0 else ("−" if d < 0 else "±")
        side = "right" if d > 0 else "left"
        cls = "higher" if d > 0 else "lower"
        parts.append(
            f'<div class="drow" role="row" title="{_esc(r["brand"])}: index {r["index"]:.1f}">'
            f'<span role="cell" class="dbrand">{_esc(r["brand"])}</span>'
            f'<span role="cell" class="dplot"><span class="dhalf l">'
            + (f'<i class="{cls}" style="width:{width:.1f}%"></i>' if side == "left" else "")
            + '</span><span class="dhalf r">'
            + (f'<i class="{cls}" style="width:{width:.1f}%"></i>' if side == "right" else "")
            + f'</span><b class="dval {side}">{sign}{abs(d):.1f}%</b></span>'
            f'<span role="cell" class="dn">{r["products"]}</span></div>'
        )
    parts.append("</div>")
    return "".join(parts)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def today_changes(data: Path, run_at: datetime | None) -> list[dict[str, str]]:
    if run_at is None:
        return []
    path = data / "changes" / f"{run_at:%Y}" / f"{run_at:%Y-%m-%d}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def context(data: Path, retailers: list[Retailer], public: dict[str, Any]) -> dict[str, Any]:
    runs = read_runs(data)
    status = (
        json.loads((data / "status.json").read_text()) if (data / "status.json").exists() else {}
    )
    last = runs[-1] if runs else {}
    good = [r for r in runs if r.get("status") in ("ok", "partial")]
    last_good = good[-1] if good else {}
    comp = last_good.get("comparison") or {}
    rows = load_comparison(data / "latest" / "comparison.csv", retailers)
    index_path = data / "latest" / "price-index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"retailers": []}
    demos = [d for d in index["retailers"] if d.get("products_shared")]
    demos.sort(key=lambda d: -d["products_shared"])
    for d in demos:
        d["svg"] = chart_svg(d["by_brand"])
    prec_path = data / "precision" / "latest.json"
    precision = json.loads(prec_path.read_text()) if prec_path.exists() else None
    run_at = parse_iso(last_good["started_at"]) if last_good else None
    names = {r.id: r.name for r in retailers}
    reports = {r["retailer_id"]: r for r in last.get("retailers", [])}
    compared_by = {
        r.id: sum(1 for row in rows if any(o["r"] == r.id for o in row["o"])) for r in retailers
    }
    brands = sorted({row["b"] for row in rows}, key=str.lower)
    return {
        "public": public,
        "status": status,
        "last": last,
        "last_good": last_good,
        "comp": comp,
        "rows": rows,
        "first_rows": rows[:TABLE_FIRST],
        "brands": brands,
        "names": names,
        "retailers": retailers,
        "reports": reports,
        "compared_by": compared_by,
        "demos": demos,
        "precision": precision,
        "held": held_back(precision),
        "changes": today_changes(data, run_at),
        "run_at": run_at,
        "vertical": retailers[0].vertical.replace("-", " ") if retailers else "",
        "data_json": json.dumps(
            {"rows": rows, "names": names}, separators=(",", ":"), ensure_ascii=False
        ).replace("</", "<\\/"),
    }


def fmt_money(value: float | None) -> str:
    return "" if value is None else f"${value:,.2f}"


def fmt_pct(value: float | None, digits: int = 1) -> str:
    return "–" if value is None else f"{value:.{digits}f}%"


def fmt_share(value: float | None) -> str:
    return "not measured yet" if value is None else f"{value * 100:.1f}%"


def build(data: Path, retailers_path: Path, public_path: Path, out: Path) -> Path:
    retailers = load_retailers(retailers_path)
    public = yaml.safe_load(public_path.read_text(encoding="utf-8"))
    env = Environment(
        autoescape=select_autoescape(default=True), trim_blocks=True, lstrip_blocks=True
    )
    env.filters.update(money=fmt_money, pct=fmt_pct, share=fmt_share)
    html = env.from_string(TEMPLATE).render(**context(data, retailers, public))
    if out.exists():
        shutil.rmtree(out)
    (out / "assets" / "fonts").mkdir(parents=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(ASSETS / "style.css", out / "assets" / "style.css")
    shutil.copy(ASSETS / "app.js", out / "assets" / "app.js")
    for f in (ASSETS / "fonts").iterdir():
        shutil.copy(f, out / "assets" / "fonts" / f.name)
    # The SteadyData icon set, copied from the steadydata.co repo (not edited here).
    for f in (ASSETS / "icons").iterdir():
        shutil.copy(f, out / "assets" / f.name)
    (out / "data").mkdir()
    for src in ("latest/comparison.csv", "public/feed.json", "latest/price-index.json"):
        if (data / src).exists():
            shutil.copy(data / src, out / "data" / Path(src).name)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return out / "index.html"


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cross-store price comparison: {{ vertical }} at {{ comp.retailers or retailers|length }} US retailers</title>
<meta name="description" content="The same {{ vertical }} products at {{ retailers|length }} US online retailers, matched by barcode and compared every day: lowest price, price gaps and stock. Public data, updated daily.">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="assets/favicon.ico" sizes="32x32">
<link rel="icon" href="assets/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<link rel="manifest" href="assets/site.webmanifest">
<link rel="stylesheet" href="assets/style.css">
<link rel="preload" href="assets/fonts/plus-jakarta-sans-800.woff2" as="font" type="font/woff2" crossorigin>
<link rel="alternate" type="application/json" href="data/feed.json" title="Run feed">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
  <div class="wrap">
    <a class="brand" href="{{ public.company_site }}"><svg viewBox="10 7 44 50" width="21" height="24" aria-hidden="true" focusable="false"><defs><linearGradient id="sdm" x1="49" x2="15" y1="12" y2="52" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#1A9486"/><stop offset="1" stop-color="#5FE8D6"/></linearGradient></defs><path fill="none" stroke="url(#sdm)" stroke-linejoin="round" stroke-width="8" d="M41 14H22l-6.5 6.5v5L22 32h20l6.5 6.5v5L42 50H23"/><path fill="#D98E14" fill-rule="evenodd" d="M40.4 14a6.6 6.6 0 1 0 13.2 0 6.6 6.6 0 1 0-13.2 0m4.1 0a2.5 2.5 0 1 1 5 0 2.5 2.5 0 1 1-5 0"/><path fill="#5FE8D6" fill-rule="evenodd" d="M10.4 50a6.6 6.6 0 1 0 13.2 0 6.6 6.6 0 1 0-13.2 0m4.1 0a2.5 2.5 0 1 1 5 0 2.5 2.5 0 1 1-5 0"/></svg>SteadyData <span>· public demo</span></a>
    <a class="cta" href="{{ public.contact }}">Built by SteadyData · Get a free sample</a>
  </div>
</header>
<main id="main">
<section class="hero">
  <div class="wrap">
    <h1>Cross-store price comparison</h1>
    <p class="lead">The same {{ vertical }} products at {{ retailers|length }} US online retailers, matched by barcode and compared every day: who has the lowest price, how far apart the prices are, and who has it in stock.</p>
    <div class="statusline">
      {% if last %}
      <span class="pill{% if last.status != 'ok' %} look{% endif %}">Last run {{ last.status }}</span>
      <span>{{ last.started_at[:16].replace('T', ' ') }} UTC</span>
      <span>{{ last.retailers_ok }} of {{ last.retailers_total }} retailers read</span>
      {% if last.run_url %}<a href="{{ last.run_url }}">run log</a>{% endif %}
      <span>{{ status.days_running }} day{{ "s" if status.days_running != 1 }} running · {{ status.runs_total }} run{{ "s" if status.runs_total != 1 }}</span>
      {% else %}
      <span class="pill look">No run yet</span>
      {% endif %}
    </div>
    <div class="kpis">
      <div class="card kpi"><div class="label">Products compared</div><div class="value">{{ "{:,}".format(comp.products_matched or 0) }}</div><div class="note">sold by 2 or more retailers</div></div>
      <div class="card kpi"><div class="label">Retailers</div><div class="value">{{ retailers|length }}</div><div class="note">US online stores, prices in USD</div></div>
      <div class="card kpi"><div class="label">Matching precision</div><div class="value">{% if comp.matching_precision and comp.matching_precision.value is not none %}{{ comp.matching_precision.value | share }}{% else %}–{% endif %}</div><div class="note">{% if comp.matching_precision and comp.matching_precision.pairs %}{{ comp.matching_precision.pairs }} pairs checked against barcodes{% elif held and held.cleared %}barcode matches only in this run; name matches return next run ({{ held.precision | share }} on {{ held.evaluated }} pairs){% elif held %}name matches held back: best {{ held.precision | share }} on {{ held.evaluated }} pairs, below 98%{% else %}barcode matches only until measured{% endif %}</div></div>
      <div class="card kpi"><div class="label">Average price gap</div><div class="value">{{ comp.avg_spread_pct | pct }}</div><div class="note">highest vs lowest in-stock price</div></div>
      <div class="card kpi"><div class="label">Changes today</div><div class="value">{{ changes|length }}</div><div class="note">price moves, new lowest, stock</div></div>
    </div>
  </div>
</section>

<section class="band alt" aria-labelledby="h-lowest">
  <div class="wrap">
    <div class="section-head">
      <div>
        <h2 id="h-lowest">Where is each product cheapest today?</h2>
        <p>Every product sold by at least two of the retailers, with each store's price. The lowest in-stock price is marked; the gap is the highest in-stock price over the lowest.</p>
      </div>
    </div>
    <div class="controls" role="search">
      <label>Search<input type="search" id="q" placeholder="Product or brand" autocomplete="off"></label>
      <label>Brand<select id="brand"><option value="">All brands</option>{% for b in brands %}<option>{{ b }}</option>{% endfor %}</select></label>
      <label>Sort<select id="sort"><option value="gap">Largest price gap</option><option value="name">Brand and name</option><option value="price">Lowest price</option></select></label>
      <span class="count" id="count" aria-live="polite">{{ rows|length }} products</span>
    </div>
    <div class="card tablecard"><div class="scroll">
      <table class="stack" id="cmp">
        <thead><tr><th scope="col">Product</th><th scope="col" class="num">Lowest price</th><th scope="col" class="num">Price gap</th><th scope="col">Price at each retailer</th></tr></thead>
        <tbody>
        {% for r in first_rows %}
          <tr>
            <td data-label=""><div class="prod"><small>{{ r.b }}</small>{{ r.n }}</div></td>
            <td class="num" data-label="Lowest">{{ r.lo | money }}</td>
            <td class="num" data-label="Gap">{{ r.sp | pct }}</td>
            <td><div class="chips">{% for o in r.o %}<a class="chip{% if not o.s %} out{% elif o.r in r.lr %} low{% endif %}" href="{{ o.u }}" rel="nofollow noopener">{{ names[o.r] }} <b>{{ o.p | money }}</b></a>{% endfor %}</div></td>
          </tr>
        {% else %}
          <tr><td colspan="4" class="empty">The first run has not compared any products yet.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div></div>
    {% if rows|length > first_rows|length %}<div class="more"><button class="ghost" id="more" type="button">Show more products</button></div>{% endif %}
    <noscript><p class="muted more">Showing the {{ first_rows|length }} largest gaps. The full list is in <a href="data/comparison.csv">comparison.csv</a>.</p></noscript>
  </div>
</section>

<section class="band" aria-labelledby="h-demo">
  <div class="wrap">
    <div class="section-head">
      <div>
        <span class="tag">Demo on public data</span>
        <h2 id="h-demo" style="margin-top:8px">Your price vs competitors</h2>
        <p>Pick any retailer as "your store". Its price index is its price divided by the median price of the other retailers for the same product, times 100, over products that both it and at least one other retailer have in stock.</p>
      </div>
      {% if demos %}<label class="controls">Your store<select id="you">{% for d in demos %}<option value="{{ d.retailer_id }}">{{ names[d.retailer_id] }}</option>{% endfor %}</select></label>{% endif %}
    </div>
    {% for d in demos %}
    <div class="demo" data-retailer="{{ d.retailer_id }}"{% if not loop.first %} hidden{% endif %}>
      <div class="kpis" style="margin-top:0;margin-bottom:16px">
        <div class="card kpi"><div class="label">Price index</div><div class="value">{{ "%.1f"|format(d.index) }}</div><div class="note">100 = market median</div></div>
        <div class="card kpi"><div class="label">Products shared</div><div class="value">{{ d.products_shared }}</div><div class="note">in stock here and elsewhere</div></div>
        <div class="card kpi"><div class="label">More than 5% above</div><div class="value">{{ d.above|length }}</div><div class="note">of the market median</div></div>
        <div class="card kpi"><div class="label">More than 5% below</div><div class="value">{{ d.below|length }}</div><div class="note">of the market median</div></div>
      </div>
      <div class="demo-grid">
        <div class="card">
          <h3>Price index by brand</h3>
          <div class="legend"><span><i style="background:var(--lower)"></i>lower than the market median</span><span><i style="background:var(--higher)"></i>higher than the market median</span></div>
          {{ d.svg | safe }}
        </div>
        <div class="card">
          <h3>More than 5% above the market median</h3>
          <ul class="list">{% for i in d.above[:8] %}<li><span><span class="prod">{{ i.product }}</span><br><span class="muted">{{ i.brand }} · ${{ i.price_usd }} vs median ${{ i.market_median_usd }}</span></span><span class="diff up">+{{ "%.1f"|format(i.difference_pct) }}%</span></li>{% else %}<li class="muted">None</li>{% endfor %}</ul>
          <h3 style="margin-top:18px">More than 5% below the market median</h3>
          <ul class="list">{% for i in d.below[:8] %}<li><span><span class="prod">{{ i.product }}</span><br><span class="muted">{{ i.brand }} · ${{ i.price_usd }} vs median ${{ i.market_median_usd }}</span></span><span class="diff down">−{{ "%.1f"|format(-i.difference_pct) }}%</span></li>{% else %}<li class="muted">None</li>{% endfor %}</ul>
        </div>
      </div>
    </div>
    {% else %}
    <div class="card empty">The demo appears once products are compared.</div>
    {% endfor %}
  </div>
</section>

<section class="band alt" aria-labelledby="h-changes">
  <div class="wrap">
    <div class="section-head"><div><h2 id="h-changes">What changed today</h2><p>Price moves, a new lowest-price retailer, and products going out of or back in stock, on the compared products since the previous run.</p></div></div>
    <div class="card tablecard"><div class="scroll">
      <table class="stack">
        <thead><tr><th scope="col">Product</th><th scope="col">Change</th><th scope="col">Retailer</th><th scope="col" class="num">Before</th><th scope="col" class="num">Now</th></tr></thead>
        <tbody>
        {% for c in changes[:30] %}
          <tr>
            <td data-label=""><div class="prod"><small>{{ c.brand }}</small>{{ c.product }}</div></td>
            <td data-label="Change">{% if c.event == 'price_down' %}<span class="diff down">price down {{ c.change_pct }}%</span>{% elif c.event == 'price_up' %}<span class="diff up">price up +{{ c.change_pct }}%</span>{% elif c.event == 'new_lowest' %}new lowest price{% elif c.event == 'out_of_stock' %}out of stock{% else %}back in stock{% endif %}</td>
            <td data-label="Retailer">{% for rid in c.retailer_id.split() %}{{ names.get(rid, rid) }}{% if not loop.last %}, {% endif %}{% endfor %}</td>
            <td class="num" data-label="Before">{% if c.event in ('price_up', 'price_down') %}${{ c.old_value }}{% elif c.event == 'new_lowest' %}{% for rid in c.old_value.split() %}{{ names.get(rid, rid) }}{% if not loop.last %}, {% endif %}{% endfor %}{% else %}{{ c.old_value }}{% endif %}</td>
            <td class="num" data-label="Now">{% if c.event in ('price_up', 'price_down') %}${{ c.new_value }}{% elif c.event == 'new_lowest' %}–{% else %}{{ c.new_value }}{% endif %}</td>
          </tr>
        {% else %}
          <tr><td colspan="5" class="empty">No changes on the compared products today.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div></div>
    {% if changes|length > 30 %}<p class="muted more">{{ changes|length - 30 }} more in the <a href="https://github.com/{{ public.repo }}/tree/{{ public.branch }}/data/changes">change log</a>.</p>{% endif %}
  </div>
</section>

<section class="band" aria-labelledby="h-match">
  <div class="wrap">
    <div class="section-head"><div><h2 id="h-match">How are the same products found at different stores?</h2><p>A product is compared only when the match is certain enough. Everything else is listed as a possible match and never compared.</p></div></div>
    <div class="tiers">
      <div class="card"><div class="label muted">1 · Barcode</div><div class="n">{{ (comp.by_tier or {}).get('gtin', 0) }}</div><p>Same GTIN barcode at both stores. Exact.</p></div>
      <div class="card"><div class="label muted">2 · Brand + part number</div><div class="n">{{ (comp.by_tier or {}).get('mpn', 0) }}</div><p>Same brand and the same manufacturer part number.</p></div>
      <div class="card"><div class="label muted">3 · Brand + model + options</div><div class="n">{{ (comp.by_tier or {}).get('fuzzy', 0) }}</div><p>Same brand, model words and options, scored; used only above a measured threshold.</p></div>
      <div class="card"><div class="label muted">Possible matches</div><div class="n">{{ "{:,}".format(comp.possible_matches or 0) }}</div><p>Below the bar: <a href="https://github.com/{{ public.repo }}/blob/{{ public.branch }}/data/latest/possible_matches.csv">listed</a>, never compared.</p></div>
    </div>
    {% if precision %}
    <div class="card" style="margin-top:12px">
      <h3>Matching precision, measured blind</h3>
      <p style="margin-top:6px">On {{ precision.measured_at[:10] }}, the part-number and name matchers ran with every barcode hidden. Of the pairs they proposed where both stores publish a barcode, {% if precision.combined_evaluated %}<b>{{ precision.combined_true }} of {{ precision.combined_evaluated }}</b> were the same item (precision {{ precision.combined_precision | share }}, recall {{ precision.combined_recall | share }} of {{ precision.gtin_pairs }} barcode pairs){% elif held and held.cleared %}at best <b>{{ held.precision | share }}</b> were the same item ({{ held.evaluated }} pairs). The previous run's test was below the 98% needed, so this run compares barcode matches only ({{ precision.gtin_pairs }} barcode pairs today); this run's result clears it, so name matches are used again from the next run{% elif held %}at best <b>{{ held.precision | share }}</b> were the same item ({{ held.evaluated }} pairs), below the 98% needed on at least 100 pairs, so only barcode matches are compared ({{ precision.gtin_pairs }} barcode pairs today){% else %}none were used yet: until a threshold reaches 98% precision on at least 100 pairs, only barcode matches are compared ({{ precision.gtin_pairs }} barcode pairs today){% endif %}. <a href="https://github.com/{{ public.repo }}/blob/{{ public.branch }}/docs/precision.md">Method and manual check</a>.</p>
    </div>
    {% endif %}
  </div>
</section>

<section class="band alt" aria-labelledby="h-retailers">
  <div class="wrap">
    <div class="section-head"><div><h2 id="h-retailers">Which retailers are compared?</h2><p>US online stores, read once a day from their public catalogs, politely and within their robots.txt rules.</p></div></div>
    <div class="card tablecard"><div class="scroll">
      <table class="stack">
        <thead><tr><th scope="col">Retailer</th><th scope="col">Last run</th><th scope="col" class="num">Product options read</th><th scope="col" class="num">Products compared</th></tr></thead>
        <tbody>
        {% for r in retailers %}{% set rep = reports.get(r.id, {}) %}
          <tr>
            <td data-label=""><div class="prod">{{ r.name }}<small class="mono">{{ r.host }}</small></div></td>
            <td data-label="Last run">{% if rep.status == 'ok' %}read completely{% elif rep %}not updated{% else %}–{% endif %}</td>
            <td class="num" data-label="Options read">{{ "{:,}".format(rep.variants or 0) }}</td>
            <td class="num" data-label="Compared">{{ compared_by[r.id] }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div></div>
  </div>
</section>

<section class="band" aria-labelledby="h-data">
  <div class="wrap">
    <div class="section-head"><div><h2 id="h-data">Download the data</h2></div></div>
    <div class="downloads">
      <a class="card" href="data/comparison.csv"><b>comparison.csv</b>Today's comparison: one row per product, each retailer's price, stock and link.</a>
      <a class="card" href="https://github.com/{{ public.repo }}/releases/latest"><b>Monthly history (Parquet)</b>Every price and stock version of every offer, per month.</a>
      <a class="card" href="data/feed.json"><b>feed.json</b>Run status, data checks and the comparison totals.</a>
      <a class="card" href="https://github.com/{{ public.repo }}"><b>Source code</b>The whole pipeline, its tests and every run's evidence.</a>
    </div>
  </div>
</section>
</main>
<footer>
  <div class="wrap">
    <p>Built and maintained by {{ public.owner }}, founder of {{ public.company }} · <a href="{{ public.company_site }}">steadydata.co</a> · <a href="{{ public.site }}">siddharthkumar.com</a></p>
    <p>Public prices and stock only, no personal data. Prices are shown as found; differences are numbers, not judgments. Store and product names belong to their owners. A retailer can opt out at <a href="mailto:{{ public.email }}">{{ public.email }}</a>; removal within 24 hours.</p>
  </div>
</footer>
<script id="data" type="application/json">{{ data_json | safe }}</script>
<script src="assets/app.js" defer></script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--retailers", type=Path, default=Path("config/retailers.yml"))
    p.add_argument("--public", type=Path, default=Path("config/public.yml"))
    p.add_argument("--out", type=Path, default=Path("site"))
    a = p.parse_args(argv)
    print(build(a.data, a.retailers, a.public, a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
