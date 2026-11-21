"""README visuals, generated from the latest real run.

    python -m crossprice.visuals --data data --out assets

Writes ``hero.svg`` and ``pipeline.svg`` and a still copy of each
(``*-still.svg``: the final frame, no animation). Rules (F1 D-022 and D-025,
docs/decisions.md D-018):

* Loaded as an image in the README, so no external fonts or scripts: the
  dashboard's self-hosted subsets are embedded as base64 WOFF2.
* CSS animation only, an 8 s loop whose last 2 s hold the final frame. The final
  frame is every element's default style, so a renderer without animation, the
  still copy and ``prefers-reduced-motion`` all show the result.
* Phone-readable: in the 1000 px viewBox, headings at least 36 px and every other
  text at least 30 px.
* Every number and row comes from the run files; the alt text repeats them.
* SteadyData light system: page #FFFFFF, card border #E2EAE8, headings #0B1416,
  body #3D4B49, muted #5F716E, lower #0E8A7D, higher #D98E14 with text labels.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from crossprice.match import strip_brand

ASSETS = Path(__file__).parent / "site_assets" / "fonts"
PAGE, ALT, LINE = "#FFFFFF", "#F3F8F7", "#E2EAE8"
INK, BODY, MUTED = "#0B1416", "#3D4B49", "#5F716E"
ACCENT, LOWER, HIGHER, SOFT = "#0B7468", "#0E8A7D", "#D98E14", "#E3F3F0"
LOOP_S = 8
MIN_HEADING_PX = 36
MIN_TEXT_PX = 30
FONTS = {
    ("PJ", 400): "plus-jakarta-sans-400.woff2",
    ("PJ", 700): "plus-jakarta-sans-700.woff2",
    ("PJ", 800): "plus-jakarta-sans-800.woff2",
}

BASE_CSS = f"""
text{{font-family:PJ,"Plus Jakarta Sans",system-ui,sans-serif;font-variant-numeric:tabular-nums}}
.h{{fill:{INK};font-weight:800}}.t{{fill:{INK};font-weight:700}}.b{{fill:{BODY}}}.m{{fill:{MUTED}}}
.lower{{fill:{LOWER}}}.higher{{fill:{HIGHER}}}
"""


def _fonts_css() -> str:
    out = []
    for (family, weight), name in FONTS.items():
        data = base64.b64encode((ASSETS / name).read_bytes()).decode()
        out.append(
            f"@font-face{{font-family:{family};font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
        )
    return "".join(out)


@dataclass(frozen=True)
class Visual:
    width: int
    height: int
    title: str
    desc: str
    body: str
    animation: str
    final: str  # declarations of the final frame, the default state

    def render(self, animated: bool = True) -> str:
        css = _fonts_css() + BASE_CSS + self.final
        if animated:
            forced = re.sub(r"([^;{}]+:[^;{}]+)(?=[;}])", r"\1!important", self.final)
            css += (
                self.animation
                + "@media (prefers-reduced-motion:reduce){*{animation:none!important}"
                + forced
                + "}"
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
            f'width="{self.width}" height="{self.height}" role="img" '
            f'aria-labelledby="t d"><title id="t">{html.escape(self.title)}</title>'
            f'<desc id="d">{html.escape(self.desc)}</desc><style>{css}</style>'
            f'<rect width="100%" height="100%" fill="{PAGE}"/>{self.body}</svg>'
        )


def _fade(cls: str, start: float, end: float) -> str:
    """Keyframes: hidden until ``start`` s, visible from ``end`` s to the loop's end."""
    a, b = start / LOOP_S * 100, end / LOOP_S * 100
    return (
        f"@keyframes k{cls}{{0%,{a:.1f}%{{opacity:0;transform:translateY(12px)}}"
        f"{b:.1f}%,100%{{opacity:1;transform:none}}}}"
        f".{cls}{{animation:k{cls} {LOOP_S}s ease-out infinite}}"
    )


def _grow(cls: str, start: float, end: float) -> str:
    a, b = start / LOOP_S * 100, end / LOOP_S * 100
    return (
        f"@keyframes k{cls}{{0%,{a:.1f}%{{transform:scaleX(0)}}{b:.1f}%,100%{{transform:scaleX(1)}}}}"
        f".{cls}{{transform-box:fill-box;transform-origin:left;"
        f"animation:k{cls} {LOOP_S}s ease-out infinite}}"
    )


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _fit(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def hero(facts: dict[str, Any]) -> Visual:
    """Problem, one real product across retailers, result as one number."""
    row = facts["hero_row"]
    offers = row["offers"][:4]
    low = min(o["cents"] for o in offers)
    high = max(o["cents"] for o in offers)
    w, h = 1000, 640
    parts = [
        f'<g class="b1"><text class="h" x="48" y="84" font-size="46">Same product, different price</text>'
        f'<text class="b" x="48" y="134" font-size="30">{facts["retailers"]} US {_esc(facts["vertical"])} stores, checked every day</text></g>',
        f'<g class="b2"><rect x="32" y="168" width="936" height="{120 + 62 * len(offers)}" rx="14" fill="{PAGE}" stroke="{LINE}" stroke-width="2"/>'
        f'<text class="m" x="64" y="214" font-size="30">{_esc(_fit(row["brand"], 22))}</text>'
        f'<text class="t" x="64" y="252" font-size="32">{_esc(_fit(row["product"], 46))}</text></g>',
    ]
    animation = _fade("b1", 0.0, 0.6) + _fade("b2", 0.8, 1.4)
    final = ""
    for i, o in enumerate(offers):
        y = 300 + 62 * i
        is_low = o["cents"] == low
        bar_w = 300 * o["cents"] / high
        cls = f"r{i}"
        label = "lowest" if is_low else f"+{(o['cents'] - low) / low * 100:.1f}%"
        parts.append(
            f'<g class="{cls}"><text class="b" x="64" y="{y + 12}" font-size="30">{_esc(_fit(o["retailer"], 18))}</text>'
            f'<rect class="{cls}bar {"lower" if is_low else "higher"}" x="360" y="{y - 12}" width="{bar_w:.0f}" height="28" rx="4"/>'
            f'<text class="t" x="{360 + bar_w + 16:.0f}" y="{y + 12}" font-size="30">{money(o["cents"])}</text>'
            f'<text class="{"t" if is_low else "m"}" x="936" y="{y + 12}" font-size="30" text-anchor="end">{label}</text></g>'
        )
        animation += _fade(cls, 1.6 + 0.6 * i, 2.1 + 0.6 * i) + _grow(
            f"{cls}bar", 1.8 + 0.6 * i, 2.6 + 0.6 * i
        )
    y0 = 168 + 120 + 62 * len(offers) + 66
    parts.append(
        f'<g class="b3"><text class="h" x="48" y="{y0}" font-size="44">{facts["products_matched"]:,} products compared</text>'
        f'<text class="b" x="48" y="{y0 + 46}" font-size="30">lowest price, price gap and stock, run of {facts["run_date"]}</text></g>'
    )
    end = 1.6 + 0.6 * len(offers) + 0.8
    animation += _fade("b3", end, end + 0.6)
    final += ""
    h = y0 + 86
    rows_text = "; ".join(f"{o['retailer']} {money(o['cents'])}" for o in offers)
    return Visual(
        width=w,
        height=h,
        title="Same product, different price",
        desc=(
            f"{row['brand']} {row['product']} at {len(offers)} stores on {facts['run_date']}: "
            f"{rows_text}. {facts['products_matched']:,} products compared across "
            f"{facts['retailers']} US {facts['vertical']} stores in that run."
        ),
        body="".join(parts),
        animation=animation,
        final=final,
    )


def hero_square(facts: dict[str, Any]) -> Visual:
    """The hero as a 1080 x 1080 square for the LinkedIn video: same beats, text 40 px or more."""
    row = facts["hero_row"]
    offers = row["offers"][:4]
    low = min(o["cents"] for o in offers)
    high = max(o["cents"] for o in offers)
    parts = [
        f'<g class="b1"><text class="h" x="64" y="130" font-size="64">Same product,</text>'
        f'<text class="h" x="64" y="206" font-size="64">different price</text>'
        f'<text class="b" x="64" y="266" font-size="40">{facts["retailers"]} US {_esc(facts["vertical"])} stores, daily</text></g>',
        f'<g class="b2"><rect x="40" y="310" width="1000" height="{150 + 86 * len(offers)}" rx="18" fill="{PAGE}" stroke="{LINE}" stroke-width="3"/>'
        f'<text class="m" x="80" y="372" font-size="40">{_esc(_fit(row["brand"], 24))}</text>'
        f'<text class="t" x="80" y="422" font-size="42">{_esc(_fit(row["product"], 36))}</text></g>',
    ]
    animation = _fade("b1", 0.0, 0.6) + _fade("b2", 0.8, 1.4)
    for i, o in enumerate(offers):
        y = 500 + 86 * i
        is_low = o["cents"] == low
        bar_w = 230 * o["cents"] / high
        cls = f"r{i}"
        label = "lowest" if is_low else f"+{(o['cents'] - low) / low * 100:.1f}%"
        parts.append(
            f'<g class="{cls}"><text class="b" x="80" y="{y + 14}" font-size="40">{_esc(_fit(o["retailer"], 13))}</text>'
            f'<rect class="{cls}bar {"lower" if is_low else "higher"}" x="370" y="{y - 16}" width="{bar_w:.0f}" height="36" rx="5"/>'
            f'<text class="t" x="624" y="{y + 14}" font-size="40">{money(o["cents"])}</text>'
            f'<text class="{"t" if is_low else "m"}" x="1000" y="{y + 14}" font-size="40" text-anchor="end">{label}</text></g>'
        )
        animation += _fade(cls, 1.6 + 0.6 * i, 2.1 + 0.6 * i) + _grow(
            f"{cls}bar", 1.8 + 0.6 * i, 2.6 + 0.6 * i
        )
    y0 = 310 + 150 + 86 * len(offers) + 100
    parts.append(
        f'<g class="b3"><text class="h" x="64" y="{y0}" font-size="60">{facts["products_matched"]:,} products</text>'
        f'<text class="b" x="64" y="{y0 + 60}" font-size="40">compared every day, {facts["run_date"]}</text></g>'
    )
    end = 1.6 + 0.6 * len(offers) + 0.8
    animation += _fade("b3", end, end + 0.6)
    return Visual(
        width=1080,
        height=1080,
        title="Same product, different price",
        desc=hero(facts).desc,
        body="".join(parts),
        animation=animation,
        final="",
    )


def pipeline(facts: dict[str, Any]) -> Visual:
    """The four steps, each with its number from the latest run."""
    steps = [
        (
            "1 Read",
            f"{facts['retailers_ok']} store catalogs",
            f"{facts['offers']:,} product options",
        ),
        ("2 Match", "barcode, part number, name", facts["match_line"]),
        ("3 Compare", "lowest price, gap, stock", f"{facts['products_matched']:,} products"),
        ("4 Publish", "CSV, dashboard, feed", f"{facts['changes']:,} changes today"),
    ]
    w, h = 1000, 700
    parts = ['<text class="h" x="48" y="76" font-size="44">How it works, every day</text>']
    animation = ""
    for i, (head, line1, line2) in enumerate(steps):
        col, row = i % 2, i // 2
        x, y = 32 + col * 484, 116 + row * 280
        cls = f"s{i}"
        parts.append(
            f'<g class="{cls}"><rect x="{x}" y="{y}" width="452" height="248" rx="14" fill="{ALT if i % 3 == 0 else PAGE}" stroke="{LINE}" stroke-width="2"/>'
            f'<rect x="{x}" y="{y}" width="10" height="248" rx="4" fill="{ACCENT}"/>'
            f'<text class="h" x="{x + 40}" y="{y + 70}" font-size="40">{_esc(head)}</text>'
            f'<text class="b" x="{x + 40}" y="{y + 134}" font-size="30">{_esc(line1)}</text>'
            f'<text class="t" x="{x + 40}" y="{y + 190}" font-size="32">{_esc(line2)}</text></g>'
        )
        animation += _fade(cls, 0.3 + 1.1 * i, 0.9 + 1.1 * i)
    return Visual(
        width=w,
        height=h,
        title="How it works, every day",
        desc=(
            f"1 Read: {facts['retailers_ok']} store catalogs, {facts['offers']:,} product options. "
            f"2 Match: by barcode, part number and name; {facts['match_line']}. "
            f"3 Compare: lowest price, gap and stock for {facts['products_matched']:,} products. "
            f"4 Publish: CSV, dashboard and feed, {facts['changes']:,} changes today. "
            f"Run of {facts['run_date']}."
        ),
        body="".join(parts),
        animation=animation,
        final="",
    )


def collect(data: Path, retailers_path: Path) -> dict[str, Any]:
    """The facts the visuals show, from runs.jsonl and comparison.csv only."""
    runs = [json.loads(x) for x in (data / "runs.jsonl").read_text().splitlines() if x]
    good = [r for r in runs if r["status"] in ("ok", "partial")]
    last = good[-1]
    comp = last["comparison"]
    names = {
        r["id"]: r["name"]
        for r in yaml.safe_load(retailers_path.read_text(encoding="utf-8"))["retailers"]
    }
    vertical = next(
        iter(
            r["vertical"]
            for r in yaml.safe_load(retailers_path.read_text(encoding="utf-8"))["retailers"]
        )
    )
    with (data / "latest" / "comparison.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    best = None
    for r in rows:
        offers = [
            {"retailer": names.get(rid, rid), "cents": round(float(r[f"{rid}_price_usd"]) * 100)}
            for rid in names
            if r.get(f"{rid}_price_usd") and r.get(f"{rid}_in_stock") == "yes"
        ]
        if len(offers) < 2 or not r["spread_pct"]:
            continue
        # Prefer a real price gap, then products at 3+ stores, barcode-verified ones,
        # and the largest gap.
        spread = float(r["spread_pct"])
        key = (spread > 0, min(len(offers), 3), r["match_tier"] == "gtin", spread)
        if best is None or key > best[0]:
            offers.sort(key=lambda o: (o["cents"], o["retailer"]))
            best = (
                key,
                {
                    "brand": r["brand"],
                    "product": strip_brand(r["brand"], r["product"]),
                    "offers": offers,
                },
            )
    prec = comp["matching_precision"]
    precision_text = (
        f"{prec['value'] * 100:.1f}%" if prec.get("value") is not None else "barcodes only"
    )
    return {
        "vertical": vertical.replace("-", " "),
        "retailers": last["retailers_total"],
        "retailers_ok": last["retailers_ok"],
        "offers": last["offers_observed"],
        "products_matched": comp["products_matched"],
        "precision_text": precision_text,
        "match_line": (
            f"precision {precision_text}" if prec.get("value") is not None else "barcode matches"
        ),
        "changes": last.get("changes_total", 0),
        "run_date": last["started_at"][:10],
        "hero_row": best[1] if best else {"brand": "", "product": "", "offers": []},
    }


def write_all(data: Path, retailers: Path, out: Path) -> list[Path]:
    facts = collect(data, retailers)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    visuals = {"pipeline": pipeline(facts)}
    if facts["hero_row"]["offers"]:
        visuals["hero"] = hero(facts)
    for name, v in visuals.items():
        for suffix, animated in (("", True), ("-still", False)):
            path = out / f"{name}{suffix}.svg"
            path.write_text(v.render(animated), encoding="utf-8")
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--retailers", type=Path, default=Path("config/retailers.yml"))
    p.add_argument("--out", type=Path, default=Path("assets"))
    a = p.parse_args(argv)
    for path in write_all(a.data, a.retailers, a.out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
