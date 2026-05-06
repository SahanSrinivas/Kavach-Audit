"""Pydantic v2 models for the PDF parser.

The parser produces TWO shapes:
  - parser_output (rich, nested): ParsedPolicy below — preserved verbatim
    on the policy document for "show your work" UX and future analytics.
  - parsed_fields (flat, engine-compatible): produced by
    response_validator.to_engine_shape() — this is what the audit engine
    reads. Engine-facing keys match the existing mock fixture exactly.

Why Pydantic instead of dataclasses (the rest of the codebase uses
dataclasses): Pydantic gives us free JSON-schema validation + tolerant
type coercion (Claude sometimes returns "5000" as a string), which is
critical for an LLM boundary. The audit engine stays on dataclasses
because it's pure-CPU on trusted Python objects.

Null tolerance (post-smoke-test fix):
The schema accepts both
    "room_rent_cap": null                                  ← preferred shape
    "room_rent_cap": {"type": null, "value": null, ...}    ← also accepted
because Claude legitimately returns either pattern when a clause is
absent from the policy document. Leaf enum fields are typed as
Optional[Literal[...]]; bool/int fields with semantic defaults use
BeforeValidator coercion so explicit JSON `null` becomes the safe
default the audit engine expects (False / 0 / "none").
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


# ---------- Type aliases ----------

RoomRentCapType = Literal["fixed_amount", "percentage_of_si", "no_cap", "single_private_room"]
ICUCapType = Literal["fixed_amount", "percentage_of_si", "no_cap"]
CopayApplyTo = Literal["all_claims", "senior_citizens_only", "specific_diseases", "none"]
RestorationType = Literal["once_per_year", "unlimited", "none"]
RestorationApplyTo = Literal["same_illness", "different_illness", "both"]
PolicyType = Literal[
    "health_individual", "health_family_floater", "health_senior",
    "term_life", "endowment", "ulip",
    "motor_private_car", "motor_two_wheeler",
    "personal_accident", "travel_international", "travel_domestic",
    "home", "critical_illness", "super_topup",
]
PremiumFrequency = Literal["annual", "semi_annual", "quarterly", "monthly"]
ConfidenceLevel = Literal["high", "medium", "low"]
Relationship = Literal["self", "spouse", "son", "daughter", "father", "mother", "other"]
Gender = Literal["male", "female", "other"]


# ---------- BeforeValidator coercers: explicit-null → safe default ----------
# Used where the downstream consumer (audit engine) expects a concrete
# bool/int/str rather than None. Keeps the rich storage shape coherent
# while letting Claude emit `null` for absent fields.

def _none_to_false(v: Any) -> Any:
    return False if v is None else v


def _none_to_zero(v: Any) -> Any:
    return 0 if v is None else v


def _none_to_empty_str(v: Any) -> Any:
    return "" if v is None else v


NullableBool = Annotated[bool, BeforeValidator(_none_to_false)]
NullableInt = Annotated[int, BeforeValidator(_none_to_zero)]
NullableStr = Annotated[str, BeforeValidator(_none_to_empty_str)]


# ---------- Sub-models for parser_output (nested rich shape) ----------

class RoomRentCap(BaseModel):
    """Null-tolerant on every leaf so partial Claude responses still validate."""
    model_config = ConfigDict(extra="ignore")
    type: Optional[RoomRentCapType] = None
    value: Optional[int] = None  # rupees if fixed_amount; basis-points if pct (100 = 1%)
    raw_text: NullableStr = ""


class ICUCap(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Optional[ICUCapType] = None
    value: Optional[int] = None
    raw_text: NullableStr = ""


class RestorationBenefit(BaseModel):
    """`available` is the engine-facing leaf (claim_readiness reads
    `restoration_benefit` flat bool). Coerce JSON null → False so the
    engine's `restoration is False` check fires correctly."""
    model_config = ConfigDict(extra="ignore")
    available: NullableBool = False
    type: Optional[RestorationType] = None
    applies_to: Optional[RestorationApplyTo] = None


class NCBStructure(BaseModel):
    model_config = ConfigDict(extra="ignore")
    max_percent: NullableInt = 0
    increment_per_year: NullableInt = 0


class SubLimit(BaseModel):
    """Sub-limit entries with a null `category` are dropped at the
    ParsedFieldsRich level (see _filter_sublimits below) — a sub-limit
    without a category is unusable for the audit engine's per-disease
    rules. Other leaves stay null-tolerant."""
    model_config = ConfigDict(extra="ignore")
    category: str
    limit_amount: Optional[int] = None
    limit_percent_of_si: Optional[int] = None  # basis points (100 = 1%)
    raw_text: NullableStr = ""


class CoveredMember(BaseModel):
    """Members with a null `relationship` are dropped (see
    _filter_covered_members) — without relationship we can't attribute
    the cover to the right household member."""
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    relationship: Relationship
    age: Optional[int] = None
    gender: Optional[Gender] = None


class SpecificDiseaseWaiting(BaseModel):
    """Rich shape Claude returns: array of {category, months}. Entries
    missing either field are dropped at the parent level."""
    model_config = ConfigDict(extra="ignore")
    category: str
    months: int


def _get(item: Any, key: str) -> Any:
    """Read `key` from either a dict or an already-instantiated Pydantic
    model. Filters run before per-item validation, so on the deserialize
    path items are dicts; but unit tests construct ParsedFieldsRich
    directly with model instances, which we must also accept."""
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _filter_sublimits(v: Any) -> Any:
    """Drop entries without a category — they're unusable downstream."""
    if not isinstance(v, list):
        return v
    return [item for item in v if _get(item, "category")]


def _filter_specific_disease_waiting(v: Any) -> Any:
    if not isinstance(v, list):
        return v
    return [item for item in v
            if _get(item, "category") and _get(item, "months") is not None]


def _filter_covered_members(v: Any) -> Any:
    if not isinstance(v, list):
        return v
    return [item for item in v if _get(item, "relationship")]


class ParsedFieldsRich(BaseModel):
    """The nested clause data from the policy document. Preserved on the
    policy doc as `parser_output`. The engine reads `parsed_fields`
    (flat) which is derived from this via to_engine_shape().
    """
    model_config = ConfigDict(extra="ignore")
    room_rent_cap: Optional[RoomRentCap] = None
    icu_cap: Optional[ICUCap] = None
    copay_percent: NullableInt = 0
    copay_applies_to: Optional[CopayApplyTo] = None
    ped_waiting_months: Optional[int] = None
    specific_disease_waiting: list[SpecificDiseaseWaiting] = Field(default_factory=list)
    initial_waiting_period_days: Optional[int] = None
    permanent_exclusions: list[str] = Field(default_factory=list)
    # NOTE: permanent_exclusions_canonical is NOT extracted by Claude (was
    # producing hallucinations + missing surface forms). Always derived
    # server-side in response_validator.canonicalize_exclusions() from the
    # verbatim list. Stored on the rich output for downstream display.
    permanent_exclusions_canonical: list[str] = Field(default_factory=list)
    network_hospital_count: Optional[int] = None
    restoration_benefit: Optional[RestorationBenefit] = None
    ncb_structure: Optional[NCBStructure] = None
    sub_limits: list[SubLimit] = Field(default_factory=list)
    ambulance_cap: Optional[int] = None
    day_care_procedures_count: Optional[int] = None

    # Drop unusable entries before per-item validation runs.
    _v_sublimits = field_validator("sub_limits", mode="before")(_filter_sublimits)
    _v_disease_wait = field_validator("specific_disease_waiting", mode="before")(_filter_specific_disease_waiting)

    @field_validator("permanent_exclusions", mode="before")
    @classmethod
    def _drop_null_strings(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v
        return [s for s in v if isinstance(s, str) and s.strip()]


class ParseConfidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    overall: ConfidenceLevel = "medium"
    fields_with_low_confidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("overall", mode="before")
    @classmethod
    def _coerce_overall(cls, v: Any) -> Any:
        return "medium" if v is None else v


class FieldConfidenceUi(BaseModel):
    """Per-field badge row for health parser_output (and parity with life extract UI).

    ``score`` is optional: health uses ``None`` with binary high/low tiers only; life
    passes numeric scores when available.
    """
    model_config = ConfigDict(extra="ignore")
    fieldKey: str
    label: str
    score: Optional[float] = None
    tier: ConfidenceLevel
    verifyInPdf: bool
    numericField: bool


class ParsedPolicy(BaseModel):
    """Full rich output from a successful parse. Stored as `parser_output`
    on the policy doc. The router also writes a flattened `parsed_fields`
    derived from this for the audit engine — see to_engine_shape().
    """
    model_config = ConfigDict(extra="ignore")
    insurer_name: str                       # canonical (or "_UNKNOWN")
    insurer_name_raw: str
    policy_type: PolicyType
    policy_number: Optional[str] = None
    # Marketing/product name printed on the schedule cover page.
    # plan_name = canonical short form ("Optima Restore", "ReAssure 2.0")
    # plan_name_raw = verbatim ("HDFC ERGO Optima Restore Family Floater Plan")
    # Both nullable: wording-only docs without a clear title get None.
    # Used as the join key for wordings DB lookup (Phase 1.5).
    plan_name: Optional[str] = None
    plan_name_raw: Optional[str] = None
    # sum_insured / premium_annual are nullable to honor Claude's correct
    # behavior of returning null for wording-only documents (no schedule).
    # The audit engine handles None by skipping the policy from coverage
    # + cost scoring rather than treating it as zero coverage.
    sum_insured: Optional[int] = None
    premium_annual: Optional[int] = None
    premium_frequency: PremiumFrequency = "annual"
    policy_start_date: Optional[str] = None
    policy_end_date: Optional[str] = None
    covered_members: list[CoveredMember] = Field(default_factory=list)
    is_employer_group: NullableBool = False
    parsed_fields: ParsedFieldsRich = Field(default_factory=ParsedFieldsRich)
    confidence: ParseConfidence = Field(default_factory=ParseConfidence)
    field_confidence_ui: list[FieldConfidenceUi] = Field(default_factory=list)

    _v_members = field_validator("covered_members", mode="before")(_filter_covered_members)

    @field_validator("premium_frequency", mode="before")
    @classmethod
    def _coerce_premium_frequency(cls, v: Any) -> Any:
        return "annual" if v is None else v

    @field_validator("parsed_fields", mode="before")
    @classmethod
    def _coerce_parsed_fields(cls, v: Any) -> Any:
        # Claude occasionally emits `"parsed_fields": null` for completely
        # uninspected sections (e.g., a renewal certificate with no clauses).
        # Default to an empty ParsedFieldsRich rather than rejecting.
        return {} if v is None else v

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> Any:
        return {} if v is None else v


# ---------- Engine-facing flat shape (matches existing mock) ----------
# This is a plain TypedDict-ish dict produced by to_engine_shape(). We
# don't model it as a Pydantic class because the engine reads it as a
# raw Mapping[str, Any] (see services/audit/types.py Policy.parsed_fields).
# Documented here so the contract is greppable.
#
# Engine-flat shape:
#     {
#         "room_rent_cap": int | None,        # rupees per day; 0 = no cap reward
#         "icu_cap": int | None,
#         "ambulance_cap": int | None,
#         "copay_percent": int,
#         "ped_waiting_years": int | None,    # YEARS, not months
#         "disease_specific_waiting": [{"disease": str, "years": int}],
#         "permanent_exclusions": [str, ...],         # verbatim
#         "permanent_exclusions_canonical": [str, ...],  # canonical
#         "network_hospitals": int | None,
#         "restoration_benefit": bool,
#         "restoration_unlimited": bool,
#         "ncb_percent": int,
#         "sub_limits": [{"type": str, "cap": int}],
#     }
