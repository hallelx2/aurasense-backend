"""
Allergy post-filter — deterministic safety check on food recommendations.

Why a separate module: **the LLM alone is not a safety filter.** It will
hallucinate, miss synonyms, ignore instructions under load, and
generally fail open. After the recommend node returns dishes, this
module runs a regex-based check against the user's allergens — anything
that matches is rejected, no exceptions, no LLM in the loop.

Public API:

* :func:`is_safe(text, allergens)` → bool. Returns True iff none of
  the allergen synonyms appear in ``text``.
* :func:`filter_recommendations(recs, allergens)` →
  ``(safe, rejected)`` tuple. Splits a list of recommendations into
  the kept set and the rejected set with reasons.

Synonym table is intentionally conservative — better a false positive
("chicken" rejected because the dish description says "chicken stock"
when the user is allergic to chicken eggs) than a real allergic
reaction. Operations folks can extend ``ALLERGEN_SYNONYMS`` as we
collect data.

Feature flag ``STRICT_ALLERGY_FILTER`` is checked at the call site
(food agent's record node). Default is ON.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Mapping

logger = logging.getLogger(__name__)


# Common allergens → synonym list (case-insensitive substring matches).
# Each canonical key matches itself plus the listed synonyms. Add more
# as we encounter false negatives in production data.
ALLERGEN_SYNONYMS: Mapping[str, tuple[str, ...]] = {
    "peanut": ("peanut", "peanuts", "groundnut", "groundnuts", "arachis"),
    "tree nut": (
        "almond",
        "almonds",
        "cashew",
        "cashews",
        "hazelnut",
        "hazelnuts",
        "walnut",
        "walnuts",
        "pecan",
        "pecans",
        "pistachio",
        "pistachios",
        "macadamia",
        "brazil nut",
    ),
    "shellfish": (
        "shrimp",
        "shrimps",
        "prawn",
        "prawns",
        "crab",
        "crabs",
        "lobster",
        "lobsters",
        "crayfish",
        "crawfish",
        "scallop",
        "scallops",
        "mussel",
        "mussels",
        "oyster",
        "oysters",
        "clam",
        "clams",
        "shellfish",
        "seafood",
    ),
    "fish": (
        "salmon",
        "tuna",
        "cod",
        "tilapia",
        "trout",
        "anchovy",
        "anchovies",
        "sardine",
        "sardines",
        "mackerel",
        "haddock",
        "halibut",
        "fish",
    ),
    "egg": ("egg", "eggs", "albumen", "ovalbumin", "mayonnaise", "mayo"),
    "milk": (
        "milk",
        "dairy",
        "cream",
        "cheese",
        "butter",
        "yogurt",
        "yoghurt",
        "lactose",
        "whey",
        "casein",
        "ghee",
    ),
    "wheat": (
        "wheat",
        "flour",
        "bread",
        "pasta",
        "noodle",
        "noodles",
        "couscous",
        "semolina",
    ),
    "gluten": (
        "wheat",
        "barley",
        "rye",
        "spelt",
        "kamut",
        "triticale",
        "flour",
        "bread",
        "pasta",
        "couscous",
        "soy sauce",
    ),
    "soy": ("soy", "soya", "soybean", "soybeans", "tofu", "edamame", "miso", "tempeh"),
    "sesame": ("sesame", "tahini"),
    "mustard": ("mustard",),
}


# Reverse synonym map — any token (canonical OR synonym) maps to the
# full equivalence class. Built once at module load so a user-input
# allergen like "dairy" finds the same set of triggers as "milk".
def _build_reverse_synonyms() -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {}
    for canonical, syns in ALLERGEN_SYNONYMS.items():
        equivalence = {canonical, *syns}
        for token in equivalence:
            reverse.setdefault(token.lower(), set()).update(equivalence)
    return reverse


_REVERSE_SYNONYMS: dict[str, set[str]] = _build_reverse_synonyms()


def _allergen_pattern(allergen: str) -> re.Pattern[str]:
    """Build a case-insensitive whole-word regex for an allergen + its synonyms.

    Looks up the user's allergen (or its singular form) in the reverse
    map so "dairy", "milk", and "cheese" all expand to the same set.
    Falls back to a literal match for unknown words.
    """
    key = allergen.strip().lower()

    # Strip trailing 's' so "peanuts" still finds the "peanut" class.
    candidates = {key}
    if key.endswith("s") and len(key) > 1:
        candidates.add(key[:-1])

    synonyms: set[str] = set()
    for c in candidates:
        synonyms.update(_REVERSE_SYNONYMS.get(c, set()))
    if not synonyms:
        synonyms = {key}
    # Always include the user's exact word (defensive).
    synonyms.add(key)

    # Build a single alternation regex with word boundaries so "almond"
    # doesn't match "almondian" but DOES match "almond milk".
    escaped = sorted({re.escape(s) for s in synonyms if s}, key=len, reverse=True)
    if not escaped:
        escaped = [re.escape(key)]
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


def is_safe(text: str, allergens: Iterable[str]) -> bool:
    """Return True iff ``text`` contains none of the allergen synonyms."""
    if not text or not allergens:
        return True
    for allergen in allergens:
        if not isinstance(allergen, str) or not allergen.strip():
            continue
        if _allergen_pattern(allergen).search(text):
            return False
    return True


def matched_allergens(text: str, allergens: Iterable[str]) -> list[str]:
    """Return the list of allergens whose patterns match ``text``."""
    if not text or not allergens:
        return []
    matches: list[str] = []
    for allergen in allergens:
        if not isinstance(allergen, str) or not allergen.strip():
            continue
        if _allergen_pattern(allergen).search(text):
            matches.append(allergen)
    return matches


def filter_recommendations(
    recs: Iterable[Mapping[str, object]],
    allergens: Iterable[str],
) -> tuple[list[dict], list[dict]]:
    """Split recommendations into (safe, rejected) by allergen check.

    Each recommendation dict is expected to have at least:
      - ``name``: the dish or restaurant name.
      - ``description``: any free-text description.
      - ``ingredients``: optional list of ingredient strings.

    Rejected entries gain a ``rejection_reason`` field listing the
    triggering allergens, so callers can audit / surface why an item
    was filtered.
    """
    allergen_list = [a for a in allergens if isinstance(a, str) and a.strip()]
    if not allergen_list:
        return list(recs), []

    safe: list[dict] = []
    rejected: list[dict] = []
    for rec in recs:
        rec_dict = dict(rec)
        text = " ".join(
            str(rec_dict.get(field, "") or "")
            for field in ("name", "description")
        )
        ingredients = rec_dict.get("ingredients") or []
        if isinstance(ingredients, (list, tuple)):
            text = text + " " + " ".join(str(i) for i in ingredients)

        hits = matched_allergens(text, allergen_list)
        if hits:
            rec_dict["rejection_reason"] = f"contains allergen(s): {', '.join(hits)}"
            rejected.append(rec_dict)
        else:
            safe.append(rec_dict)

    if rejected:
        logger.info(
            "allergy_filter: rejected %d/%d recs against allergens=%s",
            len(rejected),
            len(rejected) + len(safe),
            allergen_list,
        )
    return safe, rejected
