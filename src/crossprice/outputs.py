"""Small committed outputs: run log, status, badges, change log, public feed.

Status and badges follow F1 (shields.io endpoint files computed only from
``runs.jsonl``); ``data/public/feed.json`` is the ``steadydata.feed/v1`` envelope
with a ``comparison`` block (docs/architecture.md).
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crossprice.compare import CHANGE_COLUMNS
from crossprice.schedule import accounting

GOOD = "0B7468"  # SteadyData accent
LOOK = "D98E14"  # "look here" amber
GOOD_STATUSES = ("ok", "partial")
FEED_SCHEMA = "steadydata.feed/v1"
FEED_DAYS = 30


def iso(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def append_changes(data: Path, events: list[dict[str, Any]], run_at: datetime) -> Path | None:
    """Append the run's change rows to ``data/changes/YYYY/YYYY-MM-DD.csv``."""
    if not events:
        return None
    path = data / "changes" / f"{run_at:%Y}" / f"{run_at:%Y-%m-%d}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CHANGE_COLUMNS, lineterminator="\n")
        if new_file:
            writer.writeheader()
        writer.writerows(events)
    return path


def read_runs(data: Path) -> list[dict[str, Any]]:
    path = data / "runs.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def append_run(data: Path, record: dict[str, Any]) -> None:
    data.mkdir(parents=True, exist_ok=True)
    with (data / "runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _badge(label: str, message: str, color: str) -> dict[str, Any]:
    return {"schemaVersion": 1, "label": label, "message": message, "color": color}


def build_status(
    runs: list[dict[str, Any]], now: datetime, crons: tuple[str, ...] | None = None
) -> dict[str, Any]:
    """status.json content, computed only from runs.jsonl."""
    good = [r for r in runs if r["status"] in GOOD_STATUSES]
    last = runs[-1] if runs else None
    last_good = good[-1] if good else None
    first_good = parse_iso(good[0]["started_at"]) if good else None
    days_running = max(0, (now.date() - first_good.date()).days + 1) if first_good else 0
    # Every daily slot since the first run: on time (a good run started within 2 h),
    # late (later that day), held or missed (F1 INC-009).
    schedule = accounting(runs, now, crons)
    comparison = (last_good or {}).get("comparison") or {}
    return {
        "generated_at": iso(now),
        "first_run": iso(first_good) if first_good else None,
        "days_running": days_running,
        "runs_total": len(runs),
        "runs_good": len(good),
        "runs_held": sum(1 for r in runs if r["status"] == "held"),
        "missed_runs": schedule["missed"],
        "missed_slots": schedule["missed_slots"],
        "schedule": schedule,
        "last_run": (
            {
                "run_id": last["run_id"],
                "started_at": last["started_at"],
                "status": last["status"],
                "duration_s": last.get("duration_s"),
                "retailers_ok": last.get("retailers_ok"),
                "retailers_total": last.get("retailers_total"),
                "offers": last.get("offers_live"),
                "hold_reasons": [h["message"] for h in last.get("guard", {}).get("holds", [])],
                "run_url": last.get("run_url"),
            }
            if last
            else None
        ),
        "products_matched": comparison.get("products_matched", 0),
        "matching_precision": comparison.get("matching_precision"),
    }


def on_time_text(schedule: dict[str, Any]) -> tuple[str, str]:
    """(label, value) of the on-time count shown to readers (F1 INC-009).

    It starts at the first slot dispatched by the on-time trigger: before that,
    ("on time", "from next run"); after, ("on time since 22 Nov", "3 of 3").
    """
    since = schedule.get("on_time_since")
    counts = schedule.get("since") or {}
    if not since or not counts.get("slots"):
        return "on time", "from next run"
    day = parse_iso(str(since))
    return f"on time since {day.day} {day:%b}", f"{counts['on_time']} of {counts['slots']}"


def _on_time_badge(schedule: dict[str, Any]) -> dict[str, Any]:
    label, value = on_time_text(schedule)
    counts = schedule.get("since") or {}
    if value == "from next run":
        return _badge(label, value, GOOD)
    return _badge(label, value, GOOD if counts["on_time"] == counts["slots"] else LOOK)


def write_status(data: Path, status: dict[str, Any]) -> None:
    """status.json plus one shields.io endpoint file per badge."""
    (data / "status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    badges = data / "badges"
    badges.mkdir(parents=True, exist_ok=True)
    last = status["last_run"]
    if last:
        when = parse_iso(last["started_at"]).strftime("%Y-%m-%d %H:%M UTC")
        last_badge = _badge(
            "last run", f"{when} {last['status']}", GOOD if last["status"] == "ok" else LOOK
        )
    else:
        last_badge = _badge("last run", "none yet", LOOK)
    files = {
        "last-run.json": last_badge,
        "days-running.json": _badge("days running", str(status["days_running"]), GOOD),
        "runs.json": _badge("runs", str(status["runs_total"]), GOOD),
        "missed-runs.json": _badge(
            "missed runs", str(status["missed_runs"]), GOOD if status["missed_runs"] == 0 else LOOK
        ),
        "on-time-runs.json": _on_time_badge(status.get("schedule") or {}),
        "matched-products.json": _badge(
            "matched products",
            f"{status['products_matched']:,}",
            GOOD if status["products_matched"] else LOOK,
        ),
    }
    for name, body in files.items():
        (badges / name).write_text(json.dumps(body) + "\n", encoding="utf-8")


def build_feed(
    runs: list[dict[str, Any]],
    status: dict[str, Any],
    public: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """The public feed (``steadydata.feed/v1``), from runs.jsonl and status.json only."""
    last = runs[-1] if runs else {}
    good = [r for r in runs if r["status"] in GOOD_STATUSES]
    last_good = good[-1] if good else {}
    comparison = last_good.get("comparison") or {}
    daily = [
        {
            "date": r["started_at"][:10],
            "status": r["status"],
            "offers": r.get("offers_live", 0),
            "products_matched": (r.get("comparison") or {}).get("products_matched", 0),
            "changes": r.get("changes_total", 0),
        }
        for r in runs[-FEED_DAYS:]
    ]
    return {
        "schema": FEED_SCHEMA,
        "monitor": {
            "id": public["id"],
            "name": public["name"],
            "repo": f"https://github.com/{public['repo']}",
            "dashboard": public["dashboard"],
            "generated_at": iso(now),
        },
        "last_run": {
            "run_id": last.get("run_id"),
            "started_at": last.get("started_at"),
            "finished_at": last.get("finished_at"),
            "status": last.get("status"),
            "duration_s": last.get("duration_s"),
            "run_url": last.get("run_url"),
        },
        "checks": last.get("checks", []),
        "totals": {
            "runs": status["runs_total"],
            "runs_good": status["runs_good"],
            "days_running": status["days_running"],
            "missed_runs": status["missed_runs"],
            "runs_delivered": (status.get("schedule") or {}).get("delivered", 0),
            "retailers": last_good.get("retailers_total", 0),
            "offers": last_good.get("offers_live", 0),
        },
        "daily": daily,
        "comparison": {
            "products_matched": comparison.get("products_matched", 0),
            "retailers": comparison.get("retailers", 0),
            "matching_precision": comparison.get("matching_precision"),
            "avg_spread_pct": comparison.get("avg_spread_pct"),
        },
    }


def write_json(path: Path, body: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, sort_keys=False) + "\n", encoding="utf-8")
