"""Structural checks on the GitHub Actions workflows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"
WORKFLOWS = sorted(WF.glob("*.yml"))


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data


def _on(path: Path) -> dict[str, Any]:
    wf: dict[Any, Any] = _load(path)
    on: dict[str, Any] = wf["on" if "on" in wf else True]  # PyYAML reads `on` as True
    return on


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_actions_are_pinned_to_commit_shas(path: Path) -> None:
    for job in _load(path)["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_jobs_have_timeouts_and_step_refs_exist(path: Path) -> None:
    text = path.read_text()
    jobs = _load(path)["jobs"]
    ids = {s["id"] for job in jobs.values() for s in job["steps"] if "id" in s}
    for name, job in jobs.items():
        assert "timeout-minutes" in job, f"{path.name}:{name} has no timeout"
    for ref in re.findall(r"steps\.([\w-]+)\.", text):
        assert ref in ids, f"{path.name}: steps.{ref} is not a step id"


def test_live_checks_run_only_when_started_by_hand() -> None:
    assert set(_on(WF / "checks.yml")) == {"workflow_dispatch"}  # never on a push or tag


@pytest.mark.skipif(not (WF / "daily.yml").exists(), reason="daily workflow not added yet")
def test_daily_is_one_job_under_45_minutes_and_commits_after_upload() -> None:
    daily = _load(WF / "daily.yml")
    run = daily["jobs"]["run"]
    assert run["timeout-minutes"] <= 45  # owner limit, one runner
    assert "strategy" not in run  # never split across runners
    steps = {s.get("id"): s for s in run["steps"] if s.get("id")}
    assert "steps.upload.outcome" in steps["commit"]["if"]
    names = [s.get("name") for s in run["steps"]]
    assert names.index("Upload history to release") < names.index("Commit data")
    assert daily["concurrency"] == {"group": "daily", "cancel-in-progress": False}


@pytest.mark.skipif(not (WF / "daily.yml").exists(), reason="daily workflow not added yet")
def test_pages_deploy_is_gated_and_least_privilege() -> None:
    daily = _load(WF / "daily.yml")
    pages = daily["jobs"]["pages"]
    assert "vars.PAGES_ENABLED == 'true'" in pages["if"]
    assert pages["permissions"] == {"pages": "write", "id-token": "write"}
    assert pages["environment"]["name"] == "github-pages"
