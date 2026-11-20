from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from crossprice.match import (
    Thresholds,
    brand_key,
    candidate_pairs,
    match,
    sku_key,
    to_offer,
    tokens,
)
from crossprice.models import OfferRow
from crossprice.precision import choose_threshold, evaluate, manual_sample

T0 = datetime(2026, 11, 20, 7, 41, tzinfo=UTC)


def row(retailer: str, vid: int, title: str, **kw: Any) -> OfferRow:
    data: dict[str, Any] = {
        "retailer_id": retailer,
        "product_id": vid // 10 or 1,
        "variant_id": vid,
        "handle": title.lower().replace(" ", "-"),
        "brand": "Baratza",
        "product_type": "Grinder",
        "product_title": title,
        "variant_title": "Default Title",
        "options": (),
        "sku": "",
        "gtin14": None,
        "price_cents": 17000,
        "compare_at_cents": None,
        "availability": "in_stock",
        "observed_at": T0,
    }
    data.update(kw)
    return OfferRow.model_validate(data)


def test_brand_key_ignores_case_punctuation_and_legal_suffixes() -> None:
    assert brand_key("Baratza, Inc.") == brand_key("BARATZA") == "baratza"
    assert brand_key("Fellow Industries USA", {"fellowindustries": "fellow"}) == "fellow"
    assert brand_key("Café & Co") == "cafeand"


def test_tokens_join_numbers_and_units() -> None:
    assert tokens("Hario V60 Kettle 1.2 L") == ["hario", "v60", "kettle", "1", "2l"]
    assert "250ml" in tokens("Carafe 250 ml")


def test_sku_key_rejects_internal_or_gtin_skus() -> None:
    assert sku_key("ESP-120-BLK", 1) == "ESP120BLK"
    assert sku_key("abc", 1) is None
    assert sku_key("ABCD", 1) is None  # no digit
    assert sku_key("4006381333931", 1) is None  # a GTIN, not a part number
    assert sku_key("123456", 123456) is None  # the variant id itself


def test_gtin_pairs_are_exact_and_one_per_retailer() -> None:
    g = "04006381333931"
    rows = [
        row("a", 10, "Encore ESP", gtin14=g),
        row("b", 20, "Encore ESP Grinder", gtin14=g),
        row("c", 30, "Something else entirely", gtin14=g),
        row("c", 31, "Duplicate listing", gtin14=g),
    ]
    res = match([to_offer(r) for r in rows], Thresholds())
    assert len(res.products) == 1
    assert set(res.products[0].members) == {"a", "b", "c"}
    assert res.products[0].key == g
    assert res.gtin_duplicates == 1


def test_fuzzy_needs_numbers_and_options_to_agree() -> None:
    rows = [
        row("a", 10, "Encore ESP Coffee Grinder"),
        row("b", 20, "Baratza Encore ESP Grinder"),
        row("a", 11, "Sette 270Wi Grinder"),
        row("b", 21, "Sette 270 Grinder"),
        row("a", 12, "Virtuoso+ Grinder", options=("White",)),
        row("b", 22, "Virtuoso+ Grinder", options=("Black",)),
    ]
    pairs = {(p.a[1], p.b[1]): p for p in candidate_pairs([to_offer(r) for r in rows])}
    assert pairs[(10, 20)].score >= 0.6
    assert pairs[(10, 20)].reason == "mutual best"
    assert (11, 21) not in pairs  # 270wi vs 270: conflicting model numbers
    assert (12, 22) not in pairs  # white vs black


def test_fuzzy_rejects_far_apart_prices() -> None:
    rows = [row("a", 10, "Encore ESP"), row("b", 20, "Encore ESP", price_cents=50000)]
    assert candidate_pairs([to_offer(r) for r in rows]) == []


def test_mpn_tier_matches_brand_scoped_skus() -> None:
    rows = [
        row("a", 10, "Encore ESP Grinder", sku="1ZB-ESP-120"),
        row("b", 20, "Encore Espresso grinder (120V)", sku="1zb esp 120"),
    ]
    (pair,) = candidate_pairs([to_offer(r) for r in rows])
    assert pair.tier == "mpn"
    assert pair.score >= 0.85


def test_shared_sku_within_a_retailer_is_not_a_part_number() -> None:
    rows = [
        row("a", 10, "Encore ESP", sku="GRIND01"),
        row("a", 30, "Sette 30", sku="GRIND01"),
        row("b", 20, "Burr set", sku="GRIND01"),
    ]
    assert all(p.tier != "mpn" for p in candidate_pairs([to_offer(r) for r in rows]))


def test_thresholds_gate_what_is_compared_and_gtins_veto() -> None:
    rows = [
        row("a", 10, "Encore ESP Coffee Grinder", gtin14="00012345678905"),
        row("b", 20, "Baratza Encore ESP Grinder", gtin14="04006381333931"),
        row("a", 11, "Virtuoso Plus Grinder"),
        row("b", 21, "Virtuoso Plus Grinder"),
    ]
    offers = [to_offer(r) for r in rows]
    assert match(offers, Thresholds()).products == []  # no threshold yet: GTIN only
    res = match(offers, Thresholds(mpn=0.6, fuzzy=0.6))
    assert [sorted(p.members.values()) for p in res.products] == [[("a", 11), ("b", 21)]]
    assert res.products[0].tier == "fuzzy"
    assert res.products[0].key.startswith("M")
    assert any(p.a == ("a", 10) for p in res.possible)  # GTINs disagree: never compared


def test_one_offer_per_retailer_per_product() -> None:
    g = "04006381333931"
    rows = [
        row("a", 10, "Encore ESP", gtin14=g),
        row("b", 20, "Encore ESP", gtin14=g),
        row("b", 21, "Encore ESP"),
    ]
    res = match([to_offer(r) for r in rows], Thresholds(fuzzy=0.5, mpn=0.5))
    assert all(len(set(p.members)) == len(p.members) for p in res.products)
    assert len(res.products) == 1


def test_evaluation_scores_blind_pairs_against_gtins() -> None:
    g1, g2 = "04006381333931", "00012345678905"
    rows = [
        row("a", 10, "Encore ESP Grinder", gtin14=g1),
        row("b", 20, "Encore ESP Grinder", gtin14=g1),
        row("a", 11, "Virtuoso Plus", gtin14=g2),
        row("b", 21, "Virtuoso Plus", gtin14="00000096385074"),
    ]
    offers = [to_offer(r) for r in rows]
    ev = evaluate(offers, candidate_pairs(offers), Thresholds(fuzzy=0.5))
    fz = ev.tiers["fuzzy"]
    assert (fz.evaluated, fz.true_matches, fz.false_matches) == (2, 1, 1)
    assert fz.precision == 0.5
    assert ev.gtin_pairs == 1
    assert ev.combined_recall == 1.0


def test_threshold_needs_enough_cases_at_target_precision() -> None:
    good = [(0.9, True)] * 150
    assert choose_threshold(good, "fuzzy") == 0.9
    assert choose_threshold([(0.9, True)] * 50, "fuzzy") is None
    mixed = [(0.95, True)] * 120 + [(0.75, False)] * 10 + [(0.75, True)] * 10
    assert choose_threshold(mixed, "fuzzy") == 0.95


def test_manual_sample_prefers_non_gtin_pairs() -> None:
    from crossprice.match import Pair

    pairs = [Pair(("a", i), ("b", i), "gtin", 1.0, "x") for i in range(5)]
    pairs += [Pair(("a", 100 + i), ("b", 100 + i), "fuzzy", 0.9, "x") for i in range(3)]
    sample = manual_sample(pairs, n=4)
    assert [p.tier for p in sample[:3]] == ["fuzzy"] * 3
    assert sample == manual_sample(list(reversed(pairs)), n=4)
