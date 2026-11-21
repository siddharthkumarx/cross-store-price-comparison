# Repository settings

Settings that live on GitHub, not in files. Paste them once.

## About

**Description** (under 350 characters):

> Daily cross-store price comparison: the same skincare and beauty products at 11 US online stores, matched by barcode (GTIN), with lowest price, price gap and stock as CSV, a dashboard and a public matching-precision number. Python, DuckDB, GitHub Actions. By SteadyData.

**Website:** https://siddharthkumar.com/cross-store-price-comparison/

**Topics** (16):

```
price-comparison
competitor-price-monitoring
price-monitoring
product-matching
entity-resolution
gtin
web-scraping
ecommerce
shopify
data-pipeline
python
duckdb
parquet
github-actions
open-data
beauty
```

Home page: Releases on (data downloads), Packages off, Deployments on (GitHub Pages).

## Social preview

Settings, General, Social preview: upload `assets/social-preview.png` (1280 x 640).

## GitHub Pages

1. Settings, Pages, Build and deployment, Source: **GitHub Actions**.
2. Settings, Secrets and variables, Actions, Variables: add `PAGES_ENABLED` = `true`.
3. The next `daily` run (or Actions, daily, Run workflow) deploys `site/`. Because
   the user site `siddharthkumarx.github.io` serves the custom domain
   `siddharthkumar.com`, this project site is served at
   https://siddharthkumar.com/cross-store-price-comparison/ with no domain setting
   in this repository.

## Actions

Settings, Actions, General, Workflow permissions: "Read and write permissions"
(the workflows commit `data/` and `checks/results/`). Each workflow still declares
only the permissions it needs.
