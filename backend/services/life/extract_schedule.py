"""Heuristic extraction of a Life Schedule from CIS + policy bond plain text.

No LLM: deterministic regex / keyword windows suitable for CI and offline dev.
Confidence scores are per-field hints for UI (0–1).
"""

from __future__ import annotations

import re
from typing import Any


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_inr_amount(raw: str) -> int | None:
    """Parse Indian-style amounts like 1,00,00,000 or 10000000."""
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _first_amount_in_line(line: str) -> int | None:
    m = re.search(
        r"(?:Rs\.?|₹|INR)\s*([\d,]+)|([\d,]+)\s*(?:Rs\.?|₹)?",
        line,
        re.IGNORECASE,
    )
    if not m:
        return None
    grp = m.group(1) or m.group(2)
    return _parse_inr_amount(grp or "")


def _scan_keyword_amount(text: str, keywords: tuple[str, ...]) -> tuple[int | None, float]:
    """Return (amount, confidence) after first line mentioning a keyword."""
    lines = text.splitlines()
    for line in lines:
        low = line.lower()
        if any(k.lower() in low for k in keywords):
            amt = _first_amount_in_line(line)
            if amt is not None:
                return amt, 0.75
            # amount may be on same line after colon split
            if ":" in line:
                tail = line.split(":", 1)[1]
                amt = _first_amount_in_line(tail) or _parse_inr_amount(tail)
                if amt is not None:
                    return amt, 0.65
    return None, 0.0


def _scan_years(text: str, keywords: tuple[str, ...]) -> tuple[int | None, float]:
    lines = text.splitlines()
    for line in lines:
        low = line.lower()
        if any(k.lower() in low for k in keywords):
            m = re.search(r"(\d{1,2})\s*(?:years?|yrs?\.?)", low)
            if m:
                return int(m.group(1)), 0.7
            m2 = re.search(r"\b(\d{1,2})\b", line)
            if m2 and "year" in low:
                return int(m2.group(1)), 0.45
    return None, 0.0


def _guess_product_name(text: str) -> tuple[str | None, float]:
    for pat in (
        r"(?:Plan\s+Name|Name\s+of\s+(?:the\s+)?Plan|Product\s+Name)\s*[:]\s*([^\n]+)",
        r"(?:UIN|Plan)\s*[:#]\s*([A-Za-z0-9\-]+)",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = _normalize_whitespace(m.group(1))
            if len(name) > 2:
                return name[:120], 0.55
    return None, 0.0


def _detect_nominee(text: str) -> bool:
    low = text.lower()
    return "nominee" in low or "nomination" in low


def _detect_free_look(text: str) -> tuple[int | None, float]:
    m = re.search(
        r"free\s*look\s*(?:period)?\s*[:.]?\s*(\d{1,2})\s*days?",
        text,
        re.IGNORECASE,
    )
    if m:
        return int(m.group(1)), 0.6
    return None, 0.0


def extract_life_schedule(
    cis_text: str,
    bond_text: str,
    insurer_id: str | None = None,
) -> dict[str, Any]:
    merged_raw = f"{cis_text or ''}\n---\n{bond_text or ''}"
    merged = merged_raw
    low = merged.lower()

    sa, c_sa = _scan_keyword_amount(
        merged,
        (
            "sum assured",
            "basic sum assured",
            "basic sum",
            "death benefit",
            "life cover",
        ),
    )
    if sa is None:
        # fallback: largest rupee-looking amount in doc (often SA on CIS)
        amounts: list[int] = []
        for m in re.finditer(r"(?:Rs\.?|₹)\s*([\d,]+)", merged):
            v = _parse_inr_amount(m.group(1))
            if v and v >= 50_000:
                amounts.append(v)
        if amounts:
            sa = max(amounts)
            c_sa = 0.35

    ppt, c_ppt = _scan_years(merged, ("premium paying term", "ppt", "paying term"))
    pt, c_pt = _scan_years(merged, ("policy term", "term of policy", "coverage term"))

    prem, c_prem = _scan_keyword_amount(
        merged,
        (
            "modal premium",
            "installment premium",
            "premium payable",
            "annual premium",
            "yearly premium",
        ),
    )

    freq = None
    c_freq = 0.0
    if re.search(r"monthly", low):
        freq, c_freq = "Monthly", 0.4
    elif re.search(r"quarterly", low):
        freq, c_freq = "Quarterly", 0.4
    elif re.search(r"half\s*yearly|semi[\s-]?annual", low):
        freq, c_freq = "Half-yearly", 0.4
    elif re.search(r"annual|yearly", low):
        freq, c_freq = "Annual", 0.35

    plan, c_plan = _guess_product_name(merged)
    fl, c_fl = _detect_free_look(merged)
    nominee = _detect_nominee(merged)
    c_nominee = 0.58 if nominee else 0.22

    schedule: dict[str, Any] = {
        "schemaVersion": 1,
        "productName": plan,
        "sumAssuredInr": sa,
        "policyTermYears": pt,
        "premiumPaymentTermYears": ppt,
        "modalPremiumInr": prem,
        "premiumFrequency": freq,
        "nomineeSectionLikely": nominee,
        "freeLookDays": fl,
        "insurerHintId": insurer_id or None,
        "riders": [],
    }

    conf_parts = [c_sa, c_pt, c_ppt, c_prem, c_plan, c_freq, c_fl]
    positive = [p for p in conf_parts if p > 0]
    overall_raw = sum(positive) / len(positive) if positive else 0.2
    overall = round(min(0.95, max(0.15, overall_raw)), 2)

    confidence: dict[str, float] = {
        "sumAssuredInr": c_sa,
        "policyTermYears": c_pt,
        "premiumPaymentTermYears": c_ppt,
        "modalPremiumInr": c_prem,
        "premiumFrequency": c_freq,
        "productName": c_plan,
        "freeLookDays": c_fl,
        "nomineeSectionLikely": c_nominee,
        "overall": overall,
    }

    warnings: list[str] = []
    if confidence["overall"] < 0.45:
        warnings.append("Low extraction confidence — please verify fields against your PDF.")

    out = {
        "lifeSchedule": schedule,
        "confidence": confidence,
        "warnings": warnings,
        "textChars": {"cis": len(cis_text or ""), "bond": len(bond_text or "")},
        "fieldConfidenceUi": build_field_confidence_ui(confidence),
    }
    return out


def build_field_confidence_ui(confidence: dict[str, float]) -> list[dict[str, Any]]:
    """Per-field labels, scores, and verify-PDF nudges for the UI."""
    fields: list[tuple[str, str, bool]] = [
        ("productName", "Product / plan", True),
        ("sumAssuredInr", "Sum assured", True),
        ("policyTermYears", "Policy term", True),
        ("premiumPaymentTermYears", "Premium payment term", True),
        ("modalPremiumInr", "Modal premium", True),
        ("premiumFrequency", "Premium frequency", True),
        ("freeLookDays", "Free-look period", True),
        ("nomineeSectionLikely", "Nominee section (detected)", False),
    ]
    ui: list[dict[str, Any]] = []
    for key, label, numeric in fields:
        score = float(confidence.get(key, 0.0))
        tier = "high" if score >= 0.55 else ("medium" if score >= 0.3 else "low")
        ui.append(
            {
                "fieldKey": key,
                "label": label,
                "score": round(score, 2),
                "tier": tier,
                "verifyInPdf": tier != "high",
                "numericField": numeric,
            }
        )
    return ui
