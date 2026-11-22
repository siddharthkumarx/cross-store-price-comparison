"""Blind evaluation of the non-GTIN matchers against GTIN truth (docs/decisions.md D-011).

The MPN/SKU and fuzzy matchers never read GTINs. Every pair they propose in which
both offers have a known GTIN is a test case: equal GTINs mean a true match,
different GTINs a false one. From those cases:

* precision = true matches / evaluated pairs, at the threshold in use;
* recall = true matches found / all GTIN-verified pairs (whether proposed or not);
* the threshold for the next run: the lowest score at which precision reaches
  ``TARGET_PRECISION`` on at least ``MIN_EVALUATED`` pairs.

The run compares with the thresholds chosen by the *previous* evaluation and
reports today's precision at those thresholds, so the published number is always
measured on data the threshold was not fitted to.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from crossprice.match import Offer, Pair, Thresholds, gtin_pairs

TARGET_PRECISION = 0.98
MIN_EVALUATED = 100
MIN_THRESHOLD = {"mpn": 0.6, "fuzzy": 0.7}


@dataclass
class TierEval:
    tier: str
    threshold_used: float | None
    evaluated: int = 0  # proposed mutual-best pairs with both GTINs known, at threshold
    true_matches: int = 0
    false_matches: int = 0
    precision: float | None = None
    next_threshold: float | None = None
    curve: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Evaluation:
    gtin_pairs: int
    offers_with_gtin: int
    offers: int
    tiers: dict[str, TierEval]
    combined_evaluated: int = 0
    combined_true: int = 0
    combined_precision: float | None = None
    combined_recall: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def next_thresholds(self) -> Thresholds:
        return Thresholds(
            mpn=self.tiers["mpn"].next_threshold, fuzzy=self.tiers["fuzzy"].next_threshold
        )


def _truth(pair: Pair, offers: Mapping[tuple[str, int], Offer]) -> bool | None:
    ga, gb = offers[pair.a].gtin14, offers[pair.b].gtin14
    if not ga or not gb:
        return None
    return ga == gb


def choose_threshold(cases: list[tuple[float, bool]], tier: str) -> float | None:
    """Lowest score t with precision(score >= t) >= target on >= MIN_EVALUATED cases."""
    floor = MIN_THRESHOLD.get(tier, 0.0)
    ordered = sorted(cases, key=lambda c: -c[0])
    chosen: float | None = None
    tp = 0
    for i, (score, ok) in enumerate(ordered, start=1):
        tp += ok
        nxt = ordered[i][0] if i < len(ordered) else None
        if nxt == score:
            continue  # evaluate only at the end of a run of equal scores
        if score >= floor and i >= MIN_EVALUATED and tp / i >= TARGET_PRECISION:
            chosen = score
    return chosen


def _curve(cases: list[tuple[float, bool]]) -> list[dict[str, Any]]:
    out = []
    for t in (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0):
        sel = [ok for s, ok in cases if s >= t]
        out.append(
            {
                "threshold": t,
                "evaluated": len(sel),
                "true": sum(sel),
                "precision": round(sum(sel) / len(sel), 4) if sel else None,
            }
        )
    return out


def evaluate(offers: list[Offer], candidates: list[Pair], thresholds: Thresholds) -> Evaluation:
    by_key = {o.key: o for o in offers}
    truth_pairs, _ = gtin_pairs(offers)
    truth = {p.ordered for p in truth_pairs}
    tiers: dict[str, TierEval] = {}
    found_true: set[tuple[tuple[str, int], tuple[str, int]]] = set()
    combined_eval = combined_true = 0
    for tier in ("mpn", "fuzzy"):
        t_used = thresholds.get(tier)
        cases: list[tuple[float, bool]] = []
        for p in candidates:
            if p.tier != tier or p.reason != "mutual best":
                continue
            ok = _truth(p, by_key)
            if ok is not None:
                cases.append((p.score, ok))
        te = TierEval(tier=tier, threshold_used=t_used, curve=_curve(cases))
        if t_used is not None:
            sel = [
                p
                for p in candidates
                if p.tier == tier
                and p.reason == "mutual best"
                and p.score >= t_used
                and _truth(p, by_key) is not None
            ]
            te.evaluated = len(sel)
            te.true_matches = sum(1 for p in sel if _truth(p, by_key))
            te.false_matches = te.evaluated - te.true_matches
            te.precision = round(te.true_matches / te.evaluated, 4) if te.evaluated else None
            combined_eval += te.evaluated
            combined_true += te.true_matches
            found_true |= {p.ordered for p in sel if _truth(p, by_key)}
        te.next_threshold = choose_threshold(cases, tier)
        tiers[tier] = te
    return Evaluation(
        gtin_pairs=len(truth),
        offers_with_gtin=sum(1 for o in offers if o.gtin14),
        offers=len(offers),
        tiers=tiers,
        combined_evaluated=combined_eval,
        combined_true=combined_true,
        combined_precision=round(combined_true / combined_eval, 4) if combined_eval else None,
        combined_recall=round(len(found_true & truth) / len(truth), 4) if truth else None,
    )


def manual_sample(pairs: list[Pair], n: int = 100, salt: str = "manual-check") -> list[Pair]:
    """A stable random sample of compared pairs, non-GTIN pairs first."""

    def key(p: Pair) -> str:
        return hashlib.sha256(f"{salt}|{p.ordered}".encode()).hexdigest()

    non_gtin = sorted((p for p in pairs if p.tier != "gtin"), key=key)
    gtin = sorted((p for p in pairs if p.tier == "gtin"), key=key)
    return (non_gtin + gtin)[:n]


def held_back(latest: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The best blind result of a tier that was not used, for "held back" wording.

    A tier is held back when it had no threshold on the run; its curve is still
    measured. Returns the curve point with the highest precision on at least
    ``MIN_EVALUATED`` pairs, with ``cleared`` true when this run's test chose a
    threshold for the next run, or None when every measured tier was used.
    """
    if not latest:
        return None
    best: dict[str, Any] | None = None
    for name, tier in (latest.get("tiers") or {}).items():
        if tier.get("threshold_used") is not None:
            continue
        for point in tier.get("curve") or []:
            if point.get("precision") is None or point["evaluated"] < MIN_EVALUATED:
                continue
            if best is None or point["precision"] > best["precision"]:
                cleared = tier.get("next_threshold") is not None
                best = {"tier": name, "cleared": cleared, **point}
    return best
