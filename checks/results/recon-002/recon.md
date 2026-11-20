# Recon `recon-002` (catalog)

- purpose: Stage 2 for the two verticals with the most recon-001 passes whose catalogs fit the daily page budget (at most 4,000 products, D-005): skincare (11) and, for comparison, audio/hi-fi (7). Whole catalog up to 16 pages, 8 random product .js probes for GTIN coverage, 1 product page, robots.txt and meta.json. At most 27 requests per retailer.
- started: 2026-11-20T22:43:41+00:00, finished: 2026-11-20T23:03:02+00:00
- run: https://github.com/siddharthkumarx/cross-store-price-comparison/actions/runs/44831266297
- retailers: 18, passed: 17
- requests: 301; run-wide interval 3.0 s + jitter; per host 4.0 s + jitter; halted: no

| retailer | vertical | host | country | products (meta) | vendors | top vendor | SKU | GTIN (sampled variants) | JSON-LD GTIN | currency | reqs | result |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Audio46 | audio-hifi | audio46.com | US | 3928 | 135 | 9% | 99% | 8/12 | 1 | USD | 27 | PASS |
| Bloom Audio | audio-hifi | bloomaudio.com | US | 1168 | 87 | 7% | 100% | 4/13 | 0 | USD | 16 | PASS |
| HeadAmp | audio-hifi | www.headamp.com | US | 573 | 47 | 10% | 83% | 7/11 | 1 | USD | 14 | PASS |
| Headphones.com | audio-hifi | headphones.com | US | 716 | 76 | 7% | 99% | 4/11 | 1 | USD | 14 | PASS |
| Linsoul | audio-hifi | www.linsoul.com | US | 808 | 77 | 8% | 98% | 0/25 | 0 | USD | 15 | PASS |
| Moon Audio | audio-hifi | www.moon-audio.com | US | 704 | 72 | 20% | 95% | 7/31 | 0 | USD | 14 | PASS |
| Upscale Audio | audio-hifi | upscaleaudio.com | US | 2107 | 156 | 6% | 100% | 5/28 | 0 | USD | 20 | PASS |
| Ayla Beauty | skincare | aylabeauty.com | US | 753 | 73 | 29% | 98% | 16/18 | 0 | USD | 15 | PASS |
| Cos Bar | skincare | cosbar.com | US | 2005 | 76 | 8% | 100% | 9/9 | 1 | USD | 20 | PASS |
| Credo Beauty | skincare | credobeauty.com | US | 1747 | 147 | 3% | 99% | 9/10 | 1 | USD | 18 | PASS |
| Dermsilk | skincare | www.dermsilk.com | US | 1184 | 36 | 7% | 64% | 4/8 | 0 | USD | 16 | PASS |
| Integrity Botanicals | skincare | www.integritybotanicals.com | US | 877 | 81 | 6% | 95% | 4/16 | 0 | USD | 15 | PASS |
| Ohlolly | skincare | ohlolly.com | US | 502 | 56 | 6% | 100% | 8/8 | 1 | USD | 14 | PASS |
| Safe & Chic | skincare | safeandchic.com | US | 1678 | 87 | 10% | 100% | 12/14 | 1 | USD | 18 | PASS |
| Soko Glam | skincare | sokoglam.com | US | 506 | 81 | 6% | 100% | 8/8 | 1 | USD | 14 | PASS |
| The Detox Market | skincare | www.thedetoxmarket.com | US | 1842 | 145 | 5% | 100% | 11/11 | 1 | USD | 19 | PASS |
| Thirteen Lune | skincare | thirteenlune.com | US | 846 | 140 | 6% | 98% | 7/9 | 1 | USD | 15 | PASS |
| Violet Grey | skincare | www.violetgrey.com | US | 1367 | 161 | 4% | 99% | 17/18 | 0 | USD | 17 | fail: excluded category: alcohol, medicines, tobacco/vape |

## Notes

- **Audio46**: screen (0.1% of products): alcohol: Queen of Audio Whisky Silver Plated In-Ear Monitor Upgrade Cable, Queen of Audio Rum 6N OCC with silver plated Cable
- **Ayla Beauty**: screen (0.1% of products): medicines: The Organic Pharmacy Manuka Face Cream
- **Bloom Audio**: screen (0.1% of products): alcohol: AudioQuest Vodka Ethernet | Audiophile Ethernet Cable
- **Cos Bar**: screen (0.0% of products): tobacco/vape: Tobacco Vanille Eau de Parfum
- **Credo Beauty**: screen (0.1% of products): alcohol: Color Capsule: The Wine Edit, Charcoal Deodorant Black Oak & Bourbon
- **Integrity Botanicals**: screen (0.1% of products): alcohol: No. 12 Bourbon & Apple Soy Candle
- **Linsoul**: screen (0.2% of products): alcohol: QoA Gin, QOA Whisky Cable
- **Ohlolly**: screen (0.2% of products): alcohol: Umbraphil Rice Wine Bubble Whip Pore Cleanser
- **Safe & Chic**: screen (2.2% of products): alcohol: Gold Stag Deer Whiskey Glasses; medicines: Free Bird / Botanical Perfume, GLOW POTION / radiant body oil, GODDESS GLOW / blushing buttery body cream
- **Soko Glam**: screen (0.2% of products): alcohol: Bio-Peel Gauze Peeling Wine
- **The Detox Market**: screen (0.9% of products): alcohol: White Wine Body Cream With Hyaluronic Acid, The Takesumi Detox - Black Oak & Bourbon; medicines: Jade Gua Sha Tool, The Jade Massaging Gua Sha Comb, The Vitality Qi White Jade Gua Sha Sculpting Tool; adult: Spot - Green, Spot - Grey, Drop
- **Thirteen Lune**: screen (0.4% of products): alcohol: Lip Treatment Rum Cake, Bourbon Vanilla Signature Candle; adult: Spot Personal Vibrator
- **Upscale Audio**: screen (0.2% of products): alcohol: AudioQuest Vodka RJ/E Ethernet Cable, AudioQuest Vodka Optical Cable, AudioQuest Vodka e-ARC HDMI Cable; weapons: Acoustic Zen Satori Shotgun Bi-Wire Speaker Cable (OPEN)
- **Violet Grey**: screen (7.2% of products): tobacco/vape: Tobacco Memories Extrait, Tobacco Memories Eau De Parfum, Tobacco Vanille Eau de Parfum; medicines: Radiant Complexion Cream Apricot Glow, Micellar Lotion, Radiant Complexion Cream Rose Glow; alcohol: Ile Bourbon Extrait De Parfum
