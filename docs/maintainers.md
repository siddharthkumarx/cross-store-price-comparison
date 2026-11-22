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
in under 45 minutes on one runner.

GitHub starts `schedule` events for this account hours late or not at all (F1
INC-009, INC-003 here), so the slot is filled by the on-time trigger below.

The `slot` gate (`python -m crossprice.schedule gate`) runs a dispatch only for
the current slot and only if no run filled it; one up to 10 minutes early waits
for the slot. GitHub's late `schedule` event then skips. Without the trigger the
schedule and the watchdog still fill each day, late. `status.json` counts every
slot as on time (a good run within 2 hours), late (later the same UTC day), held
or missed; the on-time count starts with the first slot the trigger dispatched.

### On-time trigger

cron-job.org (no VPS, no other server, D-019) calls the `workflow_dispatch` API
with a **fixed** body; `slot: auto` makes the gate pick the active slot (07:43
UTC) within 10 minutes of now, before or after. With no such slot the run skips
with a one-line reason. Otherwise it is an explicit slot: a dispatch up to 10
minutes early waits for the slot, at most one pipeline run per slot, and the run
records `dispatch.by` "trigger" (on-time accounting).

- URL: `https://api.github.com/repos/siddharthkumarx/cross-store-price-comparison/actions/workflows/daily.yml/dispatches`
- Method: `POST`
- Headers: `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`.
  The token is fine-grained, this repository only, **Actions: read and write**
  and nothing else, 90-day expiry; it lives only in cron-job.org, never in the
  repository. Renew it before it expires.
- Body: `{"ref":"main","inputs":{"slot":"auto"}}`
- Schedule, time zone UTC: `43 7 * * *` (every day; no extra runs around Black
  Friday).
- Success is HTTP 204. Test the token with the body
  `{"ref":"main","inputs":{"slot":"check"}}` (runs nothing). A call at any other
  time skips, so an extra or mistimed call is harmless.

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

## History rewrite of 2026-11-20

Early commits were signed with a key that the owner's GitHub account does not have,
so GitHub showed them as "Unverified". The history was rewritten once with
`git filter-repo` to drop every signature, keeping authors, committers, dates and
messages; commits are unsigned from then on (`commit.gpgsign false`). The two recon
results recorded the SHA of the commit they ran on: `git_sha` now names the
rewritten commit and `git_sha_before_rewrite` the original one, which is also the
`head_sha` of the Actions run linked in `run_url`.
