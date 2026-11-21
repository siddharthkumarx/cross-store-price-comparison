# Incidents

What broke, the evidence, the cause, the fix, and how a repeat is detected.
Newest last. Incidents of the store monitor F1, whose fixes this project reuses,
are in [its incident log](https://github.com/siddharthkumarx/ecommerce-price-monitor/blob/main/docs/incidents.md).

## INC-001 - Commits showed as "Unverified" on GitHub (2026-11-20)

- **What happened:** the first commits were signed with an SSH key from the
  development environment that the owner's GitHub account does not hold. GitHub
  showed them as "Unverified" (API verification reason `unknown_key`), unlike the
  owner's other public repositories, whose commits are unsigned and carry no badge.
- **Fix:** signing switched off for this repository (`commit.gpgsign false`,
  `tag.gpgsign false`). The history was rewritten once with `git filter-repo`, which
  drops signatures and keeps authors, committers, dates and messages, and `main` was
  force-pushed while no live check was running. The two recon results that record
  the commit they ran on keep both SHAs (`git_sha`, `git_sha_before_rewrite`).
- **Verified:** the GitHub API reported verification reason `unsigned` for all 16
  commits on `main` after the push.
- **Detection:** the reason is visible per commit in the API
  (`commit.verification.reason`); a signed commit would show again as `unknown_key`.

## INC-002 - Five retailers throttled a second catalog read (2026-11-20)

- **What happened:** in `recon-004` Cos Bar, Credo Beauty, Integrity Botanicals,
  Safe & Chic and The Detox Market answered HTTP 429 on `/products.json` page 3 or 4
  until the retries ran out. It was the second full read of each catalog within
  30 minutes; `recon-002` had read the same catalogs without a 429.
- **Cause:** these stores limit deep catalog pages per client over a window of
  roughly half an hour. Pacing (3 s or more per host) was kept throughout; the limit
  is on repeated reads, not on speed.
- **Fix:** owner decision D-016: a 429 alone is rate limiting, not a challenge. Each
  of the five was re-tested with one catalog read after a cool-down of at least
  90 minutes (`recon-005`): three passed and are kept, two throttled again and are
  dropped (D-018). The daily run reads each catalog once per day, and the first
  daily run started more than 90 minutes after the re-test.
- **Detection:** retries and their causes are counted per retailer in
  `data/runs.jsonl`; eight 429s in a row stop the run, and a retailer that cannot
  be read is listed under `retailers_not_updated` and lowers `retailers_ok` in
  `status.json`.
