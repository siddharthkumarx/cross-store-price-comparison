"""The slot check shared by the daily gate and the watchdog (F1 INC-007)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from crossprice.schedule import (
    CRONS,
    WATCHDOG_CRONS,
    accounting,
    check_slot,
    dispatch_slot,
    gate,
    latest_slot,
    main,
    slot_states,
)

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


# -- the gate and honest accounting (F1 INC-009) -------------------------------------
def dispatched(started: str, slot: str, by: str = "trigger") -> dict[str, object]:
    return {
        "run_id": started,
        "started_at": started,
        "status": "ok",
        "trigger": "workflow_dispatch",
        "dispatch": {"slot": dispatch_slot(slot), "by": by},
    }


def scheduled(started: str) -> dict[str, object]:
    return {"run_id": started, "started_at": started, "status": "ok", "trigger": "schedule"}


def test_on_time_dispatch_runs_and_the_late_schedule_event_then_skips() -> None:
    first = gate("workflow_dispatch", [], at(22, 7, 43), slot="2026-11-22T07:43Z")
    assert (first["run"], first["slot"]) == ("true", "2026-11-22T07:43:00Z")
    runs = [run("2026-11-22T07:44:30Z", run_id="20261122T074430Z")]
    late = gate("schedule", runs, at(22, 15, 40))  # GitHub's event, 8 h late
    assert late["run"] == "false"
    assert "20261122T074430Z" in late["reason"]
    again = gate("workflow_dispatch", runs, at(22, 8, 10), slot="2026-11-22T07:43Z")
    assert again["run"] == "false"  # a retry does not read the stores again
    assert gate("schedule", [], at(22, 15, 40))["run"] == "true"  # nothing filled it


def test_dispatch_slot_rules() -> None:
    assert gate("workflow_dispatch", [], at(22, 8), slot="2026-11-22T08:00Z")["run"] == "false"
    stale = gate("workflow_dispatch", [], at(23, 7, 50), slot="2026-11-22T07:43Z")
    assert (stale["run"], "no longer the current slot" in stale["reason"]) == ("false", True)
    assert gate("workflow_dispatch", [], at(22, 7), slot="tomorrow")["run"] == "false"
    early = gate("workflow_dispatch", [], at(22, 7, 41), slot="2026-11-22T07:43Z")
    assert (early["run"], early["wait_s"]) == ("true", "120")
    assert gate("workflow_dispatch", [], at(22, 7, 20), slot="2026-11-22T07:43Z")["run"] == "false"
    assert gate("workflow_dispatch", [], at(22, 7, 43), slot="check")["run"] == "false"
    manual = gate("workflow_dispatch", [run("2026-11-22T07:44:00Z")], at(22, 9))
    assert manual["run"] == "true"


def test_gate_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runs = tmp_path / "runs.jsonl"
    runs.write_text('{"run_id": "a", "started_at": "2026-11-22T07:44:00Z", "status": "ok"}\n')
    assert (
        main(["gate", "--runs", str(runs), "--now", "2026-11-22T15:00:00Z", "--event", "schedule"])
        == 0
    )
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == ["run=false", "slot=2026-11-22T07:43:00Z"]


def test_slot_states_on_time_late_held_missed_pending() -> None:
    runs = [
        run("2026-11-21T02:45:59Z", run_id="before"),  # before the day's slot: fills nothing
        run("2026-11-21T16:10:00Z", run_id="late"),  # same day: late
        run("2026-11-22T09:43:00Z", run_id="edge"),  # exactly 2 h: on time
        run("2026-11-24T08:00:00Z", status="held", run_id="h"),
        run("2026-11-25T08:00:00Z", status="crashed", run_id="c"),  # a crash fills nothing
    ]
    states = slot_states(runs, at(26, 7, 50))
    assert [(s.slot.day, s.state) for s in states] == [
        (21, "late"),
        (22, "on_time"),
        (23, "missed"),
        (24, "held"),
        (25, "missed"),
        (26, "pending"),
    ]
    acc = accounting(runs, at(26, 7, 50))
    assert (acc["slots"], acc["delivered"], acc["on_time"], acc["late"], acc["missed"]) == (
        5,
        2,
        1,
        1,
        2,
    )


def test_a_late_run_is_not_a_missed_run_and_on_time_counts_start_with_the_trigger() -> None:
    runs = [
        run("2026-11-21T02:45:59Z", run_id="manual"),
        dispatched("2026-11-21T10:20:00Z", "2026-11-21T07:43Z", by="watchdog"),
    ]
    acc = accounting(runs, at(22, 5))
    assert (acc["missed"], acc["late"], acc["delivered"]) == (0, 1, 1)
    assert acc["on_time_since"] is None  # a watchdog dispatch is not the on-time trigger
    runs += [
        dispatched("2026-11-22T07:44:00Z", "2026-11-22T07:43Z"),
        scheduled("2026-11-23T15:00:00Z"),
    ]
    acc = accounting(runs, at(24, 5))
    assert acc["on_time_since"] == "2026-11-22T07:43:00Z"
    assert acc["since"] == {"slots": 2, "on_time": 1, "late": 1, "held": 0, "missed": 0}
    assert str(acc["note"]).startswith("Before 22 Nov 2026, ")


def test_runs_record_who_dispatched_their_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    from crossprice.run import _env_run_meta

    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("DISPATCH_SLOT", "2026-11-22T07:43Z")
    monkeypatch.setenv("DISPATCH_BY", "")
    assert _env_run_meta()["dispatch"] == {"slot": "2026-11-22T07:43:00Z", "by": "trigger"}
    monkeypatch.setenv("DISPATCH_BY", "watchdog")
    assert _env_run_meta()["dispatch"]["by"] == "watchdog"
    monkeypatch.setenv("DISPATCH_SLOT", "check")
    assert "dispatch" not in _env_run_meta()
    monkeypatch.setenv("DISPATCH_SLOT", "auto")  # resolved by the gate, not by the run
    assert "dispatch" not in _env_run_meta()


def test_workflows_pass_the_dispatch_to_the_run_record() -> None:
    daily = yaml.safe_load((WF / "daily.yml").read_text())
    assert "by" in _on(WF / "daily.yml")["workflow_dispatch"]["inputs"]
    decide = next(s for s in daily["jobs"]["slot"]["steps"] if s.get("id") == "decide")
    assert decide["env"]["SLOT"] == "${{ inputs.slot }}"
    assert "${{" not in decide["run"]  # no expression injection
    step = next(s for s in daily["jobs"]["run"]["steps"] if s.get("id") == "run")
    # The gate's resolved slot, so `slot: auto` is recorded as the slot it filled.
    assert step["env"] == {
        "DISPATCH_SLOT": "${{ inputs.slot && (needs.slot.outputs.slot || inputs.slot) || '' }}",
        "DISPATCH_BY": "${{ inputs.by }}",
    }
    assert daily["jobs"]["slot"]["outputs"]["slot"] == "${{ steps.decide.outputs.slot }}"
    watchdog = yaml.safe_load((WF / "watchdog.yml").read_text())
    rescue = next(s for s in watchdog["jobs"]["check"]["steps"] if s.get("id") == "rescue")
    assert '-f slot="$SLOT" -f by=watchdog' in rescue["run"]


def test_note_when_github_never_started_the_scheduled_run() -> None:
    runs = [dispatched("2026-11-21T12:41:42Z", "2026-11-21T07:43Z", by="manual")]
    acc = accounting(runs, at(22, 5))
    assert acc["note"] == (
        "So far GitHub's scheduler did not start the daily run; "
        "the day was still delivered (INC-003)."
    )


# -- slot: auto, for a scheduler with a fixed request body (D-019) -------------------
@pytest.mark.parametrize(("hour", "minute", "wait"), [(7, 41, "120"), (7, 43, "0"), (7, 51, "0")])
def test_auto_fills_the_slot_within_ten_minutes(hour: int, minute: int, wait: str) -> None:
    got = gate("workflow_dispatch", [], at(22, hour, minute), slot="auto")
    assert (got["run"], got["slot"], got["wait_s"]) == ("true", "2026-11-22T07:43:00Z", wait)


@pytest.mark.parametrize(("hour", "minute"), [(9, 0), (7, 32), (7, 54), (6, 17)])
def test_auto_away_from_the_slot_skips_with_one_line(hour: int, minute: int) -> None:
    got = gate("workflow_dispatch", [], at(22, hour, minute), slot="auto")
    assert (got["run"], got["slot"]) == ("false", "")
    assert "no active slot within 10 minutes" in got["reason"]
    assert "\n" not in got["reason"]


@pytest.mark.parametrize(("hour", "minute"), [(0, 17), (12, 17), (18, 17), (7, 43)])
def test_auto_in_black_friday_week_fills_only_the_one_daily_slot(hour: int, minute: int) -> None:
    # No extra runs around Black Friday here (owner rule): only 07:43 runs on 26 Nov.
    got = gate("workflow_dispatch", [], at(26, hour, minute), slot="auto")
    assert got["run"] == ("true" if (hour, minute) == (7, 43) else "false")


def test_a_second_auto_and_the_late_schedule_event_skip_after_an_auto_run() -> None:
    assert gate("workflow_dispatch", [], at(22, 7, 43), slot="auto")["run"] == "true"
    runs = [run("2026-11-22T07:43:40Z", run_id="20261122T074340Z")]
    again = gate("workflow_dispatch", runs, at(22, 7, 46), slot="auto")
    assert again["run"] == "false"
    assert "already filled by run 20261122T074340Z" in again["reason"]
    assert gate("schedule", runs, at(22, 15, 40))["run"] == "false"


def test_an_auto_run_counts_as_the_on_time_trigger() -> None:
    runs = [
        dispatched("2026-11-21T12:41:42Z", "2026-11-21T07:43Z", by="manual"),
        dispatched("2026-11-22T07:43:40Z", "2026-11-22T07:43:00Z", by="trigger"),
    ]
    acc = accounting(runs, at(22, 12))
    assert acc["on_time_since"] == "2026-11-22T07:43:00Z"
    assert acc["on_time_pct"] == 100.0


def test_auto_gate_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["gate", "--runs", str(tmp_path / "none.jsonl"), "--event", "workflow_dispatch"]
    assert main([*args, "--slot", "auto", "--now", "2026-11-22T07:41:00Z"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "run=true",
        "slot=2026-11-22T07:43:00Z",
        "wait_s=120",
        "reason=auto: dispatch for slot 2026-11-22T07:43:00Z: runs",
    ]


def test_daily_workflow_documents_auto() -> None:
    inputs = _on(WF / "daily.yml")["workflow_dispatch"]["inputs"]
    assert "auto" in inputs["slot"]["description"]
