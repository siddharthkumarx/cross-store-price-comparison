# Matching precision

How this project measures whether two stores' listings it compares are really the
same item, and how anyone can reproduce the number. Decision: D-011 in
[decisions.md](decisions.md).

## Why it matters

A price comparison is only as good as its matching. Comparing a 1 kg bag with a
250 g bag, or a black grinder with a white one, produces a "price gap" that does not
exist. So every compared pair carries the matcher that found it, and the matchers
that can be wrong are measured every day.

## The three matchers

| tier | how a pair is found | can it be wrong? |
|---|---|---|
| 1 barcode | the same GTIN barcode (normalised to GTIN-14, check digit verified, store-internal ranges rejected) at both stores | only if a store publishes a wrong barcode; treated as ground truth |
| 2 part number | same brand and the same manufacturer part number (the store SKU, when it looks like one and is unique within the store) | yes, measured |
| 3 name | same brand; model words, model numbers, sizes and options compared, with a price sanity check; a score from 0 to 1 | yes, measured |

Code: [`src/crossprice/match.py`](../src/crossprice/match.py).

## The blind test, every run

1. Tiers 2 and 3 never read barcodes. They propose pairs from names, SKUs and
   options only.
2. Every proposed pair in which **both** stores publish a barcode is a test case:
   equal barcodes mean the pair is right, different barcodes mean it is wrong.
3. **Precision** = right pairs / test cases, at the score threshold in use.
   **Recall** = barcode pairs the blind matchers also found / all barcode pairs.
4. A tier is used for the comparison only above the lowest score at which its
   precision reached **98 % on at least 100 test cases**. The threshold is chosen
   on one run and applied on the next, so the published precision is always
   measured on data the threshold was not fitted to.
5. Until a tier reaches that bar, only barcode pairs are compared.

The numbers of every run, with their counts and the date, are committed in
[`data/precision/`](../data/precision/) (`latest.json` and one file per day). Code:
[`src/crossprice/precision.py`](../src/crossprice/precision.py). The same files
feed the dashboard and the `matching_precision` block of `data/public/feed.json`.

## What the blind test cannot see

Test cases need barcodes at both stores, so the pairs where one store publishes no
barcode (exactly the pairs tiers 2 and 3 add) are not covered by it. The manual
check below covers them.

Different barcodes do not always mean different items. In the first daily run
(2026-11-21) the name matcher paired 184 products that carry a barcode at both
stores; 8 had different barcodes. Five of the 8 are the same item at the same
price under two barcodes, because the brand moved to a new GS1 company prefix
(Augustinus Bader 5060552 and 5060990, EVOLVh 850012 and 860014) or registered
uses two barcodes for one product (MDSolarSciences). The other three are, or may
be, different items: a mascara shade against the default listing, an eye cream
refill against the "Nomad" listing, and one eye cream at two prices under two
barcodes of the same brand. The blind test counts all 8 as wrong, so the
published precision is a lower bound.

## Manual check

A stable random sample of 100 compared pairs that are not barcode-verified (filled
up with barcode pairs if fewer exist) is checked by reading both stores' product
names, options, SKUs and prices against these criteria:

- **same item**: same brand, same model, same size or capacity, same colour or
  finish, same pack count;
- **different item**: any of those differs;
- **unclear**: the listings do not say enough to decide (counted as not right).

Each verdict and its reason is committed as a CSV in [`docs/manual-checks/`](manual-checks/),
with the date and the run it was drawn from. The sample is drawn by
`python -m crossprice.precision_sample`, so anyone can draw the same pairs again.
