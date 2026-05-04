"""Unit tests for backend/services/wordings.py.

Covers:
  - normalize_plan_name pure function (parametrized)
  - upsert_wording: insert / update / canonical validation
  - lookup_wording: exact / fuzzy / no-match / edge cases
  - update_qa_status: enum validation, attribution, missing-id
  - delete_wording, get_wording, list_wordings
"""
from __future__ import annotations

from typing import Any

import pytest

from services import wordings as w
from tests._fake_mongo import FakeDb


@pytest.fixture
def db() -> FakeDb:
    """Fresh fake db per test. Wordings collection unique-index on
    (insurer_canonical, plan_name_normalized) — wire it explicitly so
    upsert idempotency is correctly enforced in tests."""
    fake = FakeDb()
    fake.wordings.add_unique_index("insurer_canonical", "plan_name_normalized")
    return fake


def _sample_wording(
    insurer: str = "HDFC ERGO General",
    plan_name: str = "Optima Restore",
    **overrides: object,
) -> dict:
    """Realistic wording payload — what an admin parse would produce."""
    base = {
        "insurer_canonical": insurer,
        "plan_name": plan_name,
        "wording_uin": "HDFHLIP26055V102526",
        "wording_version": "Revision-2526",
        "source_url": "https://example.com/wording.pdf",
        "source_filename": "optima-restore-revision.pdf",
        "parser_version": "v0.4.2",
        "qa_status": "auto_parsed",
        "rules": {
            "room_rent_cap": None,
            "icu_cap": None,
            "copay_percent": 0,
            "permanent_exclusions": ["Cosmetic surgery", "War"],
            "permanent_exclusions_canonical": ["cosmetic", "war"],
            "ped_waiting_months": 24,
        },
        "available_sum_insured_lakhs": [3, 5, 10, 15, 20, 25, 50, 100],
        "add_ons": [],
    }
    base.update(overrides)
    return base


# ==========================================================================
# normalize_plan_name (pure function)
# ==========================================================================

@pytest.mark.parametrize("raw,expected", [
    ("Optima Restore",        "optimarestore"),
    ("ReAssure 2.0",          "reassure20"),
    ("Health Companion v2",   "healthcompanionv2"),
    ("  Star Comprehensive ", "starcomprehensive"),
    ("Click 2 Protect Super", "click2protectsuper"),
    ("iProtect-Smart",        "iprotectsmart"),
    ("Activ Health Platinum", "activhealthplatinum"),
    ("",                       ""),
    ("!!!@@@###",              ""),    # all-punctuation → empty
    ("123",                    "123"),  # numeric-only → numeric-only
    ("ABCxyz",                 "abcxyz"),
])
def test_normalize_plan_name(raw: str, expected: str) -> None:
    assert w.normalize_plan_name(raw) == expected


def test_normalize_plan_name_handles_none_safely() -> None:
    """Lenient signature — callers may pass Optional[str]."""
    assert w.normalize_plan_name(None) == ""  # type: ignore[arg-type]


# ==========================================================================
# upsert_wording — insert path
# ==========================================================================

@pytest.mark.asyncio
async def test_upsert_inserts_new_wording(db: FakeDb) -> None:
    wid = await w.upsert_wording(db, _sample_wording())
    assert wid  # non-empty UUID string
    rows = db.wordings.docs
    assert len(rows) == 1
    assert rows[0]["id"] == wid
    assert rows[0]["plan_name_normalized"] == "optimarestore"
    assert rows[0]["qa_status"] == "auto_parsed"
    assert "parsed_at" in rows[0]


@pytest.mark.asyncio
async def test_upsert_uses_supplied_id_if_present(db: FakeDb) -> None:
    """Caller can pre-assign id (rare, useful for migrations)."""
    payload = _sample_wording()
    payload["id"] = "preassigned-abc"
    wid = await w.upsert_wording(db, payload)
    assert wid == "preassigned-abc"


@pytest.mark.asyncio
async def test_upsert_validates_insurer_canonical(db: FakeDb) -> None:
    """Unknown insurer name must be rejected at write time — silent
    success here would let drift into prod and misroute lookups."""
    bad = _sample_wording(insurer="Made Up Insurance Co.")
    with pytest.raises(ValueError, match="not in CANONICAL_INSURER_NAMES"):
        await w.upsert_wording(db, bad)
    assert db.wordings.docs == []  # nothing stored


@pytest.mark.asyncio
async def test_upsert_validates_plan_name_present(db: FakeDb) -> None:
    bad = _sample_wording()
    bad["plan_name"] = ""
    with pytest.raises(ValueError, match="plan_name is required"):
        await w.upsert_wording(db, bad)


@pytest.mark.asyncio
async def test_upsert_validates_plan_name_normalizable(db: FakeDb) -> None:
    """'!!!' normalizes to empty — would clobber the index uniqueness."""
    bad = _sample_wording(plan_name="!!!")
    with pytest.raises(ValueError, match="normalized to empty"):
        await w.upsert_wording(db, bad)


# ==========================================================================
# upsert_wording — update path (idempotency)
# ==========================================================================

@pytest.mark.asyncio
async def test_upsert_updates_existing_wording_in_place(db: FakeDb) -> None:
    """Re-parsing the same plan REPLACES rules + qa_status but PRESERVES
    the original id (so policy.wording_id references stay stable)."""
    wid_first = await w.upsert_wording(db, _sample_wording(
        plan_name="Optima Restore",
    ))
    # Re-parse: same insurer + same normalized name, different rules
    payload = _sample_wording(plan_name="Optima Restore")
    payload["rules"]["copay_percent"] = 20  # changed
    payload["wording_version"] = "Revision-2627"
    wid_second = await w.upsert_wording(db, payload)
    assert wid_second == wid_first  # id preserved across re-parse
    assert len(db.wordings.docs) == 1   # still one row
    assert db.wordings.docs[0]["rules"]["copay_percent"] == 20
    assert db.wordings.docs[0]["wording_version"] == "Revision-2627"


@pytest.mark.asyncio
async def test_upsert_treats_normalized_name_as_match_key(db: FakeDb) -> None:
    """Different surface forms with the same normalized form are the
    same plan — so 'Optima Restore' and 'optima restore' update each
    other, not create two rows."""
    wid_first = await w.upsert_wording(db, _sample_wording(
        plan_name="Optima Restore",
    ))
    wid_second = await w.upsert_wording(db, _sample_wording(
        plan_name="OPTIMA RESTORE",
    ))
    assert wid_first == wid_second
    assert len(db.wordings.docs) == 1


@pytest.mark.asyncio
async def test_upsert_different_insurers_same_plan_name_distinct_rows(db: FakeDb) -> None:
    """A plan name can collide across insurers (e.g., 'Health Plus').
    Same normalized name + DIFFERENT insurer → distinct rows."""
    wid_a = await w.upsert_wording(db, _sample_wording(
        insurer="HDFC ERGO General", plan_name="Health Plus",
    ))
    wid_b = await w.upsert_wording(db, _sample_wording(
        insurer="ICICI Lombard", plan_name="Health Plus",
    ))
    assert wid_a != wid_b
    assert len(db.wordings.docs) == 2


# ==========================================================================
# lookup_wording — exact match path
# ==========================================================================

@pytest.mark.asyncio
async def test_lookup_returns_exact_match(db: FakeDb) -> None:
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore"))
    found = await w.lookup_wording(db, "HDFC ERGO General", "Optima Restore")
    assert found is not None
    assert found["plan_name"] == "Optima Restore"


@pytest.mark.asyncio
async def test_lookup_handles_case_and_punctuation_via_normalization(db: FakeDb) -> None:
    """'optima restore!' should hit the exact-match index because both
    sides normalize to 'optimarestore'."""
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore"))
    found = await w.lookup_wording(db, "HDFC ERGO General", "  optima restore!  ")
    assert found is not None
    assert found["plan_name"] == "Optima Restore"


# ==========================================================================
# lookup_wording — fuzzy fallback
# ==========================================================================

@pytest.mark.asyncio
async def test_lookup_containment_match_long_form_query(db: FakeDb) -> None:
    """Schedule's plan_name might come in as the long form ("Optima Restore
    Plan"), DB stores the short canonical ("Optima Restore") — containment
    match catches it. Length ratio 13/17 = 76% > CONTAINMENT_MIN_RATIO."""
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore"))
    found = await w.lookup_wording(
        db, "HDFC ERGO General", "Optima Restore Plan",
    )
    assert found is not None
    assert found["plan_name"] == "Optima Restore"


@pytest.mark.asyncio
async def test_lookup_containment_match_reverse_direction(db: FakeDb) -> None:
    """And the reverse: DB stored the long form, query is the short.
    Containment is symmetric (constrained by length ratio)."""
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore Plan"))
    found = await w.lookup_wording(
        db, "HDFC ERGO General", "Optima Restore",
    )
    assert found is not None


@pytest.mark.asyncio
async def test_lookup_containment_below_length_ratio_does_not_match(db: FakeDb) -> None:
    """Single-word stored name shouldn't false-match a longer query
    that happens to contain it. 'Companion' (9) ⊂ 'Health Companion
    Variant 2' (23) but 9/23 = 39% < 70% threshold → no match."""
    await w.upsert_wording(db, _sample_wording(plan_name="Companion"))
    found = await w.lookup_wording(
        db, "HDFC ERGO General", "Health Companion Variant 2",
    )
    assert found is None


@pytest.mark.asyncio
async def test_lookup_fuzzy_match_for_typo_level_drift(db: FakeDb) -> None:
    """Typo-level drift (single-letter difference) within difflib's
    0.85 cutoff. 'optimarestore' vs 'optimrestore' (drop one letter)."""
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore"))
    found = await w.lookup_wording(db, "HDFC ERGO General", "Optimrestore")
    assert found is not None
    assert found["plan_name"] == "Optima Restore"


@pytest.mark.asyncio
async def test_lookup_fuzzy_returns_none_when_no_close_match(db: FakeDb) -> None:
    """'Health Companion' should NOT match an entirely different plan
    in the same insurer — cutoff 0.85 protects against random hits."""
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore"))
    found = await w.lookup_wording(db, "HDFC ERGO General", "Health Companion")
    assert found is None


@pytest.mark.asyncio
async def test_lookup_fuzzy_picks_best_among_multiple_candidates(db: FakeDb) -> None:
    """Three plans in same insurer; query closest to one of them returns it."""
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore"))
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Secure"))
    await w.upsert_wording(db, _sample_wording(plan_name="Health Suraksha"))
    # Query closest to "Optima Restore"
    found = await w.lookup_wording(db, "HDFC ERGO General", "Optima Restore Plan")
    assert found is not None
    assert found["plan_name"] == "Optima Restore"


# ==========================================================================
# lookup_wording — defensive defaults
# ==========================================================================

@pytest.mark.asyncio
async def test_lookup_returns_none_for_unknown_insurer(db: FakeDb) -> None:
    await w.upsert_wording(db, _sample_wording())
    found = await w.lookup_wording(db, "Unknown Insurer", "Optima Restore")
    assert found is None


@pytest.mark.asyncio
async def test_lookup_returns_none_for_empty_inputs(db: FakeDb) -> None:
    await w.upsert_wording(db, _sample_wording())
    assert await w.lookup_wording(db, "", "Optima Restore") is None
    assert await w.lookup_wording(db, "HDFC ERGO General", "") is None
    assert await w.lookup_wording(db, "HDFC ERGO General", "!!!") is None


@pytest.mark.asyncio
async def test_lookup_returns_none_when_db_empty(db: FakeDb) -> None:
    found = await w.lookup_wording(db, "HDFC ERGO General", "Optima Restore")
    assert found is None


# ==========================================================================
# get_wording
# ==========================================================================

@pytest.mark.asyncio
async def test_get_wording_returns_doc_by_id(db: FakeDb) -> None:
    wid = await w.upsert_wording(db, _sample_wording())
    found = await w.get_wording(db, wid)
    assert found is not None
    assert found["id"] == wid


@pytest.mark.asyncio
async def test_get_wording_returns_none_for_missing(db: FakeDb) -> None:
    assert await w.get_wording(db, "nonexistent-id") is None
    assert await w.get_wording(db, "") is None


# ==========================================================================
# update_qa_status
# ==========================================================================

@pytest.mark.asyncio
async def test_update_qa_status_human_verified(db: FakeDb) -> None:
    wid = await w.upsert_wording(db, _sample_wording())
    ok = await w.update_qa_status(db, wid, "human_verified", admin_id="admin", notes="LGTM")
    assert ok is True
    doc = await w.get_wording(db, wid)
    assert doc is not None
    assert doc["qa_status"] == "human_verified"
    assert doc["qa_verified_by"] == "admin"
    assert doc["qa_notes"] == "LGTM"
    assert "qa_verified_at" in doc


@pytest.mark.asyncio
async def test_update_qa_status_needs_review_without_notes(db: FakeDb) -> None:
    wid = await w.upsert_wording(db, _sample_wording())
    ok = await w.update_qa_status(db, wid, "needs_review", admin_id="admin")
    assert ok is True
    doc = await w.get_wording(db, wid)
    assert doc is not None
    assert doc["qa_status"] == "needs_review"


@pytest.mark.asyncio
async def test_update_qa_status_rejects_invalid_status(db: FakeDb) -> None:
    wid = await w.upsert_wording(db, _sample_wording())
    with pytest.raises(ValueError, match="unknown qa_status"):
        await w.update_qa_status(db, wid, "garbage", admin_id="admin")


@pytest.mark.asyncio
async def test_update_qa_status_returns_false_for_unknown_id(db: FakeDb) -> None:
    ok = await w.update_qa_status(db, "nonexistent", "human_verified", admin_id="admin")
    assert ok is False


@pytest.mark.asyncio
async def test_update_qa_status_returns_false_for_empty_id(db: FakeDb) -> None:
    ok = await w.update_qa_status(db, "", "human_verified", admin_id="admin")
    assert ok is False


# ==========================================================================
# delete_wording
# ==========================================================================

@pytest.mark.asyncio
async def test_delete_wording_returns_true_on_match(db: FakeDb) -> None:
    wid = await w.upsert_wording(db, _sample_wording())
    deleted = await w.delete_wording(db, wid)
    assert deleted is True
    assert db.wordings.docs == []


@pytest.mark.asyncio
async def test_delete_wording_returns_false_on_no_match(db: FakeDb) -> None:
    deleted = await w.delete_wording(db, "nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_delete_wording_returns_false_for_empty_id(db: FakeDb) -> None:
    assert await w.delete_wording(db, "") is False


# ==========================================================================
# list_wordings
# ==========================================================================

@pytest.mark.asyncio
async def test_list_wordings_no_filters_returns_all(db: FakeDb) -> None:
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore"))
    await w.upsert_wording(db, _sample_wording(
        insurer="ICICI Lombard", plan_name="Complete Health",
    ))
    rows = await w.list_wordings(db)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_list_wordings_filter_by_insurer(db: FakeDb) -> None:
    await w.upsert_wording(db, _sample_wording(plan_name="Optima Restore"))
    await w.upsert_wording(db, _sample_wording(
        insurer="ICICI Lombard", plan_name="Complete Health",
    ))
    rows = await w.list_wordings(db, insurer_canonical="HDFC ERGO General")
    assert len(rows) == 1
    assert rows[0]["plan_name"] == "Optima Restore"


@pytest.mark.asyncio
async def test_list_wordings_filter_by_qa_status(db: FakeDb) -> None:
    wid_a = await w.upsert_wording(db, _sample_wording(plan_name="A"))
    await w.upsert_wording(db, _sample_wording(plan_name="B"))
    await w.update_qa_status(db, wid_a, "human_verified", admin_id="admin")
    rows = await w.list_wordings(db, qa_status="human_verified")
    assert len(rows) == 1
    assert rows[0]["plan_name"] == "A"


@pytest.mark.asyncio
async def test_list_wordings_combined_filters(db: FakeDb) -> None:
    wid_a = await w.upsert_wording(db, _sample_wording(plan_name="A"))
    await w.upsert_wording(db, _sample_wording(
        insurer="ICICI Lombard", plan_name="A",
    ))
    await w.update_qa_status(db, wid_a, "human_verified", admin_id="admin")
    rows = await w.list_wordings(
        db, insurer_canonical="HDFC ERGO General", qa_status="human_verified",
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_wordings_rejects_invalid_qa_status(db: FakeDb) -> None:
    with pytest.raises(ValueError, match="unknown qa_status"):
        await w.list_wordings(db, qa_status="garbage")


@pytest.mark.asyncio
async def test_list_wordings_sorted_by_parsed_at_desc(db: FakeDb) -> None:
    """Recent imports first — matches the index direction."""
    # Insert with explicit parsed_at to make order deterministic
    a = _sample_wording(plan_name="A"); a["parsed_at"] = "2026-05-01T10:00:00+00:00"
    b = _sample_wording(plan_name="B"); b["parsed_at"] = "2026-05-04T10:00:00+00:00"
    c = _sample_wording(plan_name="C"); c["parsed_at"] = "2026-05-02T10:00:00+00:00"
    await w.upsert_wording(db, a)
    await w.upsert_wording(db, b)
    await w.upsert_wording(db, c)
    rows = await w.list_wordings(db)
    plan_order = [r["plan_name"] for r in rows]
    assert plan_order == ["B", "C", "A"]  # newest first


# ==========================================================================
# Module-load assertions present
# ==========================================================================

def test_valid_qa_statuses_well_defined() -> None:
    """The enum is the source of truth for status validation. Drift here
    breaks update_qa_status + the admin endpoint at the same time."""
    assert w.VALID_QA_STATUSES == {"auto_parsed", "human_verified", "needs_review"}


def test_fuzzy_cutoff_matches_existing_canonicalizer_threshold() -> None:
    """Match the insurer canonicalizer's 0.85 cutoff so plan-name fuzzy
    behavior is consistent with insurer fuzzy behavior — single-letter
    typos pass; bigger drifts fall back to None."""
    from services.parser.insurer_canonicalizer import FUZZY_CUTOFF
    assert w.PLAN_NAME_FUZZY_CUTOFF == FUZZY_CUTOFF


# ==========================================================================
# compose_wording_doc — shape contract
# ==========================================================================
# Single source of truth for the wording shape. Used by both
# admin_router.py:wording_parse() and scripts/parse_wording.py --dry-run.
# Drift between the endpoint's stored shape and the CLI's preview shape
# would make the dry-run useless. These tests pin the shape.

def _fake_parsed_for_compose() -> Any:
    """Minimal ParsedPolicy stand-in for compose_wording_doc tests."""
    from services.parser.types import (
        ICUCap, ParseConfidence, ParsedFieldsRich, ParsedPolicy,
        RestorationBenefit, RoomRentCap,
    )
    return ParsedPolicy(
        insurer_name="HDFC ERGO General",
        insurer_name_raw="HDFC ERGO General Insurance",
        policy_type="health_family_floater",
        plan_name="Optima Restore",
        plan_name_raw="HDFC ERGO Optima Restore Family Floater",
        sum_insured=None, premium_annual=None,
        parsed_fields=ParsedFieldsRich(
            room_rent_cap=RoomRentCap(type="no_cap", value=None),
            icu_cap=ICUCap(type="no_cap", value=None),
            copay_percent=0,
            ped_waiting_months=24,
            permanent_exclusions=["Cosmetic surgery"],
            permanent_exclusions_canonical=["cosmetic"],
            restoration_benefit=RestorationBenefit(
                available=True, type="once_per_year", applies_to="different_illness",
            ),
        ),
        confidence=ParseConfidence(overall="high"),
    )


def test_compose_wording_doc_has_expected_top_level_keys() -> None:
    """The wording shape contract — every key the merger / admin UI / CLI
    will eventually read must be present. If a key is renamed or dropped,
    this fails immediately, before any consumer breaks."""
    parsed = _fake_parsed_for_compose()
    doc = w.compose_wording_doc(
        parsed,
        insurer_canonical="HDFC ERGO General",
        plan_name="Optima Restore",
        source_filename="optima.pdf",
    )
    expected_keys = {
        "insurer_canonical", "plan_name", "wording_uin", "wording_version",
        "source_url", "source_filename", "parser_version", "qa_status",
        "rules", "available_sum_insured_lakhs", "add_ons",
        "parser_insurer_extracted", "parser_plan_name_extracted",
        "parse_confidence",
    }
    assert set(doc.keys()) == expected_keys


def test_compose_wording_doc_passes_parser_output_into_rules() -> None:
    parsed = _fake_parsed_for_compose()
    doc = w.compose_wording_doc(
        parsed,
        insurer_canonical="HDFC ERGO General",
        plan_name="Optima Restore",
        source_filename="optima.pdf",
    )
    # Rules block matches the rich parsed_fields shape (not the flat
    # engine shape — the merger flattens later)
    assert doc["rules"]["ped_waiting_months"] == 24
    assert doc["rules"]["copay_percent"] == 0
    assert "Cosmetic surgery" in doc["rules"]["permanent_exclusions"]
    # Restoration is the nested rich shape, not the flat bool
    assert doc["rules"]["restoration_benefit"]["available"] is True
    assert doc["rules"]["restoration_benefit"]["type"] == "once_per_year"


def test_compose_wording_doc_passes_admin_metadata() -> None:
    parsed = _fake_parsed_for_compose()
    doc = w.compose_wording_doc(
        parsed,
        insurer_canonical="HDFC ERGO General",
        plan_name="Optima Restore",
        source_filename="optima-restore-revision.pdf",
        source_url="https://hdfcergo.com/wording.pdf",
        wording_uin="HDFHLIP26055V102526",
        wording_version="Revision-2526",
    )
    assert doc["insurer_canonical"] == "HDFC ERGO General"
    assert doc["plan_name"] == "Optima Restore"
    assert doc["source_filename"] == "optima-restore-revision.pdf"
    assert doc["source_url"] == "https://hdfcergo.com/wording.pdf"
    assert doc["wording_uin"] == "HDFHLIP26055V102526"
    assert doc["wording_version"] == "Revision-2526"


def test_compose_wording_doc_default_qa_status_is_auto_parsed() -> None:
    """New parses always start at auto_parsed, awaiting admin review.
    The composer NEVER produces a 'human_verified' wording — that
    state can only be reached via update_qa_status."""
    parsed = _fake_parsed_for_compose()
    doc = w.compose_wording_doc(
        parsed, insurer_canonical="HDFC ERGO General",
        plan_name="X", source_filename="x.pdf",
    )
    assert doc["qa_status"] == "auto_parsed"


def test_compose_wording_doc_default_forward_compat_fields_are_empty() -> None:
    parsed = _fake_parsed_for_compose()
    doc = w.compose_wording_doc(
        parsed, insurer_canonical="HDFC ERGO General",
        plan_name="X", source_filename="x.pdf",
    )
    assert doc["available_sum_insured_lakhs"] == []
    assert doc["add_ons"] == []


def test_compose_wording_doc_omits_top_level_schedule_fields() -> None:
    """Schedule-specific fields (sum_insured, premium_annual,
    policy_number, policy_start_date, etc.) belong on the user's policy,
    not on the wording. compose must NOT leak them into the wording doc.
    """
    parsed = _fake_parsed_for_compose()
    doc = w.compose_wording_doc(
        parsed, insurer_canonical="HDFC ERGO General",
        plan_name="X", source_filename="x.pdf",
    )
    assert "sum_insured" not in doc
    assert "premium_annual" not in doc
    assert "policy_number" not in doc
    assert "policy_start_date" not in doc
    assert "policy_end_date" not in doc
    assert "covered_members" not in doc
