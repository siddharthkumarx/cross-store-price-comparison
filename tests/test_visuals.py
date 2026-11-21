"""README visuals: phone-readable, small, self-contained, final frame by default."""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest

import crossprice.run as run_mod
from crossprice.run import run
from crossprice.visuals import MIN_HEADING_PX, MIN_TEXT_PX, write_all
from tests.test_pipeline import T0, _cfg, _client_for, workdir  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def svgs(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: F811
    monkeypatch.setattr(run_mod, "make_client", _client_for({}))
    run(_cfg(workdir), now=T0)
    monkeypatch.setattr(run_mod, "make_client", _client_for({"beta.example": {201: "159.95"}}))
    run(_cfg(workdir), now=T0 + timedelta(days=1))
    out = workdir / "assets"
    write_all(workdir / "data", workdir / "retailers.yml", out)
    return out


def test_every_visual_has_a_still_copy_and_stays_small(svgs: Path) -> None:
    for name in ("hero", "pipeline"):
        for suffix in ("", "-still"):
            path = svgs / f"{name}{suffix}.svg"
            text = path.read_text()
            assert path.stat().st_size < 1_000_000
            assert "<title" in text
            assert "<desc" in text
            assert "http://" not in text.replace("http://www.w3.org/2000/svg", "")
            assert "https://" not in text
            assert "<script" not in text
        assert "@keyframes" in (svgs / f"{name}.svg").read_text()
        assert "@keyframes" not in (svgs / f"{name}-still.svg").read_text()


def test_text_is_readable_on_a_phone(svgs: Path) -> None:
    for name in ("hero", "pipeline"):
        sizes = [
            int(s) for s in re.findall(r'font-size="(\d+)"', (svgs / f"{name}.svg").read_text())
        ]
        assert sizes
        assert min(sizes) >= MIN_TEXT_PX
        assert max(sizes) >= MIN_HEADING_PX


def test_numbers_are_in_the_alt_text(svgs: Path) -> None:
    desc = re.search(r"<desc[^>]*>(.*?)</desc>", (svgs / "hero.svg").read_text())
    assert desc is not None
    assert "$159.95" in desc.group(1)
    assert "2 products compared" in desc.group(1)


def _playwright() -> bool:
    if not shutil.which("node"):
        return False
    probe = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True)
    return probe.returncode == 0


@pytest.mark.skipif(not _playwright(), reason="Playwright for Node is not installed")
def test_reduced_motion_and_still_copy_show_the_final_frame(svgs: Path) -> None:
    result = subprocess.run(
        ["node", str(ROOT / "scripts" / "check_visuals.cjs"), str(svgs)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
