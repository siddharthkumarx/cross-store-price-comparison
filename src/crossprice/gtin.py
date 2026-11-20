"""GTIN handling: normalise every barcode to GTIN-14 and reject what cannot identify a product.

A GTIN (UPC-A = GTIN-12, EAN-13 = GTIN-13, EAN-8 = GTIN-8, GTIN-14) identifies one
trade item worldwide, so two retailers selling the same GTIN sell the same item.
Shopify stores keep it in the variant ``barcode`` field (product ``.js``) and some
themes repeat it in JSON-LD (``gtin``, ``gtin12``, ``gtin13``...).

Rules (docs/decisions.md D-008):

* digits only after stripping spaces and dashes; 8, 12, 13 or 14 digits;
  left-padded with zeros to 14;
* the GS1 check digit must be right;
* restricted-circulation numbers are not product identifiers across stores and
  are rejected: GTIN-13 prefixes 020-029, 040-049 and 200-299 (in-store and
  variable-measure numbers; a UPC-A starting with 2 or 4 lands here) and
  980-999 (coupons, refund receipts), and GTIN-14 indicator 9 (variable measure);
* an all-zero body is rejected.
"""

from __future__ import annotations

import re

_NON_DIGIT = re.compile(r"[\s\-]")


def check_digit_ok(digits: str) -> bool:
    """GS1 mod-10 check over a digit string whose last digit is the check digit."""
    if not digits.isdigit() or len(digits) < 2:
        return False
    body, check = digits[:-1], int(digits[-1])
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10 == check


def restricted(gtin14: str) -> bool:
    """Restricted-circulation or coupon numbers (not usable across stores)."""
    if gtin14.startswith("000000"):
        # GTIN-8 padded: its own prefix rules; 0 and 2 prefixes are restricted.
        return gtin14[6] in "02"
    gtin13 = gtin14[1:]
    if gtin14[0] == "9":
        return True  # variable-measure trade item
    if gtin14[0] != "0":
        return False  # a packaging-level GTIN-14 (indicator 1-8) is a real trade item
    prefix3 = int(gtin13[:3])
    return 20 <= prefix3 <= 29 or 40 <= prefix3 <= 49 or 200 <= prefix3 <= 299 or prefix3 >= 980


def normalize_gtin(raw: object) -> str | None:
    """Return the GTIN-14 for ``raw``, or ``None`` when it is not a usable GTIN."""
    if raw is None or isinstance(raw, bool):
        return None
    text = _NON_DIGIT.sub("", str(raw).strip())
    if isinstance(raw, int):
        text = text.zfill(12)  # a JSON number loses a UPC-A's leading zeros
    if not text.isdigit() or len(text) not in (8, 12, 13, 14):
        return None
    gtin14 = text.zfill(14)
    if set(gtin14[:-1]) == {"0"} or not check_digit_ok(gtin14):
        return None
    if restricted(gtin14):
        return None
    return gtin14


def gtin_problem(raw: object) -> str:
    """A short label for why ``raw`` was not accepted (for recon and run evidence)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "empty"
    text = _NON_DIGIT.sub("", str(raw).strip())
    if not text.isdigit():
        return "not digits"
    if len(text) not in (8, 12, 13, 14):
        return f"{len(text)} digits"
    gtin14 = text.zfill(14)
    if set(gtin14[:-1]) == {"0"}:
        return "all zeros"
    if not check_digit_ok(gtin14):
        return "bad check digit"
    if restricted(gtin14):
        return "restricted prefix"
    return "ok"
