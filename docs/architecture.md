# Architecture

One scheduled GitHub Actions job, on one runner, reads the public catalogs of a
fixed list of US online retailers, finds the products that several of them sell,
and compares their prices and stock every day. Everything it publishes is a small
file in git, a monthly Parquet release asset or a static dashboard.

```
config/retailers.yml
        │
        ▼
 collect ──► validate ──► match ──────────► compare ──► store (SCD2) ──► outputs
 robots       Pydantic     1 GTIN-14          lowest      DuckDB           comparison.csv
 catalog      batch guard  2 brand + MPN/SKU  spread %    snapshot CSV     changes/, status.json
 GTIN probes               3 fuzzy (scored)   stock       monthly Parquet  badges, feed.json
 currency proof            │                                               possible_matches.csv
                           └─► low confidence: possible_matches.csv, never compared
```

This repository is F3 of a public series. F1, the store monitor
([ecommerce-price-monitor](https://github.com/siddharthkumarx/ecommerce-price-monitor)),
proved the polite Shopify readers, pacing, validation, SCD2 history, status badges
and watchdog on live daily runs; F3 reuses them and adds what a comparison needs:
GTINs, matching across retailers, and a measured matching precision.

## Modules (`src/crossprice/`)

| module | role | origin |
|---|---|---|
| `polite.py` | `StoreSession` (robots, per-host pacing at least 3 s, retries, block detection) and `EdgeGuard` (run-wide pace, 429 cool-down, circuit breaker, time budget). Every request to a retailer goes through it. | F1, user agent and 3 s floor changed |
| `witness.py` | Parsers for `/products.json`, product `.js` and JSON-LD (currency, offers, GTIN fields). | F1 + `jsonld_gtins` |
| `gtin.py` | Barcode to GTIN-14, check digit, restricted prefixes. | new |
| `screen.py` | Excluded-category screen (adult, tobacco/vape, alcohol, cannabis/CBD, weapons, medicines). | F1 + medicines |
| `recon.py`, `checks.py` | Two-stage retailer recon and the live-checks runner. | F1 pattern, new measures |
| `retailers.py` | Loads `config/retailers.yml`. | new |
| `collect.py` | Per retailer: robots, catalog pages, GTIN probes within the budget, currency proof. | F1 `fetch.py` pattern |
| `models.py` | Pydantic `OfferRow` and `MatchRow` (the validation rules). | F1 pattern |
| `normalize.py` | Raw Shopify JSON to `OfferRow` (integer cents, UTC, fixed availability). | F1 |
| `guard.py` | Batch guard: holds a run that looks broken. | F1 |
| `gtincache.py` | The GTIN cache: one `.js` read per product, refreshed weekly. | new |
| `match.py` | The three matchers, confidence scores, product groups. | new |
| `precision.py` | Blind evaluation of the matchers against GTIN-verified pairs; manual-check sample. | new |
| `compare.py` | Lowest price, spread, per-retailer columns; the "your price vs competitors" index. | new |
| `history.py` | DuckDB SCD2 merge of offers, snapshot CSV, monthly Parquet. | F1 |
| `changes.py` | Price moves, new lowest retailer, stock-outs, between two runs. | F1 pattern, new events |
| `outputs.py` | `comparison.csv`, change files, `runs.jsonl`, `status.json`, badges, `feed.json`. | F1 + new files |
| `schedule.py` | Cron slots as data, slot check for the gate and the watchdog. | F1 |
| `site.py` | Static dashboard in `site/`. | F1 pattern, new design |
| `readme.py`, `visuals.py` | README and SVGs rendered from the latest run. | F1 pattern |
| `run.py` | The daily entry point and exit codes. | F1 pattern |

## Retailers and request budget

`config/retailers.yml` is generated from recon evidence (`docs/sources.md`). Each
retailer has the same fixed budget per run (D-005):

| request | count per retailer per run |
|---|---|
| `robots.txt` | 1 |
| `/products.json?limit=250&page=N&country=US` | up to `MAX_PAGES` (the whole catalog; a retailer whose catalog does not fit is not selected) |
| `/products/<handle>.js?country=US` (GTIN probes) | up to `GTIN_BUDGET` |
| one product page (currency proof, JSON-LD witness) | 1 |

Requests within a retailer are sequential and at least 3 s apart (plus jitter, or
the robots.txt `Crawl-delay` when larger). All retailers share one run-wide pacer,
because Shopify throttles per client IP across all shops (F1 INC-001, INC-005). The
whole run is one job on one runner: never split across runners, which would spread
the load over more IP addresses.

## Collect

1. `robots.txt` (RFC 9309 via Protego). Paths used: `/products.json`,
   `/products/<handle>.js`, `/products/<handle>`. A disallowed path stops that
   retailer for the run.
2. Every `/products.json` page. This gives every product and variant with price,
   compare-at price, availability, vendor (brand), product type, SKU and options.
   No barcode: Shopify does not publish it in this feed.
3. GTIN probes, `GTIN_BUDGET` per retailer, chosen in this order: products that a
   cheaper matcher (brand + MPN/SKU, or fuzzy) pairs with a product at another
   retailer and that have no cached GTIN; then cached entries older than 7 days,
   oldest first. Each probe reads the product `.js` (variant `barcode` and integer
   cent prices, which also cross-check `/products.json`).
4. One product page: the currency proof (JSON-LD `priceCurrency` or the theme's
   `Shopify.currency`) and the JSON-LD witness. A non-USD currency holds the run.
5. Content screen: products in an excluded category are dropped before anything is
   stored (D-007).

Only parsed fields are kept in memory; raw bodies are never written anywhere.

## Validate

`OfferRow` (Pydantic, strict): positive integer ids; `price_cents > 0`;
`compare_at_cents` is `None` or at least the price (a lower one is a stale merchant
value, set to `None` and counted); availability `in_stock` / `out_of_stock`;
`gtin14` is `None` or 14 digits with a valid check digit; `observed_at` is UTC.
Rejected rows are counted per retailer. The batch guard (F1's rules) holds the
run when a retailer's rows fall by more than half, when many prices move by a
factor that points at a parsing error, or when rejects pass 2 %. A held run keeps
the last good outputs live.

## Match

Offers are variants (one retailer, one Shopify variant). A **product** in the
comparison is a set of offers, at most one per retailer, that are the same item.

| tier | rule | confidence |
|---|---|---|
| 1 GTIN | equal GTIN-14 (D-008) | exact: 1.00 |
| 2 MPN/SKU | same normalised brand and same normalised SKU, where the SKU looks like a manufacturer part number (D-009) | scored |
| 3 fuzzy | same normalised brand; model tokens and variant options compared; score from token overlap, number tokens, option agreement and price ratio | scored |

A tier-2 or tier-3 pair is **high confidence** only when its score is at or above
the threshold that reached the precision target in the latest blind evaluation
(D-011), it is the best candidate in both directions, and the two GTINs (where
known) do not disagree. High-confidence pairs and GTIN pairs are joined into
products (one offer per retailer; a conflict keeps the higher-confidence link).
Every other candidate pair goes to `data/latest/possible_matches.csv` with its
score and reason and is never compared.

## Compare

For every product with offers at two or more retailers:

- each retailer's price, compare-at price, stock and product link;
- `lowest_price`: the lowest in-stock price (all offers when none is in stock),
  and the retailer(s) at that price;
- `spread_pct`: (highest − lowest) / lowest × 100 over in-stock offers, when at
  least two are in stock;
- no judgments: differences are numbers only (D-012).

"Your price vs competitors" (demo, D-013): for a chosen retailer, per brand, the
median of (its price / median price of the other retailers) × 100 over shared
products, and the list of products where it is more than 5 % above or below.

## Store (SCD2)

DuckDB is the in-run engine. Table `offer_history`, one row per version of an
offer's observable state:

| column | type | note |
|---|---|---|
| `retailer_id` | VARCHAR | from `config/retailers.yml` |
| `product_id`, `variant_id` | BIGINT | Shopify ids |
| `handle`, `brand`, `product_title`, `variant_title`, `sku` | VARCHAR | identifiers for display and matching |
| `gtin14` | VARCHAR | from the GTIN cache, may be empty |
| `price_cents`, `compare_at_cents` | BIGINT | integer cents, USD |
| `available` | BOOLEAN | |
| `valid_from`, `valid_to` | TIMESTAMPTZ | `valid_to` NULL = current |

Tracked attributes: price, compare-at price, availability, GTIN. State between
runs is the open versions in `data/latest/offers.csv` (sorted, no per-run
timestamps). Each month's versions go to the release asset
`offer_history_YYYY-MM.parquet` (release `data-YYYY-MM`), as in F1.

## Outputs

| file | content |
|---|---|
| `data/latest/comparison.csv` | one row per matched product: product, brand, GTIN, per retailer price / stock / link, lowest price, lowest retailer(s), spread % |
| `data/latest/possible_matches.csv` | candidate pairs below the confidence bar (never compared) |
| `data/latest/offers.csv` | the open SCD2 versions (state) |
| `data/changes/YYYY/YYYY-MM-DD.csv` | price moves on matched offers, new lowest retailer, stock-outs and returns |
| `data/precision/latest.json` + dated copies | blind-evaluation precision and recall with counts and date |
| `data/runs.jsonl` | one line per run |
| `data/status.json`, `data/badges/*.json` | status and shields.io endpoint badges |
| `data/public/feed.json` | the `steadydata.feed/v1` envelope (below) |
| `data/gtin/cache.csv` | the GTIN cache |
| release `data-YYYY-MM` | `offer_history_YYYY-MM.parquet`, `comparison.csv` |
| `site/` | the dashboard, deployed to GitHub Pages |

### `data/public/feed.json`

Same envelope as the other SteadyData monitors, plus a `comparison` block:

| field | type | meaning |
|---|---|---|
| `schema` | string | always `steadydata.feed/v1` |
| `monitor` | object | `id`, `name`, `repo`, `dashboard`, `generated_at` |
| `last_run` | object | `run_id`, `started_at`, `finished_at`, `status`, `duration_s`, `run_url` |
| `checks` | array | each data check of the last run: `id`, `label`, `value`, `ok` |
| `totals` | object | `runs`, `runs_good`, `days_running`, `missed_runs`, `retailers`, `offers` |
| `daily` | array | the last 30 runs: `date`, `status`, `offers`, `products_matched`, `changes` |
| `comparison` | object | `products_matched`, `retailers`, `matching_precision` (`value`, `recall`, `pairs`, `measured_at`, `manual_check`), `avg_spread_pct` |

## Workflows

| workflow | trigger | notes |
|---|---|---|
| `ci.yml` | every push | commit-message policy, ruff, mypy, pytest, gitleaks, pip-audit |
| `checks.yml` | `workflow_dispatch` only | live recon on one runner; commits `checks/results/<id>/` |
| `daily.yml` | one cron slot a day at a quiet minute; `workflow_dispatch` with a `slot` input | gate job (skips a slot already filled), the pipeline (job `timeout-minutes: 45`, no new request after the budget), Parquet upload, data commit, alert issue, Pages deploy |
| `watchdog.yml` | its own cron, after the slot | starts a missed run, opens a `run-alert` issue |

The `slot` input lets an external scheduler start the run on time later (GitHub
starts scheduled runs late on busy days, F1 INC-007); the gate treats a dispatched
run with a `slot` value as that slot's run.

## Exit codes of `python -m crossprice.run`

`0` ok, `2` partial (some retailers failed, the rest updated), `3` held, `1` crashed.
