---
license: cc-by-4.0
pretty_name: Cross-store price comparison, skincare and beauty
language:
  - en
tags:
  - prices
  - e-commerce
  - price-comparison
  - gtin
  - skincare
size_categories:
  - 1K<n<10K
---

# Dataset card: cross-store price comparison, skincare and beauty

The same skincare and beauty products at 11 US online stores, matched by barcode (GTIN), part number or name, with each store's price and stock, compared once a day. Rendered from the run of 2026-11-23.

## Files

| file | rows | what |
|---|---:|---|
| `latest/comparison.csv` | 542 | one row per product sold by 2+ stores |
| `latest/offers.csv` | 17,413 | every product option at every store (open SCD2 versions) |
| `latest/possible_matches.csv` | 374 | candidate pairs below the confidence bar, never compared |
| `changes/YYYY/YYYY-MM-DD.csv` | 6 on 2026-11-23 | price moves, new lowest store, stock changes |
| `precision/` | one per run | blind matching precision against GTINs |
| `runs.jsonl` | 5 | one line per run, with every data check |
| release `data-YYYY-MM` | | `offer_history_YYYY-MM.parquet`: every version of every offer in the month |

## Collection

- Public `/products.json` catalogs and product `.js` files of Shopify storefronts, read once a day from one GitHub Actions runner, within robots.txt, at least 3 s between requests per store, with a user agent that links to the repository.
- Prices in integer US cents (USD proven on a product page every run), availability as in stock / out of stock.
- Products in excluded categories (alcohol, tobacco/vape, weapons, adult, CBD, medicines) are never stored.

## Quality, run of 2026-11-23

- Stores read completely: 11/11
- Rows rejected by validation: 0
- Prices proven to be US dollars: USD
- Prices confirmed by a second source: 423/423
- Product options whose barcode has been read so far: 10.5%
- Matching precision (blind, against barcodes): 98.4%


## Limits

- The stores span clean, Korean and luxury beauty; most of their brands are sold by one store only, so most products are not compared (recon overlap: [decisions D-016](https://github.com/siddharthkumarx/cross-store-price-comparison/blob/main/docs/decisions.md)).
- Prices are list prices on the store page; discount codes, member prices and shipping are not included.

## Use and opt-out

Code MIT, data CC BY 4.0 with attribution. Store and product names belong to their owners. Opt-out: [hello@steadydata.co](mailto:hello@steadydata.co), removal within 24 hours.
