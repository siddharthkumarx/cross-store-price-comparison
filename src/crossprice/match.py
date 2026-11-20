"""Find the same item at different retailers (docs/decisions.md D-009, D-011).

An **offer** is one variant at one retailer. Three matchers propose offer pairs
at two different retailers:

1. ``gtin``: equal GTIN-14 (exact; confidence 1.0).
2. ``mpn``: same normalised brand and same normalised SKU, where the SKU looks
   like a manufacturer part number.
3. ``fuzzy``: same normalised brand; a weighted overlap of model tokens and
   variant options, with number tokens (model numbers, sizes) required to agree
   and the price ratio as a sanity check.

Tiers 2 and 3 never look at GTINs, so their output can be scored against GTIN
truth (:mod:`crossprice.precision`). A tier-2/3 pair is compared only when its
score reaches the tier's threshold, it is the best candidate in both directions,
and known GTINs do not disagree. Accepted pairs are joined into products with at
most one offer per retailer; everything else above ``POSSIBLE_MIN`` is a possible
match, written out but never compared.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from crossprice.gtin import normalize_gtin
from crossprice.models import OfferRow

Tier = Literal["gtin", "mpn", "fuzzy"]
TIER_RANK: dict[str, int] = {"gtin": 0, "mpn": 1, "fuzzy": 2}
POSSIBLE_MIN = 0.5
PRICE_RATIO_REJECT = 2.0
PRICE_RATIO_PENALTY = 1.5

_LEGAL = {
    "inc", "llc", "ltd", "co", "corp", "corporation", "company", "gmbh", "srl", "spa",
    "usa", "us", "america", "intl", "international", "the", "official", "brand", "brands",
}  # fmt: skip
_STOP = {
    "a", "an", "and", "the", "with", "for", "by", "of", "in", "on", "to", "w", "x",
    "new", "edition", "version", "model", "series", "default", "title",
}  # fmt: skip
_UNITS = {
    "g", "kg", "mg", "ml", "l", "oz", "lb", "lbs", "mm", "cm", "m", "in", "inch", "ft",
    "w", "v", "mah", "pack", "pk", "ct", "pc", "pcs", "piece", "pieces", "cup", "cups",
    "qt", "gal", "hz", "khz", "ohm", "ohms", "db",
}  # fmt: skip
# Trailing words that brands add or drop ("Ilia" / "ILIA Beauty", "Tom Ford Beauty").
_BRAND_SUFFIX = {
    "beauty", "skincare", "skin", "care", "cosmetics", "organics", "botanicals",
    "parfum", "parfums", "science", "labs", "lab",
}  # fmt: skip
# Option values that mean "no option".
_NO_OPTION = {"default title", "default", "one size", "onesize", "os", "n/a", "na", "standard"}
_TOKEN = re.compile(r"[a-z0-9]+")
_MARKS = re.compile("[\u2122\u00ae\u00a9]")  # trade mark, registered, copyright
_OPTION_DETAIL = re.compile(r"\s*(\(|\s[-\u2013\u2014]\s|:\s).*$")


def fold(text: str) -> str:
    """Lower case, accents removed, ``&`` spelt out."""
    text = _MARKS.sub(" ", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.lower().replace("&", " and ").replace("+", " plus ")


def brand_key(brand: str, aliases: Mapping[str, str] | None = None) -> str:
    """Normalised brand: folded, punctuation and legal suffixes removed, aliases applied."""
    words = [w for w in _TOKEN.findall(fold(brand)) if w not in _LEGAL]
    while len(words) > 1 and words[-1] in _BRAND_SUFFIX:
        words.pop()
    key = "".join(words)
    if aliases:
        key = aliases.get(key, key)
    return key


def tokens(text: str) -> list[str]:
    """Folded word tokens with a number followed by a unit joined ("250 ml" -> "250ml")."""
    raw = _TOKEN.findall(fold(text))
    out: list[str] = []
    for tok in raw:
        if out and tok in _UNITS and out[-1].isdigit():
            out[-1] = out[-1] + tok
        else:
            out.append(tok)
    return [t for t in out if t not in _STOP]


def option_value(value: str) -> str:
    """The identifying part of an option value: "Lady (cranberry...)" -> "lady"."""
    main = _OPTION_DETAIL.sub("", value.strip())
    main = " ".join(_TOKEN.findall(fold(main)))
    return "" if main in _NO_OPTION else main


def sku_key(sku: str, variant_id: int) -> str | None:
    """A SKU that can be a manufacturer part number, normalised; else ``None``.

    At least 4 characters with a digit, not the Shopify variant id, not a GTIN.
    (Uniqueness within a retailer is checked by the caller.)
    """
    key = "".join(_TOKEN.findall(fold(sku))).upper()
    if len(key) < 4 or not any(ch.isdigit() for ch in key):
        return None
    if key == str(variant_id) or normalize_gtin(key) is not None:
        return None
    return key


@dataclass(frozen=True)
class Offer:
    """The matching view of one offer."""

    key: tuple[str, int]
    product_id: int
    brand: str
    brand_key: str
    title: str
    model: frozenset[str]
    numbers: frozenset[str]
    options: frozenset[str]
    sku_key: str | None
    gtin14: str | None
    price_cents: int

    @property
    def retailer_id(self) -> str:
        return self.key[0]


def to_offer(row: OfferRow, aliases: Mapping[str, str] | None = None) -> Offer:
    bkey = brand_key(row.brand, aliases)
    brand_tokens = set(tokens(row.brand)) | {bkey}
    model = [t for t in tokens(row.product_title) if t not in brand_tokens]
    opts = {t for o in row.options for t in tokens(option_value(o))}
    words = set(model) | opts
    return Offer(
        key=row.key,
        product_id=row.product_id,
        brand=row.brand,
        brand_key=bkey,
        title=row.product_title,
        model=frozenset(model),
        numbers=frozenset(t for t in words if any(ch.isdigit() for ch in t)),
        options=frozenset(opts),
        sku_key=sku_key(row.sku, row.variant_id),
        gtin14=row.gtin14,
        price_cents=row.price_cents,
    )


@dataclass(frozen=True)
class Pair:
    a: tuple[str, int]
    b: tuple[str, int]
    tier: Tier
    score: float
    reason: str

    @property
    def ordered(self) -> tuple[tuple[str, int], tuple[str, int]]:
        return (self.a, self.b) if self.a <= self.b else (self.b, self.a)


def _price_factor(a: Offer, b: Offer) -> float:
    ratio = max(a.price_cents, b.price_cents) / min(a.price_cents, b.price_cents)
    if ratio > PRICE_RATIO_REJECT:
        return 0.0
    if ratio > PRICE_RATIO_PENALTY:
        return 0.8
    return 1.0


def _option_factor(a: Offer, b: Offer) -> float:
    if a.options and b.options:
        if a.options == b.options:
            return 1.0
        if not a.options & b.options:
            return 0.0
        return 0.8
    if a.options or b.options:
        # One side has no options: they must at least appear in the other's title.
        opts, other = (a.options, b) if a.options else (b.options, a)
        return 1.0 if opts <= other.model else 0.85
    return 1.0


def _number_factor(a: Offer, b: Offer) -> float:
    if a.numbers == b.numbers:
        return 1.0
    if a.numbers and b.numbers and (a.numbers - b.numbers) and (b.numbers - a.numbers):
        return 0.0  # both name a model number or size, and they differ
    return 0.7  # one side names a number the other does not


class Idf:
    """Token weights within one brand: rare tokens identify a model, common ones do not."""

    def __init__(self, offers: Iterable[Offer]) -> None:
        df: Counter[str] = Counter()
        seen_products: set[tuple[str, int]] = set()
        for o in offers:
            pid = (o.retailer_id, o.product_id)
            if pid in seen_products:
                continue
            seen_products.add(pid)
            df.update(o.model | o.options)
        self.n = max(1, len(seen_products))
        self.df = df

    def w(self, tok: str) -> float:
        return math.log(1 + self.n / (1 + self.df.get(tok, 0))) + 0.1


def text_similarity(a: Offer, b: Offer, idf: Idf) -> float:
    """Half weighted Jaccard, half weighted containment of the smaller token set.

    Containment credits a store that names the same model with fewer words
    ("UnCoverup" / "UnCoverup Concealer"); Jaccard keeps extra words costly.
    """
    ta, tb = a.model | a.options, b.model | b.options
    union = ta | tb
    if not ta or not tb:
        return 0.0
    common = sum(idf.w(t) for t in ta & tb)
    jaccard = common / sum(idf.w(t) for t in union)
    containment = common / min(sum(idf.w(t) for t in ta), sum(idf.w(t) for t in tb))
    return 0.5 * jaccard + 0.5 * containment


def fuzzy_score(a: Offer, b: Offer, idf: Idf) -> float:
    if a.brand_key != b.brand_key or not a.brand_key:
        return 0.0
    base = text_similarity(a, b, idf)
    return round(base * _number_factor(a, b) * _option_factor(a, b) * _price_factor(a, b), 4)


def mpn_score(a: Offer, b: Offer, idf: Idf) -> float:
    if not a.sku_key or a.sku_key != b.sku_key or a.brand_key != b.brand_key or not a.brand_key:
        return 0.0
    score = 0.85 + 0.15 * text_similarity(a, b, idf)
    return round(score * _price_factor(a, b) * (_option_factor(a, b) or 0.5), 4)


def _unique_skus(offers: list[Offer]) -> set[tuple[str, int]]:
    """Offers whose SKU is not shared by two different products at the same retailer."""
    products: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    for o in offers:
        if o.sku_key:
            products[(o.retailer_id, o.brand_key, o.sku_key)].add(o.product_id)
    return {
        o.key
        for o in offers
        if o.sku_key and len(products[(o.retailer_id, o.brand_key, o.sku_key)]) == 1
    }


def candidate_pairs(offers: list[Offer], max_df_share: float = 0.3) -> list[Pair]:
    """Tier-2 and tier-3 candidate pairs (best per offer and other retailer, both ways).

    Never reads GTINs. Pairs scoring below ``POSSIBLE_MIN`` are dropped.
    """
    by_brand: dict[str, list[Offer]] = defaultdict(list)
    for o in offers:
        if o.brand_key:
            by_brand[o.brand_key].append(o)
    unique_sku = _unique_skus(offers)
    best: dict[tuple[tuple[str, int], str], list[tuple[float, Tier, tuple[str, int]]]] = (
        defaultdict(list)
    )
    scored: dict[tuple[tuple[str, int], tuple[str, int]], tuple[float, Tier]] = {}
    for group in by_brand.values():
        if len({o.retailer_id for o in group}) < 2:
            continue
        idf = Idf(group)
        index: dict[str, list[Offer]] = defaultdict(list)
        sku_index: dict[str, list[Offer]] = defaultdict(list)
        for o in group:
            for t in o.model | o.numbers:
                if idf.df.get(t, 0) <= max(2, max_df_share * idf.n) or t in o.numbers:
                    index[t].append(o)
            if o.key in unique_sku and o.sku_key:
                sku_index[o.sku_key].append(o)
        for a in group:
            cands: dict[tuple[str, int], Offer] = {}
            for t in a.model | a.numbers:
                for b in index.get(t, ()):
                    if b.retailer_id != a.retailer_id:
                        cands[b.key] = b
            if a.key in unique_sku and a.sku_key:
                for b in sku_index.get(a.sku_key, ()):
                    if b.retailer_id != a.retailer_id:
                        cands[b.key] = b
            for b in cands.values():
                pk = (a.key, b.key) if a.key <= b.key else (b.key, a.key)
                if pk in scored:
                    s, tier = scored[pk]
                else:
                    s_m = mpn_score(a, b, idf) if {a.key, b.key} <= unique_sku else 0.0
                    s_f = fuzzy_score(a, b, idf)
                    s, tier = (s_m, "mpn") if s_m >= s_f and s_m > 0 else (s_f, "fuzzy")
                    scored[pk] = (s, tier)
                if s >= POSSIBLE_MIN:
                    best[(a.key, b.retailer_id)].append((s, tier, b.key))
    tops: dict[tuple[tuple[str, int], str], tuple[float, tuple[str, int], bool]] = {}
    for k, lst in best.items():
        lst.sort(key=lambda x: (-x[0], x[2]))
        tie = len(lst) > 1 and lst[1][0] == lst[0][0]
        tops[k] = (lst[0][0], lst[0][2], tie)
    pairs: list[Pair] = []
    done: set[tuple[tuple[str, int], tuple[str, int]]] = set()
    for (akey, _), (s, bkey, tie) in tops.items():
        pk = (akey, bkey) if akey <= bkey else (bkey, akey)
        if pk in done:
            continue
        done.add(pk)
        back = tops.get((bkey, akey[0]))
        mutual = back is not None and back[1] == akey
        tier = scored[pk][1]
        if tie or (back is not None and back[2]):
            reason = "tied candidates"
        elif mutual:
            reason = "mutual best"
        else:
            reason = "not mutual"
        pairs.append(Pair(pk[0], pk[1], tier, s, reason))
    pairs.sort(key=lambda p: (-p.score, p.ordered))
    return pairs


def gtin_pairs(offers: list[Offer]) -> tuple[list[Pair], int]:
    """Exact GTIN pairs across retailers; one offer per retailer and GTIN.

    Returns the pairs and the number of offers left out because their retailer
    lists the same GTIN more than once (the lowest variant id is kept).
    """
    by_gtin: dict[str, dict[str, tuple[str, int]]] = defaultdict(dict)
    dupes = 0
    for o in sorted(offers, key=lambda x: x.key):
        if not o.gtin14:
            continue
        slot = by_gtin[o.gtin14]
        if o.retailer_id in slot:
            dupes += 1
            continue
        slot[o.retailer_id] = o.key
    pairs: list[Pair] = []
    for members in by_gtin.values():
        keys = sorted(members.values())
        for i, a in enumerate(keys):
            for b in keys[i + 1 :]:
                pairs.append(Pair(a, b, "gtin", 1.0, "equal GTIN-14"))
    return pairs, dupes


@dataclass
class Thresholds:
    """Minimum score per tier for a pair to be compared; ``None`` = tier not used yet."""

    mpn: float | None = None
    fuzzy: float | None = None

    def get(self, tier: str) -> float | None:
        return {"gtin": 1.0, "mpn": self.mpn, "fuzzy": self.fuzzy}[tier]


@dataclass
class Product:
    key: str
    members: dict[str, tuple[str, int]]  # retailer id -> offer key
    tier: Tier
    confidence: float
    gtin14: str | None


@dataclass
class MatchResult:
    products: list[Product]
    accepted: list[Pair]
    possible: list[Pair]
    gtin_duplicates: int = 0
    conflicts: int = 0
    stats: dict[str, int] = field(default_factory=dict)


def accept(pair: Pair, thresholds: Thresholds, offers: Mapping[tuple[str, int], Offer]) -> bool:
    if pair.tier == "gtin":
        return True
    t = thresholds.get(pair.tier)
    if t is None or pair.score < t or pair.reason != "mutual best":
        return False
    ga, gb = offers[pair.a].gtin14, offers[pair.b].gtin14
    return not (ga and gb and ga != gb)


def product_key(gtin14: str | None, members: Iterable[tuple[str, int]]) -> str:
    """GTIN when known; otherwise a stable hash of the member offers."""
    if gtin14:
        return gtin14
    text = "|".join(f"{r}:{v}" for r, v in sorted(members))
    return "M" + hashlib.sha256(text.encode()).hexdigest()[:13]


def match(offers: list[Offer], thresholds: Thresholds) -> MatchResult:
    by_key = {o.key: o for o in offers}
    gpairs, dupes = gtin_pairs(offers)
    cands = candidate_pairs(offers)
    accepted = gpairs + [p for p in cands if accept(p, thresholds, by_key)]
    possible = [p for p in cands if not accept(p, thresholds, by_key)]
    # Union-find with "one offer per retailer": strongest links first.
    accepted.sort(key=lambda p: (TIER_RANK[p.tier], -p.score, p.ordered))
    parent: dict[tuple[str, int], tuple[str, int]] = {}
    members: dict[tuple[str, int], dict[str, tuple[str, int]]] = {}
    weakest: dict[tuple[str, int], tuple[int, float]] = {}

    def find(k: tuple[str, int]) -> tuple[str, int]:
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    used: list[Pair] = []
    conflicts = 0
    for p in accepted:
        ra, rb = find(p.a), find(p.b)
        if ra == rb:
            continue
        ma = members.get(ra, {p.a[0]: p.a})
        mb = members.get(rb, {p.b[0]: p.b})
        if ma.keys() & mb.keys():
            conflicts += 1
            continue
        gtins = {by_key[k].gtin14 for k in [*ma.values(), *mb.values()]} - {None}
        if len(gtins) > 1:
            conflicts += 1
            continue
        parent[rb] = ra
        members[ra] = {**ma, **mb}
        members.pop(rb, None)
        wa = weakest.get(ra, (0, -1.0))
        wb = weakest.get(rb, (0, -1.0))
        weakest[ra] = max(wa, wb, (TIER_RANK[p.tier], -p.score))
        weakest.pop(rb, None)
        used.append(p)
    tier_by_rank: dict[int, Tier] = {0: "gtin", 1: "mpn", 2: "fuzzy"}
    products: list[Product] = []
    for root, mem in members.items():
        rank, neg = weakest[root]
        found = sorted(g for k in mem.values() if (g := by_key[k].gtin14))
        gtin = found[0] if found else None
        products.append(
            Product(
                key=product_key(gtin, mem.values()),
                members=dict(sorted(mem.items())),
                tier=tier_by_rank[rank],
                confidence=round(-neg, 4),
                gtin14=gtin,
            )
        )
    products.sort(key=lambda p: p.key)
    stats: Counter[str] = Counter(p.tier for p in products)
    return MatchResult(
        products=products,
        accepted=used,
        possible=possible,
        gtin_duplicates=dupes,
        conflicts=conflicts,
        stats=dict(stats),
    )
