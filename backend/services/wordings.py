"""Wordings database — pre-parsed policy-rule documents.

Phase 1.5 strategy: when a user uploads only a schedule (1-2 page
personalized doc with sum_insured + premium), the merger looks up the
plan's wording rules from this DB instead of asking the user for the
50-page wording. Lookup key: (insurer_canonical, plan_name_normalized).

This module owns the read/write path. Admin endpoints in admin_router.py
expose CRUD; the merger (Phase 1.5+) will call lookup_wording().

Design decisions (locked in docs/WORDINGS_DESIGN_NOTES.md):
  1. difflib for fuzzy plan-name matching (no rapidfuzz dep).
  2. plan_name extracted by parser as the join key (v0.4.2).
  3. SI tier mismatch logs warning, doesn't block the merge.

Module-load assertions catch typos at import time, before any request
hits production.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from difflib import get_close_matches
from typing import Any, Final, Optional

from services.parser.canonical_vocabulary import CANONICAL_INSURER_NAMES

logger = logging.getLogger("kavach.wordings")


# QA workflow states. New parses start at "auto_parsed"; admin reviews
# and either promotes to "human_verified" or flags "needs_review" for
# re-parse / manual correction.
VALID_QA_STATUSES: Final[frozenset[str]] = frozenset({
    "auto_parsed",
    "human_verified",
    "needs_review",
})

# Fuzzy-match cutoff for plan_name lookup. Same threshold as the
# insurer canonicalizer — single-letter typos pass; bigger drifts
# fall back to UNKNOWN/None rather than mismatching.
PLAN_NAME_FUZZY_CUTOFF: Final[float] = 0.85

# Cap on candidates fetched for fuzzy fallback. A single insurer rarely
# offers more than 20 plans; 100 is generous headroom.
FUZZY_CANDIDATES_LIMIT: Final[int] = 100

# Containment pre-check: when one normalized string is a substring of
# the other (e.g., "optimarestore" ⊂ "optimarestoreplan"), accept the
# match if the shorter string is at least this fraction of the longer
# string's length. Below this threshold, single-word plan names
# ("Companion") would falsely match longer ones ("Health Companion") —
# 0.70 is the conservative compromise that catches realistic
# long-form-vs-short-form drift without false positives.
CONTAINMENT_MIN_RATIO: Final[float] = 0.70


# ==========================================================================
# Module-load sanity checks
# ==========================================================================

assert len(CANONICAL_INSURER_NAMES) > 0, (
    "CANONICAL_INSURER_NAMES is empty — wordings.upsert_wording will reject "
    "every insert. Check services/parser/canonical_vocabulary.py."
)
assert len(VALID_QA_STATUSES) >= 3, "QA status enum unexpectedly small"


# ==========================================================================
# Pure helpers
# ==========================================================================

_PLAN_NAME_NORMALIZE_RE = re.compile(r"[^a-z0-9]")


def normalize_plan_name(plan_name: str) -> str:
    """Normalize a plan name for indexing + fuzzy lookup.

    Lowercase + strip every non-alphanumeric character. So:
      "Optima Restore"        → "optimarestore"
      "ReAssure 2.0"          → "reassure20"
      "Health Companion v2"   → "healthcompanionv2"
      "  Star Comprehensive " → "starcomprehensive"
      ""                      → ""
      None                    → ""  (lenient: callers may pass Optional)

    Used at write time (stored as plan_name_normalized for the unique
    compound index) and at read time (lookup_wording normalizes the
    incoming plan_name before querying).
    """
    if not plan_name:
        return ""
    return _PLAN_NAME_NORMALIZE_RE.sub("", plan_name.lower())


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==========================================================================
# Read path
# ==========================================================================

async def lookup_wording(
    db: Any,
    insurer_canonical: str,
    plan_name: str,
) -> Optional[dict[str, Any]]:
    """Find a wording by canonical insurer + fuzzy plan-name match.

    Strategy:
      1. Fast path — exact match against the unique compound index
         (insurer_canonical, plan_name_normalized).
      2. Slow path — fetch all wordings for that insurer (small list,
         single-insurer rarely > 20 plans) and run difflib fuzzy match
         on plan_name_normalized with cutoff PLAN_NAME_FUZZY_CUTOFF.

    Returns the wording document or None. Default-safe: if any of the
    inputs are None/empty/garbage, returns None without raising. The
    merger (Phase 1.5+) treats None as "no wording lookup; merge
    skipped" — never blocks the audit flow.
    """
    if not insurer_canonical or not plan_name:
        return None
    normalized = normalize_plan_name(plan_name)
    if not normalized:
        return None

    # Fast path: exact normalized-name match on the index
    exact = await db.wordings.find_one(
        {
            "insurer_canonical": insurer_canonical,
            "plan_name_normalized": normalized,
        },
        {"_id": 0},
    )
    if exact is not None:
        _warn_if_canonical_drifted(exact)
        logger.info(
            "wordings.lookup_hit insurer=%s plan_normalized=%s match=exact",
            insurer_canonical, normalized,
        )
        return dict(exact)

    # Fetch candidates for the slow paths
    candidates_cursor = db.wordings.find(
        {"insurer_canonical": insurer_canonical}, {"_id": 0},
    )
    candidates = await candidates_cursor.to_list(FUZZY_CANDIDATES_LIMIT)
    if not candidates:
        logger.info(
            "wordings.lookup_miss insurer=%s plan_normalized=%s reason=no_candidates",
            insurer_canonical, normalized,
        )
        return None

    # Slow path 1: containment match. Catches the common "Claude
    # extracted the long form, DB has the short form" case (e.g.,
    # query "optimarestoreplan" contains stored "optimarestore"), and
    # the reverse. CONTAINMENT_MIN_RATIO guards against single-word
    # false matches like "companion" → "healthcompanion".
    for c in candidates:
        stored_norm = c.get("plan_name_normalized", "")
        if not stored_norm:
            continue
        if stored_norm == normalized:
            continue  # already handled by exact path; skip duplicate work
        shorter, longer = (stored_norm, normalized) if len(stored_norm) < len(normalized) else (normalized, stored_norm)
        if shorter not in longer:
            continue
        if (len(shorter) / len(longer)) < CONTAINMENT_MIN_RATIO:
            continue
        _warn_if_canonical_drifted(c)
        logger.info(
            "wordings.lookup_hit insurer=%s plan_normalized=%s "
            "match=containment matched_to=%s",
            insurer_canonical, normalized, stored_norm,
        )
        return dict(c)

    # Slow path 2: difflib fuzzy match for typo-level drift
    candidate_names = [c.get("plan_name_normalized", "") for c in candidates]
    matches = get_close_matches(
        normalized, candidate_names,
        n=1, cutoff=PLAN_NAME_FUZZY_CUTOFF,
    )
    if not matches:
        logger.info(
            "wordings.lookup_miss insurer=%s plan_normalized=%s "
            "reason=no_fuzzy_match candidates=%d",
            insurer_canonical, normalized, len(candidates),
        )
        return None

    matched_name = matches[0]
    for c in candidates:
        if c.get("plan_name_normalized") == matched_name:
            _warn_if_canonical_drifted(c)
            logger.info(
                "wordings.lookup_hit insurer=%s plan_normalized=%s "
                "match=fuzzy matched_to=%s",
                insurer_canonical, normalized, matched_name,
            )
            return dict(c)
    return None  # unreachable; satisfies mypy


async def list_wordings(
    db: Any,
    insurer_canonical: Optional[str] = None,
    qa_status: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List wordings, optionally filtered. Sorted by parsed_at desc
    (most recent first) — matches the index direction for cheap reads."""
    query: dict[str, Any] = {}
    if insurer_canonical:
        query["insurer_canonical"] = insurer_canonical
    if qa_status:
        if qa_status not in VALID_QA_STATUSES:
            raise ValueError(
                f"unknown qa_status: {qa_status!r}; "
                f"expected one of {sorted(VALID_QA_STATUSES)}"
            )
        query["qa_status"] = qa_status
    cursor = db.wordings.find(query, {"_id": 0})
    cursor = cursor.sort("parsed_at", -1)
    rows = await cursor.to_list(500)
    return list(rows)


async def get_wording(db: Any, wording_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single wording by its business id (UUID string).
    Returns None if not found."""
    if not wording_id:
        return None
    doc = await db.wordings.find_one({"id": wording_id}, {"_id": 0})
    return dict(doc) if doc else None


def _warn_if_canonical_drifted(wording: dict[str, Any]) -> None:
    """Defensive read-time check: log a warning if a stored wording's
    insurer_canonical is no longer in the canonical list (someone manually
    edited the DB, or a future canonical removal stranded data). Don't
    fail — the merger's defensive default still produces a usable result.
    """
    insurer = wording.get("insurer_canonical")
    if insurer and insurer not in CANONICAL_INSURER_NAMES:
        logger.warning(
            "wordings.canonical_drift wording_id=%s stale_insurer=%r",
            wording.get("id"), insurer,
        )


# ==========================================================================
# Write path
# ==========================================================================

def compose_wording_doc(
    parsed: Any,    # services.parser.types.ParsedPolicy — typed Any to avoid
                    # a parser→wordings import cycle (parser doesn't depend
                    # on wordings; wordings is the consumer here).
    *,
    insurer_canonical: str,
    plan_name: str,
    source_filename: str,
    source_url: Optional[str] = None,
    wording_uin: Optional[str] = None,
    wording_version: Optional[str] = None,
    parser_version: str = "v0.4.2",
) -> dict[str, Any]:
    """Compose a wording document from parser output + admin metadata.

    Single source of truth for the wording shape — used by both:
      - POST /api/admin/wordings/parse (the endpoint)
      - scripts/parse_wording.py --dry-run (the CLI preview)

    Top-level schedule fields (sum_insured, premium_annual) are
    intentionally NOT stored — they belong to a specific user's schedule,
    not the wording. The rich `parsed_fields` becomes the `rules` block
    that the future merger reads back to inject into the user's parse.
    """
    return {
        "insurer_canonical": insurer_canonical,
        "plan_name": plan_name,
        "wording_uin": wording_uin,
        "wording_version": wording_version,
        "source_url": source_url,
        "source_filename": source_filename,
        "parser_version": parser_version,
        "qa_status": "auto_parsed",
        "rules": parsed.parsed_fields.model_dump(),
        # Forward-compat: parser doesn't extract these today; admin can
        # populate via PATCH later or we add prompt rules in a future pass.
        "available_sum_insured_lakhs": [],
        "add_ons": [],
        # Cross-reference to what the parser saw — debugging aid for
        # admin review. If insurer_canonical disagrees with parser's
        # extraction, we still trust the admin (logged at WARNING).
        "parser_insurer_extracted": parsed.insurer_name,
        "parser_plan_name_extracted": parsed.plan_name,
        "parse_confidence": parsed.confidence.model_dump(),
    }


async def upsert_wording(db: Any, wording_data: dict[str, Any]) -> str:
    """Insert or update a wording. Returns the business id (UUID string).

    Idempotent on the unique (insurer_canonical, plan_name_normalized)
    pair — a re-parse of the same plan REPLACES the rules block, the qa
    metadata, and parsed_at, but PRESERVES the original `id` so external
    references (future policy.wording_id) stay stable across re-parses.

    Validates insurer_canonical against CANONICAL_INSURER_NAMES at write
    time. Wordings for unknown insurers cannot enter the DB through this
    path.
    """
    insurer = wording_data.get("insurer_canonical")
    plan_name = wording_data.get("plan_name")
    if insurer not in CANONICAL_INSURER_NAMES:
        raise ValueError(
            f"insurer_canonical {insurer!r} is not in CANONICAL_INSURER_NAMES — "
            f"cannot upsert. Add the insurer to canonical_vocabulary.py first."
        )
    if not plan_name or not isinstance(plan_name, str):
        raise ValueError("wording_data.plan_name is required and must be a non-empty string")

    normalized = normalize_plan_name(plan_name)
    if not normalized:
        raise ValueError(
            f"plan_name {plan_name!r} normalized to empty string — "
            f"need at least one alphanumeric character"
        )

    # Compose the doc to store. Caller-supplied fields take precedence;
    # we just ensure the index key + metadata defaults are present.
    doc = dict(wording_data)
    doc["plan_name_normalized"] = normalized

    existing = await db.wordings.find_one(
        {"insurer_canonical": insurer, "plan_name_normalized": normalized},
        {"_id": 0},
    )
    if existing is not None:
        # Update path — preserve id and original parsed_at history could
        # be added later; today we just stamp the new parse time.
        doc["id"] = existing["id"]
        doc.setdefault("parsed_at", _utcnow_iso())
        await db.wordings.update_one(
            {"id": existing["id"]},
            {"$set": doc},
        )
        logger.info(
            "wordings.upsert_updated id=%s insurer=%s plan_normalized=%s",
            existing["id"], insurer, normalized,
        )
        return str(existing["id"])

    # Insert path
    doc["id"] = doc.get("id") or str(uuid.uuid4())
    doc.setdefault("parsed_at", _utcnow_iso())
    doc.setdefault("qa_status", "auto_parsed")
    await db.wordings.insert_one(doc)
    logger.info(
        "wordings.upsert_inserted id=%s insurer=%s plan_normalized=%s",
        doc["id"], insurer, normalized,
    )
    return str(doc["id"])


async def update_qa_status(
    db: Any,
    wording_id: str,
    status: str,
    admin_id: str,
    notes: Optional[str] = None,
) -> bool:
    """Update qa_status + timestamp + admin attribution. Returns True
    if a row was updated; False if the wording_id doesn't exist."""
    if status not in VALID_QA_STATUSES:
        raise ValueError(
            f"unknown qa_status: {status!r}; "
            f"expected one of {sorted(VALID_QA_STATUSES)}"
        )
    if not wording_id:
        return False
    update: dict[str, Any] = {
        "qa_status": status,
        "qa_verified_at": _utcnow_iso(),
        "qa_verified_by": admin_id,
    }
    if notes is not None:
        update["qa_notes"] = notes
    res = await db.wordings.update_one(
        {"id": wording_id},
        {"$set": update},
    )
    matched = bool(getattr(res, "matched_count", 0))
    logger.info(
        "wordings.qa_update id=%s status=%s admin=%s matched=%s",
        wording_id, status, admin_id, matched,
    )
    return matched


async def delete_wording(db: Any, wording_id: str) -> bool:
    """Remove a wording (admin-only operation, exposed via DELETE
    endpoint). Returns True if a row was deleted, False if not found."""
    if not wording_id:
        return False
    res = await db.wordings.delete_one({"id": wording_id})
    deleted = bool(getattr(res, "deleted_count", 0))
    logger.info("wordings.deleted id=%s found=%s", wording_id, deleted)
    return deleted
