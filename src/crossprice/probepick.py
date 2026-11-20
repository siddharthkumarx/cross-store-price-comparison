"""Pick product handles for a GTIN-confirmation recon (the ``handles`` of a request).

    python -m crossprice.probepick checks/results/recon-002 --cap 18 --seed 20261120

From committed stage-2 catalogs, takes the mutual-best candidate pairs scoring at
least 0.5, keeps one pair per product pair, and draws pairs at random within the
score bands 0.5-0.6, 0.6-0.7, 0.7-0.8 and 0.8+ in turn, until every retailer has
``cap`` handles. Probing both products of a pair tells, by GTIN, whether the pair
is the same item, so the precision of each band can be measured (D-002).
Prints the ``handles`` block as YAML. Seeded, so the pick is reproducible.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from crossprice.match import Pair, candidate_pairs, to_offer
from crossprice.overlap import load_catalog

BANDS = ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01))


def pick(
    result_dir: Path, retailers: list[str], cap: int, seed: int
) -> tuple[dict[str, list[str]], Counter[tuple[float, float]]]:
    rows = [r for s in retailers for r in load_catalog(result_dir / "catalogs" / f"{s}.csv.gz", s)]
    by_key = {r.key: r for r in rows}
    pairs = [
        p
        for p in candidate_pairs([to_offer(r) for r in rows])
        if p.reason == "mutual best" and p.score >= BANDS[0][0]
    ]
    seen: set[tuple[str, int, str, int]] = set()
    unique: list[Pair] = []
    for p in pairs:
        k = (p.a[0], by_key[p.a].product_id, p.b[0], by_key[p.b].product_id)
        if k not in seen:
            seen.add(k)
            unique.append(p)
    rng = random.Random(seed)  # noqa: S311  (a reproducible sample, not security)
    pools = {b: [p for p in unique if b[0] <= p.score < b[1]] for b in BANDS}
    for pool in pools.values():
        rng.shuffle(pool)
    load: dict[str, set[str]] = defaultdict(set)
    chosen: Counter[tuple[float, float]] = Counter()
    progress = True
    while progress:
        progress = False
        for band in BANDS:
            while pools[band]:
                p = pools[band].pop()
                ha, hb = by_key[p.a].handle, by_key[p.b].handle
                extra_a = ha not in load[p.a[0]]
                extra_b = hb not in load[p.b[0]]
                if len(load[p.a[0]]) + extra_a > cap or len(load[p.b[0]]) + extra_b > cap:
                    continue
                load[p.a[0]].add(ha)
                load[p.b[0]].add(hb)
                chosen[band] += 1
                progress = True
                break
    return {k: sorted(v) for k, v in sorted(load.items())}, chosen


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("result_dir", type=Path)
    p.add_argument("--retailer", action="append", required=True)
    p.add_argument("--cap", type=int, default=18)
    p.add_argument("--seed", type=int, default=20261120)
    a = p.parse_args(argv)
    handles, chosen = pick(a.result_dir, a.retailer, a.cap, a.seed)
    print(f"# pairs per band: {dict(chosen)}", file=sys.stderr)
    sys.stdout.write(yaml.safe_dump({"handles": handles}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
