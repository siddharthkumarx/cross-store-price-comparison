# Recon `recon-004` (catalog)

- purpose: Stage 2 for the skincare retailers: the 3 that passed recon-003 get their whole catalog and 4 random GTIN probes; all 13 get product .js probes on overlap candidates drawn from the recon-002 catalogs at random within score bands 0.5-0.6, 0.6-0.7, 0.7-0.8 and 0.8+, so the precision of each cut-off can be checked against GTINs (D-002). At most 18 named probes per retailer.
- started: 2026-11-20T23:11:54+00:00, finished: 2026-11-20T23:31:47+00:00
- run: https://github.com/siddharthkumarx/cross-store-price-comparison/actions/runs/44834949148
- retailers: 13, passed: 8
- requests: 204; run-wide interval 3.0 s + jitter; per host 4.0 s + jitter; halted: no

| retailer | vertical | host | country | products (meta) | vendors | top vendor | SKU | GTIN (sampled variants) | JSON-LD GTIN | currency | reqs | result |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Ayla Beauty | skincare | aylabeauty.com | US | 753 | 73 | 29% | 98% | 37/37 | 0 | USD | 29 | PASS |
| Cos Bar | skincare | cosbar.com | - | - | - | - | - | - | 0 | - | 9 | fail: blocked mid-recon, empty catalog, currency not proven USD, single-brand store, needed 429 retries |
| Credo Beauty | skincare | credobeauty.com | - | - | - | - | - | - | 0 | - | 9 | fail: blocked mid-recon, empty catalog, currency not proven USD, single-brand store, needed 429 retries |
| Dermsilk | skincare | www.dermsilk.com | US | 1184 | 36 | 7% | 64% | 12/16 | 0 | USD | 24 | PASS |
| Integrity Botanicals | skincare | www.integritybotanicals.com | - | - | - | - | - | - | 0 | - | 8 | fail: blocked mid-recon, empty catalog, currency not proven USD, single-brand store, needed 429 retries |
| Ohlolly | skincare | ohlolly.com | US | 502 | 56 | 6% | 100% | 24/24 | 1 | USD | 28 | PASS |
| Onda Beauty | skincare | ondabeauty.com | US | 464 | 89 | 4% | 67% | 1/4 | 0 | USD | 9 | PASS |
| Petit Vour | skincare | www.petitvour.com | US | 47 | 22 | 15% | 83% | 0/6 | 0 | USD | 8 | PASS |
| Safe & Chic | skincare | safeandchic.com | - | - | - | - | - | - | 0 | - | 9 | fail: blocked mid-recon, empty catalog, currency not proven USD, single-brand store, needed 429 retries |
| Soko Glam | skincare | sokoglam.com | US | 506 | 81 | 6% | 100% | 26/26 | 1 | USD | 28 | PASS |
| The Choosy Chick | skincare | thechoosychick.com | US | 463 | 38 | 12% | 4% | 10/10 | 1 | USD | 9 | PASS |
| The Detox Market | skincare | www.thedetoxmarket.com | - | - | - | - | - | - | 0 | - | 8 | fail: blocked mid-recon, empty catalog, currency not proven USD, single-brand store, needed 429 retries |
| Thirteen Lune | skincare | thirteenlune.com | US | 846 | 140 | 6% | 98% | 24/26 | 1 | USD | 26 | PASS |

## Notes

- **Ayla Beauty**: screen (0.1% of products): medicines: The Organic Pharmacy Manuka Face Cream
- **Cos Bar**: stopped: retries exhausted: http 429
- **Credo Beauty**: stopped: retries exhausted: http 429
- **Integrity Botanicals**: stopped: retries exhausted: http 429
- **Ohlolly**: screen (0.2% of products): alcohol: Umbraphil Rice Wine Bubble Whip Pore Cleanser
- **Onda Beauty**: screen (0.9% of products): cannabis/cbd: Restorative Eucalyptus Bath Salts, Muscle Soak with Arnica - Bath Salts, California Bloom Body Oil
- **Safe & Chic**: stopped: retries exhausted: http 429
- **Soko Glam**: screen (0.2% of products): alcohol: Bio-Peel Gauze Peeling Wine
- **The Detox Market**: stopped: retries exhausted: http 429
- **Thirteen Lune**: screen (0.4% of products): alcohol: Lip Treatment Rum Cake, Bourbon Vanilla Signature Candle; adult: Spot Personal Vibrator
