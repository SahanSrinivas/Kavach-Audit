"""Life gap score (0-100): missing protections and structural weaknesses."""

from __future__ import annotations

from services.life.audit.types import LifeScheduleInput, LifeScoreBreakdown, LifeUserProfile

# --- Core coverage thresholds ---
# Below 10x annual income is treated as underinsured in first-draft life rules.
MIN_INCOME_MULTIPLE_REQUIRED = 10.0
# Family protection should usually run till at least age 60.
MIN_COVER_END_AGE = 60

# --- Prompt-specified deductions ---
DEDUCTION_MISSING_CRITICAL_ILLNESS = 20
DEDUCTION_MISSING_ACCIDENTAL_DEATH = 15
DEDUCTION_TERM_ENDS_BEFORE_60 = 25
DEDUCTION_SUM_ASSURED_BELOW_10X = 20
DEDUCTION_NO_PERSONAL_ACCIDENT_ANYWHERE = 10
DEDUCTION_SINGLE_POLICY_WITH_DEPENDENTS = 10

# --- Rider keyword map ---
# Source list from prompt; keys are semantic rider types used in details.
SAFE_RIDER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "critical_illness": ("critical illness", "ci rider", "cancer", "cardiac"),
    "accidental_death": ("accidental death", "ad benefit", "adb"),
    "personal_accident": ("personal accident", "pa rider"),
    "disability": ("disability", "permanent disability"),
    "waiver_of_premium": ("waiver of premium", "wop"),
}

# Extractor-native normalized rider tags (from extract_schedule.py).
RIDER_TAG_ALIASES: dict[str, tuple[str, ...]] = {
    "critical_illness": ("critical_illness",),
    "accidental_death": ("accidental_death", "accidental_death_benefit", "adb"),
    "personal_accident": ("personal_accident",),
    "disability": ("disability", "permanent_disability"),
    "waiver_of_premium": ("waiver_of_premium", "wop"),
}


def _rider_tokens(schedule: LifeScheduleInput) -> tuple[str, ...]:
    return tuple(str(x).strip().lower() for x in schedule.detected_riders if str(x).strip())


def _has_rider(schedule: LifeScheduleInput, rider_type: str) -> bool:
    tokens = _rider_tokens(schedule)
    keywords = SAFE_RIDER_KEYWORDS.get(rider_type, ())
    tags = RIDER_TAG_ALIASES.get(rider_type, ())
    for token in tokens:
        if token in tags:
            return True
        if any(kw in token for kw in keywords):
            return True
    return False


def score(
    profile: LifeUserProfile,
    schedule: LifeScheduleInput,
    *,
    has_personal_accident_anywhere: bool | None = None,
    life_policy_count: int | None = None,
) -> LifeScoreBreakdown:
    """Compute gap score from life schedule + household context hints."""
    if profile.age <= 0:
        return LifeScoreBreakdown(value=None, label="gap", details={"reason": "missing_age"})
    if profile.annual_income <= 0:
        return LifeScoreBreakdown(
            value=None,
            label="gap",
            details={"reason": "missing_income"},
        )
    if schedule.sum_assured_inr is None:
        return LifeScoreBreakdown(
            value=None,
            label="gap",
            details={"reason": "missing_sum_assured"},
        )
    if schedule.policy_term_years is None:
        return LifeScoreBreakdown(
            value=None,
            label="gap",
            details={"reason": "missing_policy_term"},
        )

    deductions: list[dict[str, object]] = []
    total_deduction = 0

    # 1) Missing CI rider
    if not _has_rider(schedule, "critical_illness"):
        total_deduction += DEDUCTION_MISSING_CRITICAL_ILLNESS
        deductions.append(
            {
                "code": "missing_critical_illness",
                "deduction": DEDUCTION_MISSING_CRITICAL_ILLNESS,
            }
        )

    # 2) Missing accidental death cover
    if not _has_rider(schedule, "accidental_death"):
        total_deduction += DEDUCTION_MISSING_ACCIDENTAL_DEATH
        deductions.append(
            {
                "code": "missing_accidental_death",
                "deduction": DEDUCTION_MISSING_ACCIDENTAL_DEATH,
            }
        )

    # 3) Term ends before age 60
    cover_end_age = profile.age + int(schedule.policy_term_years)
    if cover_end_age < MIN_COVER_END_AGE:
        total_deduction += DEDUCTION_TERM_ENDS_BEFORE_60
        deductions.append(
            {
                "code": "term_too_short",
                "deduction": DEDUCTION_TERM_ENDS_BEFORE_60,
                "cover_end_age": cover_end_age,
            }
        )

    # 4) SA below 10x income
    income_multiple = schedule.sum_assured_inr / float(profile.annual_income)
    if income_multiple < MIN_INCOME_MULTIPLE_REQUIRED:
        total_deduction += DEDUCTION_SUM_ASSURED_BELOW_10X
        deductions.append(
            {
                "code": "underinsured_life",
                "deduction": DEDUCTION_SUM_ASSURED_BELOW_10X,
                "income_multiple": round(income_multiple, 2),
            }
        )

    # 5) No PA cover anywhere (if unknown, derive from life schedule riders)
    pa_anywhere = (
        has_personal_accident_anywhere
        if has_personal_accident_anywhere is not None
        else _has_rider(schedule, "personal_accident")
    )
    if not pa_anywhere:
        total_deduction += DEDUCTION_NO_PERSONAL_ACCIDENT_ANYWHERE
        deductions.append(
            {
                "code": "no_personal_accident_cover",
                "deduction": DEDUCTION_NO_PERSONAL_ACCIDENT_ANYWHERE,
            }
        )

    # 6) Single life policy with dependents
    policy_count = life_policy_count if life_policy_count is not None else 1
    if profile.dependents > 0 and policy_count <= 1:
        total_deduction += DEDUCTION_SINGLE_POLICY_WITH_DEPENDENTS
        deductions.append(
            {
                "code": "single_dependent_risk",
                "deduction": DEDUCTION_SINGLE_POLICY_WITH_DEPENDENTS,
                "dependents": profile.dependents,
                "life_policy_count": policy_count,
            }
        )

    value = max(0, 100 - total_deduction)
    return LifeScoreBreakdown(
        value=value,
        label="gap",
        details={
            "deductions": deductions,
            "total_deduction": total_deduction,
            "sum_assured_inr": schedule.sum_assured_inr,
            "annual_income_inr": profile.annual_income,
            "income_multiple": round(income_multiple, 2),
            "cover_end_age": cover_end_age,
            "pa_anywhere": bool(pa_anywhere),
            "life_policy_count": policy_count,
            "dependents": profile.dependents,
        },
    )
