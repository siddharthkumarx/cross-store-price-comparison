# Recon `recon-005` (catalog)

- purpose: Re-test under D-016 for the five skincare retailers that answered HTTP 429 in recon-004 (the second full read of their catalogs within 30 minutes): one catalog read each after a cool-down of at least 90 minutes, plus the product .js probes recon-004 planned for them but could not make (same handles).
- started: 2026-11-21T01:02:35+00:00, finished: 2026-11-21T01:14:49+00:00
- run: https://github.com/siddharthkumarx/cross-store-price-comparison/actions/runs/44847696199
- retailers: 5, passed: 3
- requests: 103; run-wide interval 3.0 s + jitter; per host 4.0 s + jitter; halted: run halted: edge throttling persisted (8 429s in a row)

| retailer | vertical | host | country | products (meta) | vendors | top vendor | SKU | GTIN (sampled variants) | JSON-LD GTIN | currency | reqs | result |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Cos Bar | skincare | cosbar.com | US | 2005 | 76 | 8% | 100% | 46/46 | 1 | USD | 30 | PASS |
| Credo Beauty | skincare | credobeauty.com | US | 1746 | 147 | 3% | 99% | 55/56 | 1 | USD | 28 | PASS |
| Integrity Botanicals | skincare | www.integritybotanicals.com | - | - | - | - | - | - | 0 | - | 8 | fail: stopped mid-recon: retries exhausted: http 429, empty catalog, currency not proven USD, single-brand store, needed 429 retries |
| Safe & Chic | skincare | safeandchic.com | US | 1678 | 87 | 10% | 100% | 20/22 | 1 | USD | 27 | PASS |
| The Detox Market | skincare | www.thedetoxmarket.com | - | - | - | - | - | - | 0 | - | 10 | fail: stopped mid-recon: retries exhausted: http 429, empty catalog, currency not proven USD, single-brand store, needed 429 retries |

## Notes

- **Cos Bar**: screen (0.0% of products): tobacco/vape: Tobacco Vanille Eau de Parfum
- **Credo Beauty**: screen (0.1% of products): alcohol: Color Capsule: The Wine Edit, Charcoal Deodorant Black Oak & Bourbon
- **Integrity Botanicals**: stopped: retries exhausted: http 429
- **Safe & Chic**: screen (2.2% of products): alcohol: Gold Stag Deer Whiskey Glasses; medicines: Free Bird / Botanical Perfume, GLOW POTION / radiant body oil, GODDESS GLOW / blushing buttery body cream
- **The Detox Market**: stopped: retries exhausted: http 429
