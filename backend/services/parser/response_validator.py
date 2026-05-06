"""Validate Claude's JSON response, normalize fields, run sanity checks,
and produce the engine-facing flat shape.

Two-layer output (per Step 2 architecture):
  - parser_output (rich): a validated ParsedPolicy preserving Claude's
    nested structure verbatim.
  - parsed_fields (flat): produced by to_engine_shape() — matches the
    existing mock fixture's schema so the audit engine reads it unchanged.

Drift between to_engine_shape() and the engine's reads in
claim_readiness.py is the most likely silent breakage in this whole
session. Tests in test_to_engine_shape.py assert the exact mapping.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Mapping

from pydantic import ValidationError

from services.parser.canonical_vocabulary import EXCLUSION_PHRASE_MAP
from services.parser.insurer_canonicalizer import canonicalize_insurer
from services.parser.types import (
    FieldConfidenceUi,
    ParseConfidence,
    ParsedPolicy,
)


# Rows always emitted so the UI shows a stable checklist. Keys align with parser /
# Claude `fields_with_low_confidence` entries where possible.
#
# NOTE: Health pipeline confidence is binary today (flagged or not).
# Mapping to UI tiers honestly:
# - Flagged in fields_with_low_confidence → tier="low", score=None
# - Unflagged → tier="high", score=None
# No medium tier; we don't have the data granularity to support it.
# TODO(health-confidence-richer): Update Claude system prompt to return per-field
# confidence floats. Then health gets the same tier resolution as life.
_HEALTH_FIELD_UI_ROWS: tuple[tuple[str, str, bool], ...] = (
    ("sum_insured", "Sum Insured", True),
    ("premium_annual", "Annual Premium", True),
    ("policy_end_date", "Policy End Date", False),
    ("room_rent_cap", "Room Rent Cap", True),
    ("copay_percent", "Copay %", True),
    ("ped_waiting_months", "PED Waiting Period", True),
    ("insurer_name", "Insurer", False),
    ("plan_name", "Product Name", False),
    ("policy_number", "Policy Number", False),
)

# Alternate keys Claude occasionally emits — map to canonical row keys above.
_HEALTH_LOW_CONF_KEY_TO_CANONICAL: dict[str, str] = {
    "ped_waiting_period_months": "ped_waiting_months",
    "product_name": "plan_name",
}

_HEALTH_UI_CANONICAL_KEYS: frozenset[str] = frozenset(row[0] for row in _HEALTH_FIELD_UI_ROWS)


def _health_low_conflicts_canonical(canonical_key: str, low: frozenset[str]) -> bool:
    if canonical_key in low:
        return True
    for alt_key, canon in _HEALTH_LOW_CONF_KEY_TO_CANONICAL.items():
        if canon == canonical_key and alt_key in low:
            return True
    return False


def _health_low_key_covered_by_table(low_key: str) -> bool:
    if low_key in _HEALTH_UI_CANONICAL_KEYS:
        return True
    return low_key in _HEALTH_LOW_CONF_KEY_TO_CANONICAL


def _build_health_field_confidence_ui(low_confidence_fields: list[str]) -> list[FieldConfidenceUi]:
    """Binary tier rows for health — see module-level NOTE on ParsedPolicy."""

    low = frozenset(low_confidence_fields)
    out: list[FieldConfidenceUi] = []

    for field_key, label, numeric in _HEALTH_FIELD_UI_ROWS:
        is_low = _health_low_conflicts_canonical(field_key, low)
        tier = "low" if is_low else "high"
        out.append(
            FieldConfidenceUi(
                fieldKey=field_key,
                label=label,
                score=None,
                tier=tier,
                verifyInPdf=tier != "high",
                numericField=numeric,
            )
        )

    for lk in sorted(low):
        if not _health_low_key_covered_by_table(lk):
            out.append(
                FieldConfidenceUi(
                    fieldKey=lk,
                    label=lk,
                    score=None,
                    tier="low",
                    verifyInPdf=True,
                    numericField=False,
                )
            )

    return out

logger = logging.getLogger("kavach.parser")


class InvalidParseResponseError(Exception):
    """Claude returned malformed JSON or violated the schema."""


# ---------- Outer validate ----------

def validate_and_normalize(raw_response: Mapping[str, Any]) -> ParsedPolicy:
    """Coerce Claude's JSON into a ParsedPolicy. Run sanity checks and
    fold them into confidence.warnings. Re-canonicalize the insurer name
    server-side as a defense in depth (Claude may pick a non-canonical
    name despite the prompt rules).
    """
    if not isinstance(raw_response, Mapping):
        raise InvalidParseResponseError(f"expected JSON object, got {type(raw_response).__name__}")

    if "error" in raw_response:
        # Claude flagged the upload as not-a-policy / unreadable.
        raise InvalidParseResponseError(
            f"claude_returned_error:{raw_response.get('error')}"
        )

    try:
        coerced = _coerce_types(dict(raw_response))
        parsed = ParsedPolicy.model_validate(coerced)
    except ValidationError as e:
        raise InvalidParseResponseError(f"schema_validation:{e.error_count()}_errors") from e

    # Server-side canonicalization (defense in depth)
    canonical = canonicalize_insurer(parsed.insurer_name_raw or parsed.insurer_name)
    if canonical != parsed.insurer_name:
        parsed = parsed.model_copy(update={"insurer_name": canonical})

    # Sanity checks → fold into confidence.warnings
    warnings = list(parsed.confidence.warnings)
    low_conf_fields = list(parsed.confidence.fields_with_low_confidence)

    # Null sum_insured / premium_annual is acceptable for wording-only
    # documents (e.g., a policy brochure rather than a schedule). Warn so
    # the audit engine knows to short-circuit; do NOT coerce to 0 — that
    # would silently produce a "zero coverage" audit.
    if parsed.sum_insured is None:
        warnings.append(
            "sum_insured not found in document — likely a wording/brochure "
            "rather than a policy schedule. Audit engine will skip this policy."
        )
        low_conf_fields.append("sum_insured")
    elif parsed.sum_insured <= 0:
        warnings.append("sum_insured is zero or negative — policy data unusable")
        low_conf_fields.append("sum_insured")

    if parsed.premium_annual is None:
        warnings.append(
            "premium_annual not found in document — likely a wording/brochure "
            "rather than a policy schedule."
        )
        low_conf_fields.append("premium_annual")
    elif parsed.premium_annual <= 0:
        warnings.append("premium_annual is zero or negative")
        low_conf_fields.append("premium_annual")

    if (parsed.premium_annual is not None and parsed.sum_insured is not None
            and parsed.premium_annual > parsed.sum_insured > 0):
        warnings.append(
            f"premium ({parsed.premium_annual:,}) exceeds sum_insured "
            f"({parsed.sum_insured:,}) — likely OCR/extraction error"
        )
        low_conf_fields.append("premium_annual")
    if parsed.policy_start_date and parsed.policy_end_date:
        try:
            sd = date.fromisoformat(parsed.policy_start_date)
            ed = date.fromisoformat(parsed.policy_end_date)
            if ed <= sd:
                warnings.append(
                    f"policy_end_date ({parsed.policy_end_date}) is not after "
                    f"policy_start_date ({parsed.policy_start_date})"
                )
                low_conf_fields.append("policy_end_date")
        except ValueError:
            warnings.append("policy_start_date or policy_end_date not ISO-8601")
            low_conf_fields.append("policy_end_date")

    # ALWAYS overwrite permanent_exclusions_canonical from server-side
    # derivation. Claude was producing hallucinations (e.g., "mental_health"
    # with no matching verbatim entry) and missing legitimate surface forms
    # ("Sterility and Infertility" → infertility). The vocabulary +
    # phrase_map in canonical_vocabulary.py is the single source of truth.
    parsed.parsed_fields.permanent_exclusions_canonical[:] = canonicalize_exclusions(
        parsed.parsed_fields.permanent_exclusions
    )

    if warnings != parsed.confidence.warnings or low_conf_fields != parsed.confidence.fields_with_low_confidence:
        parsed = parsed.model_copy(update={
            "confidence": ParseConfidence(
                overall=parsed.confidence.overall,
                fields_with_low_confidence=sorted(set(low_conf_fields)),
                warnings=warnings,
            )
        })

    ui = _build_health_field_confidence_ui(parsed.confidence.fields_with_low_confidence)
    parsed = parsed.model_copy(update={"field_confidence_ui": ui})

    return parsed


def canonicalize_exclusions(verbatim: list[str]) -> list[str]:
    """Deterministic canonicalization of verbatim exclusion strings.

    Single source of truth — replaces both Claude's in-prompt
    canonicalization (was hallucinating) and any server-side fallback.
    The router calls this on every response; the result OVERWRITES any
    `permanent_exclusions_canonical` Claude may have returned.

    Algorithm:
      For each verbatim exclusion, scan EXCLUSION_PHRASE_MAP (longer
      phrases first so "self injury" beats a hypothetical "injury"
      bare-word matcher). Each verbatim string contributes AT MOST one
      canonical category — first match wins, dedupes preserved across
      the full input list. Phrases pre-padded with spaces (" bp ",
      " cva ") match at word boundaries to avoid false positives in
      common English words.
    """
    # Sort phrases longer-first so "self-injury" beats "self" (if added),
    # "intentional injury" beats "injury", etc. Stable across calls
    # because EXCLUSION_PHRASE_MAP keys are static.
    ordered_phrases = sorted(EXCLUSION_PHRASE_MAP.keys(), key=len, reverse=True)
    out: list[str] = []
    for exc in verbatim:
        if not isinstance(exc, str):
            continue
        padded = f" {exc.lower()} "
        for phrase in ordered_phrases:
            if phrase in padded:
                canon = EXCLUSION_PHRASE_MAP[phrase]
                if canon not in out:
                    out.append(canon)
                break
    return out


# ---------- Type coercion ----------

_LAKH_RE = re.compile(r"(?i)([\d,.]+)\s*(?:l|lakh|lakhs)\b")
_CR_RE = re.compile(r"(?i)([\d,.]+)\s*(?:cr|crore|crores)\b")


def _coerce_types(d: dict[str, Any]) -> dict[str, Any]:
    """Best-effort coercion before Pydantic validation.

    Claude is generally well-behaved at temperature=0 + the strict prompt,
    but it occasionally returns numeric strings. Coerce here so we don't
    fail on technically-correct-but-quoted integers.
    """
    # Null-preserving: pass None through so the schema sees nullable.
    # Coerce only non-null values (handles "Rs. 15 Lakhs" etc).
    if "sum_insured" in d and d["sum_insured"] is not None:
        d["sum_insured"] = _to_int_rupees(d["sum_insured"])
    if "premium_annual" in d and d["premium_annual"] is not None:
        d["premium_annual"] = _to_int_rupees(d["premium_annual"])

    pf = d.get("parsed_fields")
    if isinstance(pf, dict):
        for k in ("copay_percent", "ped_waiting_months", "initial_waiting_period_days",
                  "network_hospital_count", "ambulance_cap", "day_care_procedures_count"):
            if k in pf and pf[k] is not None and not isinstance(pf[k], int):
                pf[k] = _to_int_or_none(pf[k])
        # Nested {value: ...} coercions
        for nested_key in ("room_rent_cap", "icu_cap"):
            n = pf.get(nested_key)
            if isinstance(n, dict) and "value" in n and n["value"] is not None and not isinstance(n["value"], int):
                n["value"] = _to_int_or_none(n["value"])
        for sl in pf.get("sub_limits") or []:
            if isinstance(sl, dict):
                for k in ("limit_amount", "limit_percent_of_si"):
                    if k in sl and sl[k] is not None and not isinstance(sl[k], int):
                        sl[k] = _to_int_or_none(sl[k])

    return d


def _to_int_rupees(v: Any) -> int:
    """Accepts int, "150000", "1,50,000", "₹1,50,000", "15 Lakh", "1.5 Cr"."""
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if not isinstance(v, str):
        return 0
    s = v.strip().replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    cr = _CR_RE.search(s)
    if cr:
        return int(float(cr.group(1).replace(",", "")) * 10_000_000)
    lk = _LAKH_RE.search(s)
    if lk:
        return int(float(lk.group(1).replace(",", "")) * 100_000)
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else 0


def _to_int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        digits = re.sub(r"[^\d]", "", v)
        return int(digits) if digits else None
    return None


# ---------- Engine-facing flat shape adapter ----------

def to_engine_shape(parsed: ParsedPolicy) -> dict[str, Any]:
    """Map the rich ParsedPolicy to the flat dict the audit engine consumes.

    Engine-flat keys (must match what claim_readiness.py reads):
      room_rent_cap, icu_cap, ambulance_cap, copay_percent,
      ped_waiting_years, disease_specific_waiting,
      permanent_exclusions, permanent_exclusions_canonical,
      network_hospitals, restoration_benefit, restoration_unlimited,
      ncb_percent, sub_limits.

    This adapter is the joint between the parser (Claude output) and the
    engine (existing schema). Tests in test_to_engine_shape.py assert
    the exact mapping for every field — drift here corrupts every audit.
    """
    pf = parsed.parsed_fields
    # Use 0 as the SI fallback for percentage-of-SI calculations: the
    # leaf flatteners already short-circuit to None when SI <= 0, so a
    # null sum_insured (wording-only document) yields room_rent_cap=None
    # / icu_cap=None / sub_limit caps=0 → engine treats as "no rule fires".
    si_or_zero = parsed.sum_insured or 0
    flat: dict[str, Any] = {
        "room_rent_cap": _flatten_room_rent_cap(pf.room_rent_cap, si_or_zero),
        "icu_cap": _flatten_icu_cap(pf.icu_cap, si_or_zero),
        "ambulance_cap": pf.ambulance_cap,
        "copay_percent": pf.copay_percent,
        "ped_waiting_years": _months_to_years(pf.ped_waiting_months),
        "disease_specific_waiting": [
            {"disease": w.category, "years": _months_to_years_int(w.months)}
            for w in pf.specific_disease_waiting
        ],
        "permanent_exclusions": list(pf.permanent_exclusions),
        "permanent_exclusions_canonical": list(pf.permanent_exclusions_canonical),
        "network_hospitals": pf.network_hospital_count,
        "restoration_benefit": pf.restoration_benefit.available if pf.restoration_benefit else False,
        "restoration_unlimited": (
            pf.restoration_benefit.type == "unlimited"
            if pf.restoration_benefit else False
        ),
        "ncb_percent": pf.ncb_structure.max_percent if pf.ncb_structure else 0,
        "sub_limits": [
            _flatten_sublimit(sl, si_or_zero) for sl in pf.sub_limits
        ],
        # plan_name passes through for the wordings-DB lookup join key
        # (Phase 1.5). The audit engine itself doesn't read this field;
        # it's here so the merger and any downstream consumer can read
        # the plan name from a single place (parsed_fields) regardless
        # of whether they have the rich ParsedPolicy or just the flat dict.
        "plan_name": parsed.plan_name,
    }
    return flat


def _flatten_room_rent_cap(rrc: Any, sum_insured: int) -> int | None:
    """
    fixed_amount → that integer (rupees per day)
    percentage_of_si → SI × (basis_points / 10_000). value=100 means 1% → 1% × SI
    no_cap → 0  (engine reads 0 as the explicit "no cap" reward signal)
    single_private_room → None (no penalty fires; we don't have a meaningful
                                 numeric for single-room basis)
    None → None
    """
    if rrc is None:
        return None
    if rrc.type == "fixed_amount":
        return int(rrc.value or 0)
    if rrc.type == "percentage_of_si":
        bps = int(rrc.value or 0)
        return int(sum_insured * (bps / 10_000)) if sum_insured > 0 else None
    if rrc.type == "no_cap":
        return 0  # engine: 0 → "no cap" reward
    if rrc.type == "single_private_room":
        return None  # engine: None → rule skipped
    return None


def _flatten_icu_cap(icu: Any, sum_insured: int) -> int | None:
    if icu is None:
        return None
    if icu.type == "fixed_amount":
        return int(icu.value or 0)
    if icu.type == "percentage_of_si":
        bps = int(icu.value or 0)
        return int(sum_insured * (bps / 10_000)) if sum_insured > 0 else None
    if icu.type == "no_cap":
        return 0
    return None


def _flatten_sublimit(sl: Any, sum_insured: int) -> dict[str, Any]:
    """
    Engine reads {type, cap}. category → type. Prefer limit_amount; fall
    back to limit_percent_of_si × sum_insured (basis points → rupees).
    """
    cap: int = 0
    if sl.limit_amount is not None:
        cap = int(sl.limit_amount)
    elif sl.limit_percent_of_si is not None and sum_insured > 0:
        cap = int(sum_insured * (sl.limit_percent_of_si / 10_000))
    return {"type": sl.category, "cap": cap}


def _months_to_years(m: int | None) -> int | None:
    """Months → years, rounding down (engine asks for years; preserves
    the spec's '> 3 years' threshold semantics — 36 months = 3 years
    won't trigger the > 3 rule, which matches the spec author's intent)."""
    if m is None:
        return None
    return m // 12


def _months_to_years_int(m: int) -> int:
    return m // 12
