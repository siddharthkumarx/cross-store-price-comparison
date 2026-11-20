# Maintainers' guide

Working notes for anyone continuing this build. Read this file, then
`docs/plan.md` (the first item that is not `done`), `docs/architecture.md` and
`docs/decisions.md`.

## Goal

A daily cross-store price comparison: the same products sold by several US online
retailers, matched across stores, compared every day, with the matching precision
measured in public. Public portfolio repository of Siddharth Kumar, founder of
SteadyData (steadydata.co). Readers: clients first, engineers second. **Every
number shown anywhere comes from a committed run** (recon results,
`data/runs.jsonl`, `data/precision/`, the Parquet history); none is typed by hand.

## Hard rules

### Git

- Author: `Siddharth Kumar <273157498+siddharthkumarx@users.noreply.github.com>`.
- `git config core.hooksPath .githooks`. Commit messages: no trailers except
  `Signed-off-by`, no "Generated with" footer, no session links, tool-neutral
  wording. The hook strips them; the CI job `commit-messages` fails on them.
- Work on `main`, small commits (`area: what and why`). Workflows commit `data/`
  and `checks/results/` to `main` too: always `git pull --rebase` before pushing.
- No secrets in the repository. No notes, placeholders or HTML comments in
  published files. Maintainer notes live here, not in a tool-specific file.

### Live checks

The development sandbox cannot reach retailers: never request a retailer from it.

1. Edit `checks/request.yml` (new `id`, `check: recon` or `check: catalog`, options).
2. Commit and push to `main`.
3. Start Actions, `checks`, Run workflow (`workflow_dispatch`).
4. `git pull` and read `checks/results/<id>/recon.md` and `recon.json`. Results are
   evidence: keep them.

### Scraping

- Public data only: no logins, no personal data; robots.txt respected (Protego,
  RFC 9309). No images or descriptions stored or republished.
- Never bypass CAPTCHAs or anti-bot systems: a retailer that challenges is dropped.
- No marketplaces (Amazon, Walmart, eBay, Etsy, Target), no Google.
- Excluded: alcohol, tobacco/vape, weapons, adult, CBD, medicines (D-007).
- One runner per run; at least 3 s between requests per host; one run-wide pace;
  a small fixed request budget per retailer per run; F1's back-off (D-004, D-005).
- Facts only: price differences as numbers, never judgments (D-012).

### Schedule

One daily run at a quiet minute, no extra runs around Black Friday. It must finish
in under 45 minutes on one runner. The `slot` input of `daily.yml` exists so an
on-time external trigger can start runs later; the watchdog covers missed slots.

## Commands

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run python -m crossprice.checks checks/request.yml   # what the checks workflow runs (runner only)
```

`UV_SYSTEM_CERTS=1` may be needed in the sandbox for uv to trust the proxy CA.

## Layout

```
src/crossprice/  polite.py, witness.py, gtin.py, screen.py, recon.py, checks.py and the
                 pipeline modules listed in docs/architecture.md
checks/          candidates.yml, request.yml, results/<id>/ (committed evidence)
config/          retailers.yml (generated from recon evidence), screen-review.yml
data/            pipeline outputs committed by the daily workflow
docs/            maintainers (this guide), architecture, decisions, plan, sources,
                 incidents, precision, repo-settings
tests/           pytest
```
