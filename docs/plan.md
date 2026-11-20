# Plan

Numbered build items. Status: `done`, `in progress`, `next`, `later`.

## Phase A - architecture and recon

1. `done` Architecture, decisions and this plan (`docs/architecture.md`,
   `docs/decisions.md`).
2. `done` Reuse F1's polite client, witness parsers and content screen; add the
   GTIN rules, a 3 s per-host floor and a medicines category (with tests).
3. `done` Two-stage recon and the `checks` workflow (`workflow_dispatch`, one
   runner, results committed to `checks/results/<id>/`).
4. `in progress` Stage 1 recon over 103 candidates in 8 verticals (`recon-001`).
5. `next` Stage 2 catalogs for the verticals that still have at least 8 passing
   retailers; overlap and GTIN coverage computed offline from the committed
   catalogs; GTIN probes on overlap candidates.
6. `next` Choose the vertical by D-002; `docs/sources.md` with the evidence for
   every retailer kept or dropped; `config/retailers.yml` generated from it.

## Phase B - build

7. `later` Collect: catalog pages, GTIN probes within the budget, currency proof,
   content screen; request budget fixed in D-005 from the stage-2 numbers.
8. `later` Validate: `OfferRow`, normalisation, batch guard (from F1).
9. `later` GTIN cache with weekly refresh.
10. `later` Matching: GTIN, brand-scoped MPN/SKU, fuzzy with scores; product groups;
    `possible_matches.csv`.
11. `later` Precision: blind evaluation, thresholds, `data/precision/`; the
    100-pair manual check in `docs/precision.md`.
12. `later` Compare: `comparison.csv` (lowest price, spread), changes (price moves,
    new lowest retailer, stock-outs).
13. `later` Store: DuckDB SCD2 offer history, snapshot, monthly Parquet release.
14. `later` Outputs: `status.json`, badges, `runs.jsonl`, `data/public/feed.json`.
15. `later` Workflows: `daily.yml` (quiet minute, `slot` input, gate, 45-minute
    job, alert issue), `watchdog.yml`, CI.
16. `later` "Your price vs competitors" demo.
17. `later` Dashboard on GitHub Pages in the SteadyData light system (self-hosted
    font subsets, WCAG AA, 390 px, reduced motion).
18. `later` `docs/incidents.md` kept from the first live run on.

## Phase C - README and polish (after 2-3 real runs)

19. `later` README template rendered every run; hero and pipeline SVGs (still and
    animated, Playwright test); social preview 1280 x 640; LinkedIn video
    1080 x 1080.
20. `later` SEO/GEO: quotable first sentence, H2s as real searches, comparison
    table (Prisync, Price2Spy, checking by hand), dated numbers linked to runs,
    `docs/repo-settings.md`, `CITATION.cff`, dataset card.
