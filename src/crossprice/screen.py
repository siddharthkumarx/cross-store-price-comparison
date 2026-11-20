"""Content screen: adult, tobacco/vape, alcohol, cannabis/CBD, weapons and medicines.

Reused from F1 with a medicines category added. Runs over the catalog fields
already in memory (title, product_type, tags; never descriptions) and returns,
per excluded category, up to three matching product titles as evidence.
Matching is on whole words, minus a short allow-list of harmless phrases
("wine glass"). A matching product is never collected; a retailer whose share of
matching products passes ``STORE_DROP_SHARE`` is dropped (docs/decisions.md D-007).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

EXCLUDED: dict[str, tuple[str, ...]] = {
    "adult": ("sex toy", "vibrator", "dildo", "adult toy", "erotic"),
    "tobacco/vape": ("vape", "vaping", "e-liquid", "nicotine", "tobacco", "cigar", "cigarette"),
    "alcohol": (
        "wine",
        "beer",
        "whiskey",
        "whisky",
        "bourbon",
        "vodka",
        "tequila",
        "mezcal",
        "gin",
        "rum",
        "liquor",
        "spirits",
        "hard seltzer",
    ),
    "cannabis/cbd": ("cbd", "thc", "cannabis", "hemp extract", "delta-8", "delta 8", "marijuana"),
    "weapons": (
        "firearm",
        "handgun",
        "rifle",
        "shotgun",
        "ammo",
        "ammunition",
        "holster",
        "pepper spray",
        "stun gun",
        "switchblade",
        "brass knuckles",
        "crossbow",
        "airsoft",
        "bb gun",
        "air rifle",
    ),
    "medicines": (
        "medicine",
        "medication",
        "prescription",
        "rx only",
        "otc drug",
        "pharmacy",
        "ibuprofen",
        "acetaminophen",
        "antibiotic",
        "dewormer",
        "heartworm",
        "flea and tick",
        "flea & tick",
    ),
}

# A retailer is dropped when more than this share of its products match the screen.
STORE_DROP_SHARE = 0.05

# Phrases that contain an excluded word but are not excluded products.
ALLOWED_PHRASES: tuple[str, ...] = (
    "wine glass",
    "wine glasses",
    "wine tumbler",
    "wine opener",
    "wine red",
    "rum raisin",
    "gin gingham",
    "beer koozie",
    "spirits up",
    "wine decanter",
    "wine aerator",
    "wine chiller",
    "wine rack",
    "beer glass",
    "beer glasses",
    "medicine cabinet",
    "medicine ball",
)

_PATTERNS = {
    cat: re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)
    for cat, words in EXCLUDED.items()
}


def _texts(product: dict[str, Any]) -> Iterable[str]:
    for key in ("title", "product_type"):
        value = product.get(key)
        if isinstance(value, str):
            yield value
    tags = product.get("tags")
    if isinstance(tags, list):
        yield from (t for t in tags if isinstance(t, str))
    elif isinstance(tags, str):
        yield tags


def _clean(text: str) -> str:
    lowered = text.lower()
    for phrase in ALLOWED_PHRASES:
        lowered = lowered.replace(phrase, " ")
    return lowered


def is_excluded(product: dict[str, Any], reviewed_titles: frozenset[str] = frozenset()) -> bool:
    """Whether one product matches any excluded category (and is not a reviewed title)."""
    if product.get("title") in reviewed_titles:
        return False
    text = " | ".join(_clean(t) for t in _texts(product))
    return any(pattern.search(text) for pattern in _PATTERNS.values())


def screen_content(
    products: list[dict[str, Any]],
    max_examples: int = 3,
    reviewed_titles: frozenset[str] = frozenset(),
) -> dict[str, list[str]]:
    """Excluded categories with at least one matching product, with example titles.

    ``reviewed_titles``: exact product titles a person reviewed as false positives
    (config/screen-review.yml); only those exact titles are skipped.
    """
    found: dict[str, list[str]] = {}
    for product in products:
        if product.get("title") in reviewed_titles:
            continue
        text = " | ".join(_clean(t) for t in _texts(product))
        for cat, pattern in _PATTERNS.items():
            if pattern.search(text):
                examples = found.setdefault(cat, [])
                if len(examples) < max_examples:
                    examples.append(str(product.get("title", "?"))[:80])
    return found
