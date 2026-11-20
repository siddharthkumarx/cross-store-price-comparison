# Recon `recon-003` (recon)

- purpose: Stage 1 for 12 added clean and indie beauty candidates. recon-002 found skincare meets D-002 on retailers (10) and GTINs (79 % of sampled variants) but not on overlap: the passing retailers span clean, Korean and luxury beauty, which share few brands. At most 6 requests per retailer.
- started: 2026-11-20T23:07:59+00:00, finished: 2026-11-20T23:10:48+00:00
- run: https://github.com/siddharthkumarx/cross-store-price-comparison/actions/runs/44834461170
- retailers: 12, passed: 3
- requests: 45; run-wide interval 3.0 s + jitter; per host 4.0 s + jitter; halted: no

| retailer | vertical | host | country | products (meta) | vendors | top vendor | SKU | GTIN (sampled variants) | JSON-LD GTIN | currency | reqs | result |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Beauteque | skincare | beauteque.com | - | - | - | - | - | - | 0 | - | 1 | fail: robots disallows a path we use |
| Beauty Heroes | skincare | beautyheroes.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| CAP Beauty | skincare | www.capbeauty.com | US | 25 | 6 | 80% | 89% | 0/2 | 0 | USD | 6 | fail: single-brand store |
| Clean Beauty Collective | skincare | cleanbeautycollective.co.nz | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Follain | skincare | follain.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Onda Beauty | skincare | ondabeauty.com | US | 464 | 75 | 6% | 61% | 0/2 | 0 | USD | 6 | PASS |
| Peach & Lily | skincare | www.peachandlily.com | US | 141 | 2 | 60% | 100% | 7/7 | 1 | USD | 6 | fail: single-brand store |
| Petit Vour | skincare | www.petitvour.com | US | 47 | 22 | 15% | 83% | 0/3 | 0 | USD | 6 | PASS |
| Pure Beauty Boutique | skincare | purebeautyboutique.com | - | - | - | - | - | - | 0 | - | 4 | fail: blocked or challenged |
| Shen Beauty | skincare | shenbeauty.com | - | - | - | - | - | - | 0 | - | 2 | fail: blocked or challenged |
| Spruce Beauty | skincare | sprucebeauty.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| The Choosy Chick | skincare | thechoosychick.com | US | 463 | 33 | 16% | 5% | 2/2 | 1 | USD | 6 | PASS |

## Notes

- **Beauty Heroes**: /products.json: http 404, ?
- **Clean Beauty Collective**: /products.json: http 404, text/html; charset=UTF-8
- **Follain**: /products.json: http 404, ?
- **Onda Beauty**: screen (0.4% of products): cannabis/cbd: Restorative Eucalyptus Bath Salts
- **Peach & Lily**: screen (0.7% of products): alcohol: Bio Rice Wine Softening Toner
- **Pure Beauty Boutique**: stopped: robots.txt unreachable: retries exhausted: http 503
- **Shen Beauty**: stopped: blocked: cloudflare challenge
- **Spruce Beauty**: /products.json: http 404, text/html;charset=utf-8
