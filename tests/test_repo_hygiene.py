"""Repository rules that CI enforces through pytest."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 50 * 1024 * 1024
JUDGMENT_WORDS = ("map violation", "overpriced", "too expensive", "rip-off", "price gouging")


def _tracked() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode()
    return [ROOT / p for p in out.split("\0") if p]


def test_every_tracked_file_is_under_50_mb() -> None:
    big = [p for p in _tracked() if p.exists() and p.stat().st_size >= MAX_BYTES]
    assert big == [], f"files at or over 50 MB: {big}"


def test_committed_data_holds_no_descriptions_or_images() -> None:
    for base in (ROOT / "data", ROOT / "checks" / "results"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in (".csv", ".json", ".jsonl", ".md"):
                text = path.read_text(encoding="utf-8", errors="replace")
                assert "body_html" not in text, path
                assert "cdn.shopify.com" not in text, path


def test_published_markdown_has_no_html_comments_or_placeholders() -> None:
    for path in _tracked():
        if path.suffix != ".md" or not path.exists() or "checks/results" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        assert "<!--" not in text, path
        assert not re.search(r"\b(TODO|TBD|FIXME|lorem ipsum)\b", text, re.IGNORECASE), path


def test_no_judgment_words_in_published_text() -> None:
    for path in _tracked():
        if not path.exists() or path.suffix not in (".md", ".html", ".j2", ".svg"):
            continue
        if path.name == "test_repo_hygiene.py" or "docs/decisions.md" in str(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        assert not [w for w in JUDGMENT_WORDS if w in text], path


def test_no_tool_specific_maintainer_file() -> None:
    names = {p.name.lower() for p in _tracked()}
    assert "claude.md" not in names
    assert "agents.md" not in names


def test_commit_hook_is_executable() -> None:
    hook = ROOT / ".githooks" / "commit-msg"
    assert hook.exists()
    assert hook.stat().st_mode & 0o111, "commit-msg hook must be executable"
