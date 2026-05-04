"""Canonicalize insurer names from PDF parses + user declarations.

Two-pass strategy:
  1. Substring match on INSURER_ALIASES (fast, deterministic).
  2. Fuzzy fallback via difflib.get_close_matches() against the canonical
     list with a strict 0.85 cutoff (catches "HDFC Errgo", "Niva Bupaa",
     etc. without matching unrelated insurers).

Returns "_UNKNOWN" when neither pass finds a hit. The router still stores
the raw string in insurer_name_raw so it's recoverable.
"""
from __future__ import annotations

from difflib import get_close_matches
from functools import lru_cache

from services.parser.canonical_vocabulary import (
    CANONICAL_INSURER_NAMES,
    INSURER_ALIASES,
    UNKNOWN_INSURER,
)

FUZZY_CUTOFF = 0.85


@lru_cache(maxsize=512)
def canonicalize_insurer(raw_name: str) -> str:
    """Return one of CANONICAL_INSURER_NAMES, or UNKNOWN_INSURER."""
    if not raw_name or not raw_name.strip():
        return UNKNOWN_INSURER

    needle = raw_name.lower()
    # Pass 1 — substring on aliases (longer aliases first so
    # "max bupa" beats a "bupa" matcher; we don't have one but safer).
    for alias in sorted(INSURER_ALIASES.keys(), key=len, reverse=True):
        if alias in needle:
            return INSURER_ALIASES[alias]

    # Pass 2 — fuzzy match on canonical list.
    matches = get_close_matches(
        raw_name,
        list(CANONICAL_INSURER_NAMES),
        n=1,
        cutoff=FUZZY_CUTOFF,
    )
    if matches:
        return matches[0]

    # Pass 2b — fuzzy on lowercase against lowercase canonicals (catches
    # casing differences that the case-sensitive get_close_matches misses).
    lc_to_canon = {c.lower(): c for c in CANONICAL_INSURER_NAMES}
    matches = get_close_matches(
        raw_name.lower(),
        list(lc_to_canon.keys()),
        n=1,
        cutoff=FUZZY_CUTOFF,
    )
    if matches:
        return lc_to_canon[matches[0]]

    return UNKNOWN_INSURER
