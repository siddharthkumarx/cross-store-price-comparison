from __future__ import annotations

import pytest

from crossprice.gtin import check_digit_ok, gtin_problem, normalize_gtin


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("012345678905", "00012345678905"),  # UPC-A
        ("4006381333931", "04006381333931"),  # EAN-13
        (" 4006-381333931 ", "04006381333931"),
        ("10012345678902", "10012345678902"),  # GTIN-14, case indicator 1
        (12345678905, "00012345678905"),  # an int loses the leading zero but pads back
        ("96385074", "00000096385074"),  # EAN-8
    ],
)
def test_valid_gtins_normalise_to_gtin14(raw: object, expected: str) -> None:
    assert normalize_gtin(raw) == expected


@pytest.mark.parametrize(
    ("raw", "problem"),
    [
        (None, "empty"),
        ("", "empty"),
        ("ABC-123", "not digits"),
        ("12345", "5 digits"),
        ("012345678906", "bad check digit"),
        ("000000000000", "all zeros"),
        ("212345678909", "restricted prefix"),  # UPC number system 2: variable measure
        ("2001234567893", "restricted prefix"),  # in-store EAN
        ("9800000000007", "restricted prefix"),  # coupon range
    ],
)
def test_unusable_barcodes_are_rejected_with_a_reason(raw: object, problem: str) -> None:
    assert normalize_gtin(raw) is None
    assert gtin_problem(raw) == problem


def test_check_digit() -> None:
    assert check_digit_ok("4006381333931")
    assert not check_digit_ok("4006381333932")
    assert not check_digit_ok("x")
