"""Hardcoded mock fixtures — single source of truth for skeleton mode.

When USE_MOCKS=true (default in dev), routers return these fixtures.
When USE_MOCKS=false, routers should call real services (Claude API for parsing,
audit-engine, Riskcovry quotes, etc). All real-implementation hooks are marked
with TODO(...) comments at their consumers.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


# ---------- Stage 4 Path A — parsed PDF policy ----------
def make_mock_parsed_policy(user_id: str, raw_pdf_path: str = "") -> dict:
    """Returns a realistic HDFC ERGO Optima Restore parse result."""
    pid = str(uuid.uuid4())
    return {
        "id": pid,
        "user_id": user_id,
        "type": "health",
        "insurer": "HDFC ERGO General Insurance",
        "policy_name": "Optima Restore",
        "policy_number": "HE-OR-23-9087421",
        "sum_insured": 1500000,  # ₹15L
        "premium": 22400,
        "start_date": "2024-04-01",
        "end_date": "2025-03-31",
        "raw_pdf_path": raw_pdf_path,
        "parsed_fields": {
            "room_rent_cap": 5000,
            "icu_cap": 10000,
            "ambulance_cap": 2000,
            "copay_percent": 10,
            "ped_waiting_years": 3,
            "disease_specific_waiting": [
                {"disease": "cataract", "years": 2},
                {"disease": "hernia", "years": 2},
            ],
            "permanent_exclusions": [
                "cosmetic surgery",
                "hazardous sports",
                "self-inflicted injuries",
            ],
            "network_hospitals": 4500,
            "restoration_benefit": True,
            "ncb_percent": 25,
            "sub_limits": [
                {"type": "cataract", "cap": 100000},
                {"type": "knee_replacement", "cap": 200000},
                {"type": "maternity", "cap": 50000},
            ],
        },
        "created_at": _utcnow_iso(),
        "source": "upload",
    }


# ---------- Stage 6 — full audit fixture ----------
def make_mock_audit(
    user_id: str,
    *,
    policy_ids: list[str] | None = None,
) -> dict:
    """Return a realistic audit dict with the same shape as the real engine.

    `policy_ids`: optional list of the user's actual policy ids. When
    provided, the first id is stamped on findings that point at a
    specific policy (room rent cap, PED waiting). This lets the dashboard's
    per-policy chip and detail-view filtering work in dev under
    USE_MOCKS=true. When None, those findings get related_policy_id=None
    — keeps older callers / tests that don't seed policies working.

    Shape parity (kept in sync with services.audit.types.AuditResult):
      scores, findings, all_findings, portfolio, breakdowns,
      data_version, engine_ms, generated_at.
    """
    related_pid = policy_ids[0] if policy_ids else None

    findings = [
        {
            "id": "f1",
            "severity": "red",
            "type": "room_rent_cap",
            "icon": "alert-triangle",
            "headline": "Your health policy has a ₹5,000/day room rent cap. In Mumbai, that means 40-60% of your hospital bill won't be covered.",
            "explanation": "Most Tier-1 hospitals in Mumbai charge ₹12,000–₹18,000/day for a private room. When your policy caps room rent at ₹5,000, the insurer pays only that fraction of *every* bill line — surgery, doctor's fees, medicines — not just the room. This is called proportionate deduction and it's the single biggest reason genuine claims get reduced.",
            "action": "Switch to a policy with no room rent cap. We have 2 such options that cost only ~₹6,000 more per year.",
            "fix_target": "increase_health_cover",
            "related_policy_id": related_pid,
        },
        {
            "id": "f2",
            "severity": "red",
            "type": "term_life_gap",
            "icon": "shield-off",
            "headline": "You have no term life cover. With ₹15L of dependents and a ₹50K monthly EMI, your family needs at least ₹2Cr.",
            "explanation": "Term life is the cheapest insurance per rupee of cover. At your age (32, non-smoker), ₹2Cr cover costs roughly ₹14,000–₹18,000 per year. Without it, your family would lose 12–15 years of income if anything happens to you. This is the single most under-bought policy in India.",
            "action": "Add term life of ₹2Cr from a top-CSR insurer. Three options ranked by fit.",
            "fix_target": "buy_term_life",
            "related_policy_id": None,   # missing-policy finding, not tied to any existing row
        },
        {
            "id": "f3",
            "severity": "amber",
            "type": "ped_waiting",
            "icon": "clock",
            "headline": "3-year pre-existing disease waiting period. The market standard is now 2 years.",
            "explanation": "If you or a covered family member has any pre-existing condition (diabetes, BP, thyroid), your insurer won't pay claims related to it for the first 3 years. Newer policies have brought this down to 24 months — and a few to 12 months. You're locked out of treatment for an extra year.",
            "action": "Compare policies with 24-month PED waiting from your renewal date.",
            "fix_target": "shorten_ped_wait",
            "related_policy_id": related_pid,
        },
    ]

    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "scores": {
            "coverage": 62,
            "cost": 78,
            "claim_readiness": 41,
            "gap": 54,
        },
        "findings": findings,
        # Mock has no extras beyond top 3 — real engine returns the full
        # ranked list including amber/info findings the UI doesn't promote.
        "all_findings": findings,
        "breakdowns": {
            "coverage": {
                "value": 62,
                "label": "coverage",
                "details": {
                    "ideal_health_cover": 2500000,
                    "actual_health_cover": 1500000,
                    "shortfall_inr": 1000000,
                    "city_tier": "tier-1",
                },
            },
            "cost": {
                "value": 78,
                "label": "cost",
                "details": {
                    "actual_premium": 22400,
                    "market_band": [18000, 25000],
                    "verdict": "in band, slightly above median",
                },
            },
            "claim_readiness": {
                "value": 41,
                "label": "claim_readiness",
                "details": {
                    "red_flags": ["room_rent_cap", "ped_waiting_3y", "copay_10pct"],
                    "csr_score": 95.6,
                },
            },
            "gap": {
                "value": 54,
                "label": "gap",
                "details": {
                    "missing_categories": ["term", "pa"],
                    "underinsured_categories": ["health"],
                },
            },
        },
        "portfolio": {
            "total_cover": 1500000,
            "total_premium": 22400,
            "active_policies": 1,
            "next_renewal": "2025-03-31",
            "by_type": [
                {"type": "Health", "current": 1500000, "ideal": 2500000, "ratio": 60},
                {"type": "Term Life", "current": 0, "ideal": 20000000, "ratio": 0},
                {"type": "Personal Accident", "current": 0, "ideal": 15000000, "ratio": 0},
                {"type": "Motor", "current": 0, "ideal": 0, "ratio": 100},
                {"type": "Travel", "current": 0, "ideal": 0, "ratio": 100},
            ],
        },
        "data_version": "wordings-2026.04",
        "engine_ms": 12,   # mock doesn't actually run the engine; nominal value
        "generated_at": _utcnow_iso(),
    }


# ---------- Stage 7 — recommendation cards per finding ----------
def make_mock_recommendations(finding_id: str | None = None) -> list[dict]:
    base = [
        {
            "id": "rec_best",
            "category": "best_match",
            "label": "🎯 Best Match for You",
            "insurer": "Niva Bupa",
            "policy_name": "ReAssure 2.0",
            "sum_insured": 5000000,
            "premium": 28500,
            "features": [
                "No room rent cap",
                "10,000+ network hospitals",
                "100% restoration benefit (unlimited)",
                "1-day pre-existing waiting (with rider)",
            ],
            "csr": 95.6,
            "fit_reason": "Removes your biggest red flag (room rent cap) and matches Mumbai Tier-1 hospital pricing. Restoration benefit covers a second illness in the same year.",
            "our_commission": 1850,
            "direct_link": "https://www.nivabupa.com",
        },
        {
            "id": "rec_cheap",
            "category": "lowest_premium",
            "label": "💰 Lowest Premium",
            "insurer": "Star Health",
            "policy_name": "Comprehensive",
            "sum_insured": 5000000,
            "premium": 19200,
            "features": [
                "₹15,000/day room rent cap",
                "5,000+ network hospitals",
                "150% restoration",
            ],
            "csr": 89.9,
            "fit_reason": "₹9,300 cheaper per year. Room rent cap is high enough for most metros but not unlimited.",
            "our_commission": 920,
            "direct_link": "https://www.starhealth.in",
        },
        {
            "id": "rec_max",
            "category": "highest_coverage",
            "label": "🛡️ Highest Coverage",
            "insurer": "HDFC ERGO",
            "policy_name": "Optima Secure",
            "sum_insured": 10000000,
            "premium": 41800,
            "features": [
                "₹1Cr base cover",
                "No room rent cap",
                "Secure benefit doubles cover after 2 years",
                "International cover for emergency",
            ],
            "csr": 98.0,
            "fit_reason": "Highest cover for one-time critical illness. International emergency cover useful given your travel pattern.",
            "our_commission": 2900,
            "direct_link": "https://www.hdfcergo.com",
        },
    ]
    return base


# ---------- Stage 8 — alerts ----------
def make_mock_alerts(user_id: str) -> list[dict]:
    return [
        {
            "id": "alert_renewal",
            "user_id": user_id,
            "type": "renewal",
            "severity": "amber",
            "headline": "Renewal in 18 days — premium up 14%",
            "body": "Your HDFC ERGO Optima Restore renews on 31 Mar. The insurer has hiked your premium from ₹19,640 to ₹22,400. We found 2 cheaper alternatives with better room rent terms.",
            "cta_label": "See alternatives",
            "target_url": "/dashboard/policies",
            "short_token": "rnw18d",
            "read_status": False,
            "triggered_at": _future_iso(-2),
        },
        {
            "id": "alert_life_event",
            "user_id": user_id,
            "type": "life_event",
            "severity": "info",
            "headline": "Home loan added → your term cover should increase by ₹50L",
            "body": "We noticed you added a home loan to your profile. To keep your family debt-free if anything happens, your term life cover should grow proportionally.",
            "cta_label": "Update term cover",
            "target_url": "/recommendations?finding_id=f2",
            "short_token": "lifehl1",
            "read_status": False,
            "triggered_at": _future_iso(-7),
        },
        {
            "id": "alert_reaudit",
            "user_id": user_id,
            "type": "reaudit",
            "severity": "info",
            "headline": "Annual re-audit available — re-run in 30 seconds",
            "body": "It's been a year since your last Kavachly audit. Markets shifted — let's see what's changed.",
            "cta_label": "Re-run audit",
            "target_url": "/audit/identity",
            "short_token": "reaud1",
            "read_status": False,
            "triggered_at": _future_iso(-14),
        },
    ]


# ---------- Top 20 Indian health insurers (Stage 4 Path B autocomplete) ----------
INDIAN_HEALTH_INSURERS = [
    "HDFC ERGO General Insurance",
    "ICICI Lombard",
    "Star Health & Allied Insurance",
    "Niva Bupa (Max Bupa)",
    "Care Health Insurance",
    "Aditya Birla Health Insurance",
    "Bajaj Allianz General Insurance",
    "Tata AIG General Insurance",
    "New India Assurance",
    "United India Insurance",
    "National Insurance",
    "Oriental Insurance",
    "Manipal Cigna Health Insurance",
    "Future Generali India Insurance",
    "Reliance General Insurance",
    "Kotak General Insurance",
    "SBI General Insurance",
    "IFFCO Tokio General Insurance",
    "Cholamandalam MS",
    "Liberty General Insurance",
]

INDIAN_TERM_INSURERS = [
    "LIC of India",
    "HDFC Life",
    "ICICI Prudential Life",
    "Max Life Insurance",
    "Tata AIA Life",
    "SBI Life",
    "Bajaj Allianz Life",
    "Aditya Birla Sun Life",
    "Kotak Life",
    "PNB MetLife",
]
