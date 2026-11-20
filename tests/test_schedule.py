"""The slot check shared by the daily gate and the watchdog (F1 INC-007)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from crossprice.schedule import CRONS, WATCHDOG_CRONS, check_slot, latest_slot, main

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def run(started: str, status: str = "ok", run_id: str = "r") -> dict[str, object]:
    return {"run_id": run_id, "started_at": started, "status": status}


def _on(path: Path) -> dict[str, Any]:
    wf: dict[Any, Any] = yaml.safe_load(path.read_text())
    on: dict[str, Any] = wf["on" if "on" in wf else True]  # PyYAML reads `on` as True
    return on


@pytest.mark.skipif(not (WF / "daily.yml").exists(), reason="daily workflow not added yet")
def test_crons_match_the_workflows() -> None:
    assert tuple(s["cron"] for s in _on(WF / "daily.yml")["schedule"]) == CRONS
    assert tuple(s["cron"] for s in _on(WF / "watchdog.yml")["schedule"]) == WATCHDOG_CRONS
    assert "slot" in _on(WF / "daily.yml")["workflow_dispatch"]["inputs"]


def test_one_quiet_daily_slot() -> None:
    assert len(CRONS) == 1
    minute = int(CRONS[0].split()[0])
    assert minute not in (0, 30)
    assert not set(WATCHDOG_CRONS) & set(CRONS)


def test_latest_slot() -> None:
    assert latest_slot(at(21, 7, 42)) == at(20, 7, 43)
    assert latest_slot(at(21, 7, 43)) == at(21, 7, 43)
    assert latest_slot(at(21, 10, 19)) == at(21, 7, 43)


def test_late_scheduled_run_skips_a_filled_slot() -> None:
    runs = [run("2026-11-21T10:20:00Z", run_id="x")]
    assert check_slot(runs, at(21, 14, 0))["covered"] == "true"
    assert check_slot([], at(21, 14, 0))["covered"] == "false"


def test_an_external_trigger_names_its_slot() -> None:
    runs = [run("2026-11-20T07:44:00Z")]
    assert check_slot(runs, at(21, 7, 44), slot=at(21, 7, 43))["covered"] == "false"
    assert check_slot(runs, at(21, 7, 44), slot=at(20, 7, 43))["covered"] == "true"


@pytest.mark.parametrize(("status", "covered"), [("held", "true"), ("crashed", "false")])
def test_statuses_that_cover_a_slot(status: str, covered: str) -> None:
    assert check_slot([run("2026-11-21T07:50:00Z", status)], at(21, 10, 19))["covered"] == covered


def test_cli_prints_github_output_lines(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runs = tmp_path / "runs.jsonl"
    runs.write_text('{"run_id":"a","started_at":"2026-11-21T07:50:00Z","status":"ok"}\n')
    main(["check", "--runs", str(runs), "--now", "2026-11-21T10:19:00Z"])
    out = capsys.readouterr().out.splitlines()
    assert out == ["slot=2026-11-21T07:43:00Z", "covered=true", "run_id=a"]
