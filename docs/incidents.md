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

## INC-003 - The first daily slot did not fire (2026-11-21)

- **Slot:** 07:43 UTC on 2026-11-21, the first scheduled slot of `daily.yml`.
- **What happened:** GitHub created no `schedule` run for `daily.yml` and none for
  `watchdog.yml` (10:19 UTC): no run, no queued run, read from the public Actions
  API at 10:51 UTC. Both workflows were `active`; manual runs and push-triggered CI
  ran normally all night.
- **Cause:** GitHub's scheduler delays or drops `schedule` events and gives no
  start-time guarantee. The store monitor F1 measured 7 to 10 hours of delay on
  every slot of the same account (F1 INC-009).
- **Fix:** the schedule rules of F1 INC-009 are ported. The daily gate
  (`python -m crossprice.schedule gate`) lets a dispatch that names its slot fill
  it, so an on-time external trigger can start each run at 07:43 UTC; GitHub's
  late event then skips. The watchdog's dispatch is marked `by=watchdog`. A slot
  now counts as late, not missed, when a good run starts later the same UTC day,
  and the on-time count starts with the first triggered slot. The 2026-11-21 slot
  was filled by hand at 10:54 UTC (dispatch with `slot` and `by=manual`).
- **Detection:** `status.json` `schedule` (on time, late, held, missed per slot)
  and the "on time" and "missed runs" badges.

## INC-004 - A product title with an inch mark crashed the history merge (2026-11-21)

- **Run:** `daily` for the 07:43 slot of 2026-11-21, dispatched by hand,
  [Actions run 44896513350](https://github.com/siddharthkumarx/cross-store-price-comparison/actions/runs/44896513350);
  alert issue #1.
- **What happened:** all 11 retailers were read, then the run stopped in the
  history step with `Value with unterminated quote found` on line 3,260 of the
  previous snapshot (`data/latest/offers.csv`): the Cos Bar title
  `T3 SINGLEPASS CURL 1.25" SATIN BLUSH`, written as valid CSV with the quote
  doubled. The run was recorded as `crashed`; the snapshot, the GTIN cache and the
  monthly Parquet file were left unchanged, so no data was lost or half-written.
- **Cause:** DuckDB's `read_csv` sniffs the CSV dialect even when the column
  types are given. The first 3,259 rows hold no quote at all, and the sniffer
  settled on a dialect that does not read `""` as an escaped quote. The first run
  had no previous snapshot to read, so it did not meet the problem.
- **Fix:** the snapshot is read with the dialect stated (`delim ','`, `quote '"'`,
  `escape '"'`, no auto-detection). A regression test writes 3,999 plain rows and
  one title with an inch mark and a comma, and reads them back unchanged; it fails
  on the old query.
- **Detection:** a crash is a run record with `status: crashed` and its error, the
  "last run" badge, and the `run-alert` issue.

## INC-005 - CI failed on a type error, then on a product id read as a secret (2026-11-21)

- **Runs:** `ci` from [run 26](https://github.com/siddharthkumarx/cross-store-price-comparison/actions/runs/44896509377)
  to [run 33](https://github.com/siddharthkumarx/cross-store-price-comparison/actions/runs/44907516879);
  the README's CI badge showed "failing" for about two hours. The daily runs were
  not affected: they do not depend on CI.
- **What happened:** first, `mypy` rejected a test that called `.startswith` on a
  value typed `object`; the tests had been run locally, the type check had not.
  Once that was fixed, the secret scan reported 6 findings in
  `data/latest/price-index.json` as committed by the run of 12:41 UTC.
- **Cause:** gitleaks' `generic-api-key` rule looks for a name containing `key`
  or `token` followed by a random-looking value. A product compared without a
  barcode has the id `M` + 13 hex digits of a SHA-256, stored as
  `"product_key": "M…"`; its entropy is just over the rule's limit. The first run
  compared barcode products only, so the scan met the first such id on this run.
  A first guess (a shade name next to a store SKU) was wrong; the scan's output
  did not show the findings, so `--verbose` (still redacted) was added to the CI
  step and the findings were read from it.
- **Fix:** the type is narrowed in the test. `.gitleaks.toml` keeps the default
  rules and exempts from that one rule only values that are exactly this id
  format (`^M[0-9a-f]{13}$`); everything else in every file is still scanned.
- **Detection:** the `ci` workflow on every push, its findings in the log, and its
  badge in the README.
