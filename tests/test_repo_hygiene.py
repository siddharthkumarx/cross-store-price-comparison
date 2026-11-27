"""Repository rules that CI enforces through pytest."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 50 * 1024 * 1024
JUDGMENT_WORDS = ("map violation", "overpriced", "too expensive", "rip-off", "price gouging")
# The terms before 27 Nov 2026 (LICENSE-HISTORY.md, decisions D-020): the code license
# named by its three-letter id, and the data license without "-NC", in any spelling
# (spaces, dashes, lower case, the legal-code URL or the full name). Written so that
# this file does not match itself.
OLD_LICENSES = (
    re.compile(r"\bMI[T]\b"),
    re.compile(r"licen[cs]e\s*[:=]\s*[\"']?mi[t]\b|\bmi[t] licen[cs]e\b", re.IGNORECASE),
    re.compile(r"\bCC[ _-]BY[ _-]4\.0\b", re.IGNORECASE),
    re.compile(r"creativecommons\.org/licenses/by/4\.0", re.IGNORECASE),
    re.compile(r"Attribution 4\.0 International", re.IGNORECASE),
)
LICENSE_HISTORY = "LICENSE-HISTORY.md"


def _tracked() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode()
    return [ROOT / p for p in out.split("\0") if p]


def _rel(path: Path) -> str:
    """Repository-relative path with forward slashes, on every platform."""
    return path.relative_to(ROOT).as_posix()


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
        if path.suffix != ".md" or not path.exists() or _rel(path).startswith("checks/results/"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "<!--" not in text, path
        assert not re.search(r"\b(TODO|TBD|FIXME|lorem ipsum)\b", text, re.IGNORECASE), path


def test_no_judgment_words_in_published_text() -> None:
    for path in _tracked():
        if not path.exists() or path.suffix not in (".md", ".html", ".j2", ".svg"):
            continue
        if path.name == "test_repo_hygiene.py" or _rel(path) == "docs/decisions.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        assert not [w for w in JUDGMENT_WORDS if w in text], path


def test_old_license_terms_appear_only_in_the_license_history() -> None:
    found = []
    for path in _tracked():
        if not path.is_file() or _rel(path) == LICENSE_HISTORY:
            continue
        raw = path.read_bytes()
        if b"\0" in raw[:8192]:  # binary: images, fonts, video, gzip
            continue
        for n, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
            if any(p.search(line) for p in OLD_LICENSES):
                found.append(f"{_rel(path)}:{n}: {line.strip()[:120]}")
    assert found == [], "old license terms outside LICENSE-HISTORY.md:\n" + "\n".join(found)


def test_old_license_pattern_catches_the_old_wording() -> None:
    old = (
        "Code: [" + "MI" + "T](LICENSE)",
        "shared under CC BY " + "4.0 with attribution",
        "license: cc-by-" + "4.0",
        "license: m" + "it",
        'license = "M' + 'IT"',
        "https://creativecommons.org/licenses/by/" + "4.0/legalcode",
    )
    new = (
        "Code: [PolyForm Noncommercial 1.0.0](LICENSE)",
        "shared under [CC BY-NC 4.0](LICENSE-DATA.md)",
        "license: cc-by-nc-4.0",
        "https://creativecommons.org/licenses/by-nc/4.0/legalcode",
        "No new request after the time LIMIT; SUBMIT; Mitigation; license: permitted",
        "Attribution-NonCommercial 4.0 International",
    )
    assert all(any(p.search(s) for p in OLD_LICENSES) for s in old)
    assert not any(p.search(s) for p in OLD_LICENSES for s in new)


def test_no_tool_specific_maintainer_file() -> None:
    names = {p.name.lower() for p in _tracked()}
    assert "claude.md" not in names
    assert "agents.md" not in names


def test_commit_hook_is_executable() -> None:
    hook = ROOT / ".githooks" / "commit-msg"
    assert hook.exists()
    # The mode git records, which every clone gets; Windows file systems have no exec bit,
    # so the checkout's own mode is checked only where it exists.
    staged = subprocess.run(
        ["git", "ls-files", "-s", ".githooks/commit-msg"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert staged, "commit-msg hook must be tracked"
    assert staged.startswith("100755 "), "commit-msg hook must be executable in git"
    if os.name != "nt":
        assert hook.stat().st_mode & 0o111, "commit-msg hook must be executable"
