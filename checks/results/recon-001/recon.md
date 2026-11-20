# Recon `recon-001` (recon)

- purpose: Stage 1 over 8 verticals: Shopify, robots, US/USD, multi-brand, SKU and GTIN coverage on 2 sampled products. At most 6 requests per retailer.
- started: 2026-11-20T22:14:35+00:00, finished: 2026-11-20T22:42:08+00:00
- run: https://github.com/siddharthkumarx/cross-store-price-comparison/actions/runs/44827270510
- retailers: 103, passed: 52
- requests: 440; run-wide interval 3.0 s + jitter; per host 4.0 s + jitter; halted: no

| retailer | vertical | host | country | products (meta) | vendors | top vendor | SKU | GTIN (sampled variants) | JSON-LD GTIN | currency | reqs | result |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Apos Audio | audio-hifi | apos.audio | US | 2135 | 25 | 57% | 98% | 1/2 | 1 | USD | 6 | fail: single-brand store |
| Audio Advice | audio-hifi | www.audioadvice.com | US | 4130 | 60 | 12% | 99% | 1/2 | 2 | USD | 6 | PASS |
| Audio Advisor | audio-hifi | www.audioadvisor.com | US | 6872 | 46 | 26% | 100% | 3/3 | 1 | USD | 6 | PASS |
| Audio46 | audio-hifi | audio46.com | US | 3928 | 46 | 28% | 98% | 2/2 | 1 | USD | 6 | PASS |
| Bloom Audio | audio-hifi | bloomaudio.com | US | 1168 | 68 | 9% | 100% | 0/6 | 0 | USD | 6 | PASS |
| HeadAmp | audio-hifi | www.headamp.com | US | 573 | 39 | 10% | 68% | 3/3 | 1 | USD | 6 | PASS |
| Headphones.com | audio-hifi | headphones.com | US | 716 | 57 | 8% | 97% | 1/2 | 1 | USD | 6 | PASS |
| Linsoul | audio-hifi | www.linsoul.com | US | 808 | 52 | 8% | 95% | 0/8 | 0 | USD | 6 | PASS |
| Moon Audio | audio-hifi | www.moon-audio.com | US | 704 | 51 | 9% | 97% | 1/2 | 1 | USD | 6 | PASS |
| Music Direct | audio-hifi | www.musicdirect.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Upscale Audio | audio-hifi | upscaleaudio.com | US | 2104 | 68 | 18% | 100% | 1/2 | 0 | USD | 6 | PASS |
| World Wide Stereo | audio-hifi | www.worldwidestereo.com | US | 25001 | 43 | 16% | 100% | 2/2 | 1 | USD | 6 | PASS |
| Atomic Empire | board-games | atomicempire.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Boardlandia | board-games | boardlandia.com | - | - | - | - | - | - | 0 | - | 4 | fail: blocked or challenged |
| Cardhaus | board-games | www.cardhaus.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| CoolStuffInc | board-games | coolstuffinc.com | - | - | - | - | - | - | 0 | - | 4 | fail: blocked or challenged |
| Funagain Games | board-games | funagain.com | US | 0 | - | - | - | - | 0 | - | 3 | fail: empty catalog, currency not proven USD, single-brand store |
| Game Kastle | board-games | gamekastle.com | US | 24878 | 30 | 35% | 100% | 2/2 | 0 | USD | 6 | PASS |
| Game Nerdz | board-games | www.gamenerdz.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Gamers Guild AZ | board-games | www.gamersguildusa.com | US | 25001 | 18 | 20% | 89% | 2/2 | 1 | USD | 6 | PASS |
| Labyrinth Games | board-games | labyrinthgameshop.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Miniature Market | board-games | www.miniaturemarket.com | - | - | - | - | - | - | 0 | - | 1 | fail: robots disallows a path we use |
| Mox Boarding House | board-games | www.moxboardinghouse.com | US | 2164 | 59 | 36% | 92% | 1/2 | 1 | USD | 6 | PASS |
| Noble Knight Games | board-games | www.nobleknight.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Tabletop Merchant | board-games | tabletopmerchant.com | US | 3712 | 86 | 10% | 98% | 0/2 | 0 | USD | 6 | PASS |
| The Game Steward | board-games | www.thegamesteward.com | US | 3544 | 113 | 15% | 100% | 0/2 | 0 | USD | 6 | PASS |
| 1st-line Equipment | coffee-equipment | 1st-line.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Chris' Coffee | coffee-equipment | www.chriscoffee.com | US | 1292 | 58 | 10% | 100% | 0/3 | 0 | USD | 6 | PASS |
| Clive Coffee | coffee-equipment | clivecoffee.com | - | - | - | - | - | - | 0 | - | 2 | fail: blocked or challenged |
| CoffeeAM | coffee-equipment | www.coffeeam.com | US | 860 | 9 | 50% | 100% | 18/26 | 1 | USD | 6 | PASS |
| Espresso Machine Experts | coffee-equipment | espressomachineexperts.com | - | - | - | - | - | - | 0 | - | 4 | fail: blocked or challenged |
| Espresso Outlet | coffee-equipment | espressooutlet.com | US | 2880 | 33 | 18% | 86% | 1/2 | 0 | USD | 6 | PASS |
| Espresso Parts | coffee-equipment | www.espressoparts.com | US | 6629 | 37 | 12% | 97% | 0/2 | 0 | USD | 6 | PASS |
| Majesty Coffee | coffee-equipment | majestycoffee.com | US | 757 | 43 | 32% | 61% | 0/5 | 0 | USD | 6 | PASS |
| MiiCoffee | coffee-equipment | miicoffee.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Prima Coffee Equipment | coffee-equipment | prima-coffee.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Seattle Coffee Gear | coffee-equipment | www.seattlecoffeegear.com | US | 1442 | 54 | 14% | 100% | 0/2 | 0 | USD | 6 | PASS |
| Voltage Coffee Supply | coffee-equipment | www.voltagecoffeesupply.com | US | 735 | 45 | 12% | 86% | 0/13 | 0 | USD | 6 | PASS |
| Whole Latte Love | coffee-equipment | www.wholelattelove.com | US | 8704 | 37 | 12% | 100% | 0/2 | 0 | USD | 6 | PASS |
| Above Category | cycling | abovecategory.com | US | 453 | 44 | 25% | 91% | 0/8 | 0 | USD | 6 | PASS |
| Art's Cyclery | cycling | www.artscyclery.com | US | 1019 | 28 | 58% | 100% | 16/16 | 1 | USD | 6 | fail: single-brand store |
| Cambria Bike | cycling | cambriabike.com | US | 25001 | 75 | 22% | 100% | 11/11 | 5 | USD | 6 | PASS |
| Contender Bicycles | cycling | contenderbicycles.com | US | 2387 | 43 | 21% | 98% | 24/24 | 0 | USD | 6 | PASS |
| Excel Sports | cycling | www.excelsports.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Fanatik Bike | cycling | www.fanatikbike.com | US | 4258 | 66 | 11% | 87% | 1/12 | 0 | USD | 6 | PASS |
| Freewheel Bike | cycling | www.freewheelbike.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Jenson USA | cycling | www.jensonusa.com | - | - | - | - | - | - | 0 | - | 2 | fail: blocked or challenged |
| R&A Cycles | cycling | racycles.com | US | 8576 | 57 | 36% | 98% | 13/13 | 1 | USD | 6 | PASS |
| The Pro's Closet | cycling | www.theproscloset.com | US | 25001 | 65 | 17% | 100% | 0/2 | 0 | USD | 6 | PASS |
| Treefort Bikes | cycling | www.treefortbikes.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Universal Cycles | cycling | www.universalcycles.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Worldwide Cyclery | cycling | worldwidecyclery.com | US | 19384 | 13 | 50% | 100% | 6/6 | 6 | USD | 6 | PASS |
| Bernal Cutlery | kitchenware | bernalcutlery.com | US | 5062 | 55 | 14% | 87% | 2/2 | 1 | USD | 6 | PASS |
| Burrfection | kitchenware | burrfection.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Carbon Knife Co | kitchenware | carbonknifeco.com | US | 3227 | 44 | 17% | 66% | 2/2 | 1 | USD | 6 | PASS |
| Chef Knives To Go | kitchenware | chefknivestogo.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Chef's Edge | kitchenware | www.chefs-edge.com | AU | 2156 | 50 | 11% | 81% | 0/2 | 1 | USD | 6 | fail: shop country AU |
| Chubo Knives | kitchenware | chuboknives.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Cutlery and More | kitchenware | cutleryandmore.com | US | 3329 | 40 | 10% | 100% | 0/2 | 0 | USD | 6 | PASS |
| Everything Kitchens | kitchenware | everythingkitchens.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Japanese Knife Imports | kitchenware | www.japaneseknifeimports.com | US | 1481 | 35 | 18% | 94% | 0/2 | 1 | USD | 6 | PASS |
| Kitchen Kapers | kitchenware | www.kitchenkapers.com | US | 2967 | 64 | 13% | 100% | 2/2 | 0 | USD | 6 | fail: excluded category: alcohol, tobacco/vape |
| Korin | kitchenware | www.korin.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| MTC Kitchen | kitchenware | mtckitchen.com | US | 2440 | 72 | 9% | 100% | 2/2 | 0 | USD | 6 | PASS |
| Toiro Kitchen | kitchenware | toirokitchen.com | US | 471 | 40 | 12% | 100% | 1/2 | 0 | USD | 6 | PASS |
| Bentgate Mountaineering | outdoor-gear | www.bentgate.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Campsaver | outdoor-gear | www.campsaver.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Dancing Light Gear | outdoor-gear | dancinglightgear.com | - | - | - | - | - | - | 0 | - | 4 | fail: blocked or challenged |
| Garage Grown Gear | outdoor-gear | www.garagegrowngear.com | - | - | - | - | - | - | 0 | - | 2 | fail: blocked or challenged |
| Gear Coop | outdoor-gear | gearcoop.com | - | - | - | - | - | - | 0 | - | 4 | fail: blocked or challenged |
| Mountain Gear | outdoor-gear | mgear.com | - | - | - | - | - | - | 0 | - | 4 | fail: blocked or challenged |
| Mountain Tools | outdoor-gear | mtntools.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Outdoor Gear Exchange | outdoor-gear | www.gearx.com | US | 24885 | 51 | 22% | 100% | 0/2 | 0 | USD | 6 | PASS |
| Piragis | outdoor-gear | www.piragis.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Pro Mountain Sports | outdoor-gear | promountainsports.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Ramsey Outdoor | outdoor-gear | ramseyoutdoor.com | US | 25001 | 42 | 12% | 100% | 4/4 | 3 | USD | 6 | PASS |
| Second Ascent | outdoor-gear | ascentoutdoors.com | US | 12126 | 88 | 11% | 99% | 2/3 | 0 | USD | 6 | PASS |
| Sunlight Sports | outdoor-gear | sunlightsports.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Bentley's Pet Stuff | pet-supplies | earthwisepet.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| EarthWise Pet | pet-supplies | earthwisepet.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Healthy Spot | pet-supplies | healthyspot.com | US | 0 | - | - | - | - | 0 | - | 3 | fail: empty catalog, currency not proven USD, single-brand store |
| Kriser's | pet-supplies | www.krisers.com | - | - | - | - | - | - | 0 | - | 1 | fail: robots disallows a path we use |
| Mud Bay | pet-supplies | www.mudbay.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Only Natural Pet | pet-supplies | www.onlynaturalpet.com | US | 2235 | 57 | 11% | 100% | 14/14 | 0 | USD | 6 | PASS |
| Pet Food Express | pet-supplies | www.petfood.express | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Pet Mountain | pet-supplies | petmountain.com | - | - | - | - | - | - | 0 | - | 4 | fail: blocked or challenged |
| Pet Supplies Plus | pet-supplies | www.petsuppliesplus.com | - | - | - | - | - | - | 0 | - | 1 | fail: blocked or challenged |
| Petflow | pet-supplies | www.petflow.com | - | - | - | - | - | - | 0 | - | 1 | fail: blocked or challenged |
| PetPeople | pet-supplies | www.hollywoodfeed.com | - | - | - | - | - | - | 0 | - | 1 | fail: blocked or challenged |
| Ayla Beauty | skincare | aylabeauty.com | US | 753 | 41 | 40% | 100% | 1/2 | 0 | USD | 6 | PASS |
| Beauty Habit | skincare | www.beautyhabit.com | US | 6241 | 64 | 11% | 100% | 1/2 | 0 | USD | 6 | PASS |
| Cos Bar | skincare | cosbar.com | US | 2005 | 52 | 8% | 100% | 3/3 | 1 | USD | 6 | PASS |
| Credo Beauty | skincare | credobeauty.com | US | 1747 | 72 | 7% | 98% | 2/3 | 1 | USD | 6 | PASS |
| Dermsilk | skincare | www.dermsilk.com | US | 1184 | 30 | 23% | 25% | 1/2 | 2 | USD | 6 | PASS |
| Goop | skincare | goop.com | - | - | - | - | - | - | 0 | - | 1 | fail: blocked or challenged |
| Integrity Botanicals | skincare | www.integritybotanicals.com | US | 878 | 49 | 7% | 100% | 0/2 | 0 | USD | 6 | PASS |
| Ohlolly | skincare | ohlolly.com | US | 502 | 43 | 7% | 100% | 2/2 | 1 | USD | 6 | PASS |
| Safe & Chic | skincare | safeandchic.com | US | 1678 | 12 | 34% | 100% | 3/3 | 1 | USD | 6 | PASS |
| SkinCareRx | skincare | skincarerx.com | - | - | - | - | - | - | 0 | - | 2 | fail: not shopify |
| Soko Glam | skincare | sokoglam.com | US | 506 | 60 | 5% | 99% | 2/2 | 1 | USD | 6 | PASS |
| The Detox Market | skincare | www.thedetoxmarket.com | US | 1842 | 59 | 9% | 99% | 2/2 | 1 | USD | 6 | PASS |
| Thirteen Lune | skincare | thirteenlune.com | US | 846 | 47 | 8% | 95% | 1/2 | 1 | USD | 6 | PASS |
| Violet Grey | skincare | www.violetgrey.com | US | 1367 | 73 | 8% | 99% | 6/6 | 0 | USD | 6 | PASS |

## Notes

- **1st-line Equipment**: /products.json: http 404, text/html; charset=UTF-8
- **Atomic Empire**: /products.json: http 404, text/html
- **Audio Advisor**: screen (0.8% of products): alcohol: AudioQuest Root Beer 18 Active Optical HDMI Cable - HAOC - 30.0 Meter, Audioquest Vodka eARC HDMI Cable
- **Bentgate Mountaineering**: /products.json: http 404, text/html;charset=utf-8
- **Bentley's Pet Stuff**: /products.json: http 406, application/json
- **Bernal Cutlery**: screen (0.4% of products): alcohol: Dryads, Spirits of the Trees - Brian D. Hoefling
- **Boardlandia**: stopped: robots.txt unreachable: retries exhausted: network error: ConnectError
- **Burrfection**: /products.json: http 404, text/html;charset=utf-8
- **Campsaver**: /products.json: http 404, text/html; charset=UTF-8
- **Carbon Knife Co**: screen (0.4% of products): alcohol: Hitohira Imojiya FW 1K6 Paring 80mm Wine Pakka Handle
- **Cardhaus**: /products.json: http 404, text/html; charset=UTF-8
- **Chef Knives To Go**: /products.json: http 404, text/html
- **Chubo Knives**: /products.json: http 404, ?
- **Clive Coffee**: stopped: blocked: cloudflare block
- **CoffeeAM**: screen (0.8% of products): alcohol: DaVinci Butter Rum Syrup 750ml, Bourbon Whiskey Flavored Coffee
- **CoolStuffInc**: stopped: robots.txt unreachable: retries exhausted: network error: ConnectTimeout
- **Credo Beauty**: screen (0.4% of products): alcohol: Color Capsule: The Wine Edit
- **Dancing Light Gear**: stopped: robots.txt unreachable: retries exhausted: network error: ConnectError
- **EarthWise Pet**: /products.json: http 406, application/json
- **Espresso Machine Experts**: stopped: robots.txt unreachable: retries exhausted: network error: ConnectError
- **Espresso Outlet**: screen (0.8% of products): alcohol: Peñas Blancas Pink Bourbon Coffee, Colombia Orange Bourbon Green Coffee
- **Everything Kitchens**: /products.json: http 404, text/html; charset=UTF-8
- **Excel Sports**: /products.json: http 404, text/html; charset=UTF-8
- **Fanatik Bike**: screen (0.4% of products): weapons: Shotgun Pro Child MTB Seat/Handlebars Combo
- **Freewheel Bike**: /products.json: http 404, text/html
- **Game Nerdz**: /products.json: http 404, text/html; charset=UTF-8
- **Garage Grown Gear**: stopped: blocked: cloudflare challenge
- **Gear Coop**: stopped: robots.txt unreachable: retries exhausted: network error: ConnectError
- **Goop**: stopped: blocked: cloudflare challenge (robots.txt)
- **Integrity Botanicals**: screen (0.4% of products): alcohol: No. 12 Bourbon & Apple Soy Candle
- **Jenson USA**: stopped: blocked: cloudflare challenge
- **Kitchen Kapers**: screen (9.6% of products): alcohol: Riedel Buy 3/Get 4 Vinum Pinot Noir/Nebbiolo Wine Glasses, Riedel Buy 3/Get 4 Vinum Riesling/Zinfandel Wine Glasses, Riedel Buy 3/Get 4 Vinum Syrah / Shiraz Wine Glasses; tobacco/vape: Tobacco Leaf Paper Beverage Napkins
- **Korin**: /products.json: http 404, text/html;charset=utf-8
- **Labyrinth Games**: /products.json: http 404, text/html;charset=utf-8
- **MiiCoffee**: /products.json: http 404, ?
- **Mountain Gear**: stopped: robots.txt unreachable: retries exhausted: network error: ConnectError
- **Mountain Tools**: /products.json: http 200, text/html
- **MTC Kitchen**: screen (0.4% of products): alcohol: Kanayama Matte Brown Medium Beer Tumbler with Dimples 9.5 fl oz
- **Mud Bay**: /products.json: http 200, text/html;charset=UTF-8
- **Music Direct**: /products.json: http 404, text/html; charset=UTF-8
- **Noble Knight Games**: /products.json: http 404, text/html
- **Ohlolly**: screen (0.4% of products): alcohol: Umbraphil Rice Wine Bubble Whip Pore Cleanser
- **Only Natural Pet**: screen (0.8% of products): medicines: Tickless Ultrasonic Flea & Tick Protection Device for Dogs, Kin + Kind Flea & Tick Travel Multi-Kit for Dogs
- **Pet Food Express**: /products.json: http 404, text/html; charset=UTF-8
- **Pet Mountain**: stopped: robots.txt unreachable: retries exhausted: network error: ConnectError
- **Pet Supplies Plus**: stopped: blocked: cloudflare challenge (robots.txt)
- **Petflow**: stopped: blocked: cloudflare challenge (robots.txt)
- **PetPeople**: stopped: blocked: cloudflare challenge (robots.txt)
- **Piragis**: /products.json: http 404, text/html; charset=utf-8
- **Prima Coffee Equipment**: /products.json: http 404, text/html; charset=UTF-8
- **Pro Mountain Sports**: /products.json: http 404, text/html; charset=iso-8859-1
- **Ramsey Outdoor**: screen (0.4% of products): alcohol: Alpaca Socks
- **SkinCareRx**: /products.json: http 404, text/plain; charset=utf-8
- **Sunlight Sports**: /products.json: http 404, text/html;charset=utf-8
- **Tabletop Merchant**: screen (0.8% of products): alcohol: Tea & Rum; medicines: World Wonders: Bighorn  Medicine Wheel / Mont Saint-Michel Promo Pack
- **The Detox Market**: screen (0.4% of products): alcohol: White Wine Body Cream With Hyaluronic Acid
- **The Pro's Closet**: screen (0.4% of products): weapons: Pivot Switchblade Pro XT/XTT Mountain Bike - 2021, Medium
- **Thirteen Lune**: screen (0.4% of products): alcohol: Lip Treatment Rum Cake
- **Treefort Bikes**: /products.json: http 404, text/html; charset=utf-8
- **Universal Cycles**: /products.json: http 404, text/html; charset=UTF-8
- **Violet Grey**: screen (4.4% of products): tobacco/vape: Tobacco Memories Extrait; medicines: Radiant Complexion Cream Apricot Glow, Micellar Lotion, Radiant Complexion Cream Rose Glow
