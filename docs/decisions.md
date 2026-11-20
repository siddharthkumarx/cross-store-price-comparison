# Decisions

Numbered, newest last. Each: the decision, why, and what follows from it. A
decision is changed by a new entry that supersedes it, not by editing history.
"F1" is the store monitor
[ecommerce-price-monitor](https://github.com/siddharthkumarx/ecommerce-price-monitor),
whose decisions and incidents are referenced as F1 D-nnn and F1 INC-nnn.

## D-001 - Stack: F1's, reused where it is proven (2026-11-20)

Python 3.12 with uv (`uv.lock` committed, CI uses `uv sync --locked`); httpx,
Protego (robots.txt with wildcards), Pydantic, DuckDB, PyArrow, PyYAML, Jinja2;
ruff, mypy (strict), pytest, pip-audit, gitleaks; Actions pinned by commit SHA.
Same versions as F1 on 2026-11-20. Code taken from F1 keeps its behaviour and its
tests: the polite client (`polite.py`), the witness parsers, the content screen,
validation, SCD2 history, status and badges, the schedule gate and the watchdog.
What is new is written and tested here: GTINs, matching, precision, comparison.

## D-002 - The vertical is chosen by recon numbers (2026-11-20, owner rule)

One vertical is compared. It is the one whose recon evidence meets all of:

1. **At least 8 retailers pass recon**: US shop (`/meta.json` country `US`), USD
   proven on a product page, Shopify catalog readable, robots.txt allows the paths
   used, no challenge or block and no 429 retry in any recon run, multi-brand (at
   least 5 vendors and no vendor above 50 % of products), no more than 5 % excluded
   products.
2. **Overlap of at least 30 % across at least 3 of them.** Measured per retailer
   as the share of its products that at least one other passing retailer also
   sells (GTIN match where known, otherwise brand + MPN/SKU or a high-scoring
   brand-scoped title match, confirmed by GTIN probes on a sample). The rule holds
   when 3 or more retailers each have at least 30 %. The number of products sold
   by 3 or more retailers is reported next to it.
3. **GTINs for most variants**: more than 50 % of sampled variants across the
   passing retailers carry a valid, unrestricted GTIN (product `.js` barcode or
   JSON-LD `gtin*`).

Ties or several passing verticals: the one with more retailers at 30 % overlap,
then the higher GTIN share. Candidates tested: outdoor gear, cycling, coffee
equipment, kitchenware, audio/hi-fi, pet supplies, board games, skincare. Every
retailer kept or dropped is listed with its evidence in `docs/sources.md`.

## D-003 - Live checks only on GitHub Actions, started by hand (2026-11-20)

The development sandbox cannot reach retailers, and production runs on
GitHub-hosted runners, so recon runs there too: same network, same IP reputation.
`.github/workflows/checks.yml` runs on `workflow_dispatch` only (never on a push
or a tag: F1 INC-008 re-ran a check by moving a tag). It reads
`checks/request.yml` and commits `checks/results/<id>/`; an existing id is refused,
so evidence is never overwritten.

Recon has two stages so that most candidates cost at most 6 requests:

- **stage 1** (`check: recon`): robots.txt, `/products.json` page 1, `/meta.json`,
  2 product `.js`, 1 product page;
- **stage 2** (`check: catalog`), for the verticals still in the running: the whole
  catalog up to a page cap, a stable random sample of product `.js` for unbiased
  GTIN coverage, named handles for overlap confirmation, 1 product page. The
  catalog identifiers (no descriptions, no images) are committed gzip-compressed so
  overlap is computed offline and reproducibly.

## D-004 - Politeness (2026-11-20, owner rules)

- One run is one job on one runner, recon included. Never split across runners:
  that would spread requests over more IP addresses and work around per-IP limits.
- At least 3 s between two requests to the same host (`MIN_HOST_GAP_S`, enforced
  by `PoliteConfig`; defaults 4 s + 0-3 s jitter), longer when robots.txt sets a
  `Crawl-delay`.
- One run-wide pace across all retailers (3 s + 0-1.5 s, F1's proven daily
  setting): Shopify throttles per client IP across shops (F1 INC-001, INC-005).
- A fixed request budget per retailer per run (D-005).
- F1's back-off: retries only on 429, 5xx and network errors; a 429 pauses the
  whole run for its Retry-After and slows the pace (F1 INC-004); Retry-After over
  120 s stops the retailer; 8 consecutive 429s halt the run; a challenge or block
  page stops the retailer at once and is never retried; 4 blocked hosts within
  120 s halt the run (6 for recon, whose candidates include non-Shopify sites that
  refuse automated clients outright).
- Identification: `cross-store-price-comparison/0.1
  (+https://github.com/siddharthkumarx/cross-store-price-comparison)`; robots.txt
  group `cross-store-price-comparison`, falling back to `*`.
- No logins, no proxies, no browser automation, no CAPTCHA or anti-bot bypass. A
  retailer that challenges is dropped, not retried another way.
- `country=US` on every request except robots.txt.

## D-005 - Daily budget: 45 minutes, fixed requests per retailer (2026-11-20, owner rules)

The daily run must finish in under 45 minutes. At F1's measured pace (about 4.5 s
per request including latency, F1 D-005 and daily runs since 2026-11-07) that is
about 500 requests at most; the budget is set well below so a throttled day still
fits. Per retailer: 1 robots.txt + up to `MAX_PAGES` catalog pages + up to
`GTIN_BUDGET` product `.js` + 1 product page. The concrete numbers are set from
the stage-2 catalog sizes of the chosen retailers and recorded here when the
retailer list is final. No new request starts after 38 minutes; the job times out
at 45.

## D-006 - Retailer drop rules (2026-11-20, owner rules)

A candidate is dropped when, in any recon run, it showed a challenge or block,
needed a 429 retry, or its robots.txt disallows a path we use; and in its latest
recon when it is not a readable Shopify catalog, not a US shop, not proven USD,
single-brand, a marketplace, or above the excluded-products share (D-007).
Marketplaces (Amazon, Walmart, eBay, Etsy, Target) and Google are never
candidates (a test checks the candidate file).

## D-007 - Excluded categories: product-level screen, retailer-level drop (2026-11-20, owner rules)

Alcohol, tobacco/vape, weapons, adult, cannabis/CBD and medicines are excluded.
F1's whole-word screen over title, product type and tags (never descriptions),
plus a medicines list, runs on every catalog. A multi-brand retailer can carry a
stray matching item, so matching products are dropped before anything is stored,
and a retailer whose matching share is above 5 % (`STORE_DROP_SHARE`) is dropped
as a seller of excluded goods. Harmless phrases ("wine glass", "medicine ball")
are allow-listed; reviewed false positives are listed by exact title in
`config/screen-review.yml`, as in F1 D-016.

## D-008 - GTIN normalisation (2026-11-20)

Every barcode becomes a GTIN-14: digits only, 8, 12, 13 or 14 long, left-padded
with zeros, valid GS1 check digit. Rejected: restricted-circulation and
variable-measure numbers (GTIN-13 prefixes 020-029, 040-049, 200-299; indicator
9), coupon ranges (980-999) and all-zero bodies, because those numbers are
assigned by a store, not by the brand, and two retailers can use the same one for
different items. Sources: product `.js` variant `barcode` first, JSON-LD `gtin*`
second. A product whose two sources disagree keeps the `.js` value and the
disagreement is counted.

## D-009 - Matching tiers (2026-11-20, owner rules)

1. **GTIN exact** on GTIN-14.
2. **Brand-scoped MPN/SKU**: brands normalised (case, punctuation, legal suffixes,
   an alias table for known spellings); SKUs normalised (upper case, no spaces,
   dashes, dots or slashes). A SKU counts as a manufacturer part number only if
   it is at least 4 characters with at least one digit, is not the variant id or
   a GTIN, and is not shared by different products within one retailer. Equal brand
   and equal normalised SKU at two retailers is a candidate pair.
3. **Fuzzy**: equal brand; model tokens (title minus brand words, stop words and
   colour words) compared with a weighted overlap in which number-bearing tokens
   (model numbers, sizes) must agree; variant options compared; price ratio
   outside 0.5-2.0 lowers the score. Output: a score from 0 to 1.

Only high-confidence pairs are compared (thresholds from D-011); the rest are
written to `possible_matches.csv` and never compared. A product has at most one
offer per retailer.

## D-010 - GTIN cache and weekly refresh (2026-11-20, owner rule)

Barcodes are not in `/products.json`, so each costs one product `.js` request.
They are fetched once per product and cached in `data/gtin/cache.csv`
(retailer, product, variant, GTIN-14, source, fetched date). Each run spends at
most `GTIN_BUDGET` probes per retailer: first on products another matcher pairs
with a product elsewhere and that have no cache entry, then on entries older than
7 days. Daily prices always come from `/products.json`, never from the cache.

## D-011 - Matching precision is measured blind and in public (2026-11-20, owner rule)

- **Ground truth**: offer pairs at two retailers whose GTINs are equal (true
  match) or both known and different (true non-match).
- **Blind run**: tiers 2 and 3 run on the same offers with every GTIN hidden.
- **Precision** = predicted pairs that are true matches / predicted pairs where
  both GTINs are known. **Recall** = true matches the blind matchers found / all
  true matches. Both are published with their counts, the date and the run in
  `data/precision/`.
- **Thresholds**: the tier-2 and tier-3 thresholds are the lowest scores at which
  blind precision is at least 98 % on at least 100 evaluated pairs; until that is
  reached, only GTIN pairs are compared.
- **Manual check**: 100 compared pairs that are not GTIN-verified (or all, if
  fewer), drawn by a stable random sample, are checked by reading both retailers'
  product names, options, SKUs and prices against written criteria;
  each verdict and its reason is committed (`docs/precision.md`).
- The same procedure re-runs every day, so the number on the dashboard is always
  the latest measurement. It must be honest and reproducible because it later backs
  the "your price vs competitors" claim on steadydata.co.

## D-012 - Facts only (2026-11-20, owner rule)

Prices are compared as numbers: lowest price, spread percent, price index. No
words that judge a retailer or a price ("MAP violation", "overpriced", "too
expensive", "cheapest store"). Colours carry direction only (lower, higher), and
every coloured value has a text label.

## D-013 - "Your price vs competitors" is a labelled demo (2026-11-20)

Any compared retailer can be picked as "your store". Its price index per brand is
the median, over products it shares with at least one other retailer, of its price
divided by the median price of the others, times 100; products more than 5 % above
or below are listed. It is labelled as a demo on public data on every surface.

## D-014 - What is kept (2026-11-20, owner rules)

Kept: retailer, product and variant ids, handle, brand (vendor), product type,
product and variant titles, options, SKU, GTIN, prices, compare-at prices,
availability. Never kept: descriptions, images, reviews, personal data. Raw
response bodies are parsed in memory and dropped.
