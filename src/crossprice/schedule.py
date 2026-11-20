"""The daily workflow's schedule, as data.

Reused from F1. ``CRONS`` must equal the ``schedule`` entries of
.github/workflows/daily.yml (tests/test_schedule.py checks this). Only the cron subset used there is
supported: fixed minute, hour lists, day-of-month ranges or lists, month lists.

``WATCHDOG_CRONS`` must equal the ``schedule`` entries of
.github/workflows/watchdog.yml. They are not run slots: the watchdog only checks
that the latest slot was run, and starts it if not (F1 INC-007).

    python -m crossprice.schedule check --runs data/runs.jsonl [--slot ISO]

prints ``slot=``, ``covered=`` and ``run_id=`` lines for $GITHUB_OUTPUT.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

# One daily slot at a quiet minute (off the hour and the half hour, where GitHub's
# scheduler queues most jobs; 07:43 UTC is 02:43 US Eastern, after nightly price
# updates). No extra runs around Black Friday (owner rule).
CRONS: tuple[str, ...] = ("43 7 * * *",)


def active_crons() -> tuple[str, ...]:
    """The cron slots that are meant to run."""
    return CRONS


# Same-day guard (F1 INC-007): it starts the run when the slot has not been run.
WATCHDOG_CRONS: tuple[str, ...] = ("19 10 * * *", "19 15 * * *")

GRACE = timedelta(hours=3)

# A slot counts as run once a run record with one of these statuses started at or
# after it. "held" counts: the pipeline ran, and running it again sooner would
# accept the hold before the owner looked at it. "crashed" does not count.
COVERING_STATUSES = frozenset({"ok", "partial", "held"})


def _field(spec: str, lo: int, hi: int) -> set[int]:
    if spec == "*":
        return set(range(lo, hi + 1))
    out: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def slots(start: datetime, end: datetime, crons: tuple[str, ...] = CRONS) -> Iterator[datetime]:
    """Scheduled run times in ``[start, end)``, UTC, sorted, de-duplicated."""
    times: set[datetime] = set()
    for expr in crons:
        minute, hour, dom, month, dow = expr.split()
        if dow != "*":
            raise ValueError(f"day-of-week not supported: {expr}")
        minutes, hours = _field(minute, 0, 59), _field(hour, 0, 23)
        days, months = _field(dom, 1, 31), _field(month, 1, 12)
        day = start.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        while day < end:
            if day.day in days and day.month in months:
                for h in hours:
                    for m in minutes:
                        t = day.replace(hour=h, minute=m)
                        if start <= t < end:
                            times.add(t)
            day += timedelta(days=1)
    yield from sorted(times)


def missed_slots(
    run_starts: list[datetime], first: datetime, now: datetime, crons: tuple[str, ...] = CRONS
) -> list[datetime]:
    """Slots since ``first`` (exclusive of the last ``GRACE``) with no good run within GRACE."""
    starts = sorted(run_starts)
    missed: list[datetime] = []
    for slot in slots(first, now - GRACE, crons):
        if not any(slot <= s <= slot + GRACE for s in starts):
            missed.append(slot)
    return missed


def latest_slot(now: datetime, crons: tuple[str, ...] | None = None) -> datetime | None:
    """The most recent active slot at or before ``now`` (looking back two days)."""
    found = list(
        slots(now - timedelta(days=2), now + timedelta(seconds=1), crons or active_crons())
    )
    return found[-1] if found else None


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def check_slot(
    runs: list[dict[str, object]],
    now: datetime,
    crons: tuple[str, ...] | None = None,
    slot: datetime | None = None,
) -> dict[str, str]:
    """Has the latest slot (or ``slot``) been run? The gate and the watchdog both ask."""
    slot = slot or latest_slot(now, crons)
    covering = [
        r
        for r in runs
        if slot is not None
        and r.get("status") in COVERING_STATUSES
        and _parse(str(r["started_at"])) >= slot
    ]
    return {
        "slot": slot.strftime("%Y-%m-%dT%H:%M:%SZ") if slot else "",
        "covered": "true" if covering or slot is None else "false",
        "run_id": str(covering[-1]["run_id"]) if covering else "",
    }


def _read_runs(path: str) -> list[dict[str, object]]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    # Standard library only, so the workflows run it with the runner's python3
    # without installing the project.
    p = argparse.ArgumentParser(description="Was the latest scheduled slot run?")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--runs", default="data/runs.jsonl")
    c.add_argument("--slot", help="ISO time of the slot a dispatched run fills (default: latest)")
    c.add_argument("--now", help="ISO time, default now (UTC)")
    a = p.parse_args(argv)
    now = _parse(a.now) if a.now else datetime.now(UTC).replace(microsecond=0)
    slot = _parse(a.slot) if a.slot else None
    result = check_slot(_read_runs(a.runs), now, active_crons(), slot=slot)
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
