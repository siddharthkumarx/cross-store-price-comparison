"""The README and dataset card render from run files, with no template leftovers."""

from __future__ import annotations

import re
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

import crossprice.run as run_mod
from crossprice.readme import context, render
from crossprice.run import run
from tests.test_pipeline import T0, _cfg, _client_for, workdir  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def rendered(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:  # noqa: F811
    monkeypatch.setattr(run_mod, "make_client", _client_for({}))
    run(_cfg(workdir), now=T0)
    monkeypatch.setattr(run_mod, "make_client", _client_for({"beta.example": {201: "159.95"}}))
    run(_cfg(workdir), now=T0 + timedelta(days=1))
    root = workdir / "root"
    (root / "config").mkdir(parents=True)
    shutil.copy(workdir / "retailers.yml", root / "config" / "retailers.yml")
    shutil.copy(ROOT / "config" / "public.yml", root / "config" / "public.yml")
    shutil.copytree(ROOT / "docs", root / "docs")
    ctx = context(workdir / "data", root)
    return {
        name: render(ROOT / "templates" / name, ctx)
        for name in ("README.md.j2", "DATASET_CARD.md.j2")
    }


def test_no_template_leftovers_comments_or_placeholders(rendered: dict[str, str]) -> None:
    for text in rendered.values():
        assert "{{" not in text
        assert "{%" not in text
        assert "<!--" not in text
        assert not re.search(r"\b(TODO|TBD|lorem)\b", text, re.IGNORECASE)


def test_readme_client_part_comes_first(rendered: dict[str, str]) -> None:
    text = rendered["README.md.j2"]
    order = [
        "assets/hero.svg",
        "# Cross-store price comparison",
        "last-run.json",
        "Open the dashboard",
        "## What does a daily cross-store price comparison give you?",
        "### What changed today",
        "## Why can you trust these numbers?",
        "## How does cross-store price matching work?",
        "## What broke, and how was it fixed?",
        "## Who uses cross-store price data?",
        "## Want this for your own stores?",
        "## FAQ",
        "## Data dictionary",
        "<summary><b>For engineers</b></summary>",
        "## Data use and compliance",
        "## License",
        "Built and maintained by Siddharth Kumar, founder of SteadyData",
    ]
    positions = [text.index(s) for s in order]
    assert positions == sorted(positions)
    assert "https://steadydata.co/contact/" in text
    assert "hello@steadydata.co" in text


def test_numbers_come_from_the_run(rendered: dict[str, str]) -> None:
    text = rendered["README.md.j2"]
    assert "Encore ESP Grinder" in text  # a real row of the run
    assert "$159.95" in text
    assert "price drop" in text.lower()
    assert "2026-11-21" in text


def test_sample_rows_prefer_a_price_gap() -> None:
    from crossprice.readme import sample_rows

    base = {"match_tier": "gtin", "lowest_price_retailers": "a", "brand": "B", "product": "B X"}
    rows = [
        {**base, "spread_pct": "0.0", "retailers_in_stock": "3"},
        {**base, "spread_pct": "12.5", "retailers_in_stock": "2"},
    ]
    picked = sample_rows(rows, {"a": "A"}, n=1)
    assert picked[0]["spread_pct"] == "12.5"
    assert picked[0]["title"] == "X"


def test_held_back_picks_the_best_measured_point_of_an_unused_tier() -> None:
    from crossprice.precision import held_back

    curve = [
        {"threshold": 0.5, "evaluated": 280, "true": 267, "precision": 0.9536},
        {"threshold": 0.95, "evaluated": 224, "true": 219, "precision": 0.9777},
        {"threshold": 1.0, "evaluated": 90, "true": 90, "precision": 1.0},  # too few pairs
    ]
    used = {"tiers": {"fuzzy": {"threshold_used": 0.76, "curve": curve}}}
    unused = {"tiers": {"fuzzy": {"threshold_used": None, "curve": curve}}}
    assert held_back(used) is None
    assert held_back(None) is None
    best = held_back(unused)
    assert best is not None
    assert (best["tier"], best["threshold"], best["evaluated"]) == ("fuzzy", 0.95, 224)


def test_a_barcode_only_run_says_name_matches_were_held_back(tmp_path: Path) -> None:
    import json

    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    latest = data / "precision" / "latest.json"
    p = json.loads(latest.read_text())
    p["tiers"]["fuzzy"]["threshold_used"] = None
    p.update(combined_evaluated=0, combined_true=0, combined_precision=None)
    latest.write_text(json.dumps(p))
    lines = (data / "runs.jsonl").read_text().splitlines()
    last = json.loads(lines[-1])
    for c in last["checks"]:
        if c["id"] == "matching_precision":
            c["value"] = None
    (data / "runs.jsonl").write_text("\n".join([*lines[:-1], json.dumps(last)]) + "\n")
    text = render(ROOT / "templates" / "README.md.j2", context(data, ROOT))
    assert "name matches held back: best 97.8% on 224 pairs, below 98%" in text
    assert "so only barcode matches were compared" in text
    assert "not measured yet" not in text
