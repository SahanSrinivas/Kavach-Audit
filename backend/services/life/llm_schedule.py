"""Optional LLM refinement for low-confidence heuristic life extraction (text-only)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("kavach.life.llm")

LIFE_LLM_MODEL = os.environ.get("LIFE_LLM_MODEL", "claude-3-5-haiku-20241022")
MAX_CHARS_PER_DOC = 55_000
_METRICS: dict[str, int] = {
    "attempted": 0,
    "used": 0,
    "skipped_no_key": 0,
    "skipped_no_client": 0,
    "api_errors": 0,
    "bad_json": 0,
}


async def llm_refine_life_schedule(
    cis_text: str,
    bond_text: str,
    insurer_hint: str | None,
) -> dict[str, Any] | None:
    """Returns ``{"lifeSchedule": {...}, "confidence": {...}}`` or None on failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        _METRICS["skipped_no_key"] += 1
        logger.warning("life.llm.skip no ANTHROPIC_API_KEY")
        return None

    ct = (cis_text or "")[:MAX_CHARS_PER_DOC]
    bt = (bond_text or "")[:MAX_CHARS_PER_DOC]
    hint = insurer_hint or "unknown"

    prompt = f"""You are extracting structured data from Indian life insurance CIS and policy bond text.
Insurer hint (may be wrong): {hint}

Return ONLY valid JSON (no markdown) with this exact shape:
{{
  "lifeSchedule": {{
    "productName": string or null,
    "sumAssuredInr": number or null,
    "policyTermYears": number or null,
    "premiumPaymentTermYears": number or null,
    "modalPremiumInr": number or null,
    "premiumFrequency": "Monthly"|"Quarterly"|"Half-yearly"|"Annual"|null,
    "freeLookDays": number or null,
    "detectedRiders": ["critical_illness"|"personal_accident"|"hospital_daily_cash"|"waiver_of_premium"]
  }},
  "confidence": {{
    "sumAssuredInr": 0-1,
    "policyTermYears": 0-1,
    "premiumPaymentTermYears": 0-1,
    "modalPremiumInr": 0-1,
    "productName": 0-1,
    "overall": 0-1
  }}
}}

Rules:
- Parse Indian rupee formats (e.g. 1,00,00,000).
- If unsure, use null for fields and lower confidence.
- detectedRiders: only include riders explicitly mentioned.

--- CIS ---
{ct}
--- BOND ---
{bt}
"""

    try:
        from anthropic import AsyncAnthropic
    except ImportError as e:
        _METRICS["skipped_no_client"] += 1
        logger.warning("life.llm.skip anthropic missing: %s", e)
        return None

    client = AsyncAnthropic(api_key=api_key, timeout=45.0)
    _METRICS["attempted"] += 1
    try:
        message = await client.messages.create(
            model=LIFE_LLM_MODEL,
            max_tokens=2048,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        _METRICS["api_errors"] += 1
        logger.warning("life.llm.api_error %s", e)
        return None

    text = ""
    for block in message.content:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "") or ""
            break
    if not text:
        return None

    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        _METRICS["bad_json"] += 1
        logger.warning("life.llm.bad_json")
        return None

    if not isinstance(parsed, dict):
        return None
    _METRICS["used"] += 1
    logger.info("life.llm.used metrics=%s", _METRICS)
    return parsed


def merge_heuristic_and_llm(
    base: dict[str, Any],
    llm: dict[str, Any],
    threshold: float,
) -> dict[str, Any]:
    """When heuristic field confidence is below ``threshold``, prefer LLM value if present."""
    import copy

    out = copy.deepcopy(base)
    conf = out.get("confidence") or {}
    ls = out.get("lifeSchedule") or {}
    llm_ls = llm.get("lifeSchedule") or {}
    llm_cf = llm.get("confidence") or {}

    float_keys = [
        "sumAssuredInr",
        "policyTermYears",
        "premiumPaymentTermYears",
        "modalPremiumInr",
    ]
    for k in float_keys:
        if (conf.get(k) or 0) < threshold and llm_ls.get(k) is not None:
            ls[k] = llm_ls[k]
            conf[k] = max(conf.get(k) or 0, float(llm_cf.get(k) or 0.65))

    if (conf.get("productName") or 0) < threshold and llm_ls.get("productName"):
        ls["productName"] = llm_ls["productName"]
        conf["productName"] = max(conf.get("productName") or 0, float(llm_cf.get("productName") or 0.6))

    if llm_ls.get("premiumFrequency") and not ls.get("premiumFrequency"):
        ls["premiumFrequency"] = llm_ls["premiumFrequency"]
        conf["premiumFrequency"] = max(conf.get("premiumFrequency") or 0, 0.55)

    if llm_ls.get("detectedRiders"):
        merged = list(set((ls.get("detectedRiders") or []) + list(llm_ls["detectedRiders"])))
        ls["detectedRiders"] = merged

    # Recompute overall & fieldConfidenceUi (same keys as heuristic extractor).
    from services.life.extract_schedule import build_field_confidence_ui

    _overall_keys = (
        "sumAssuredInr",
        "policyTermYears",
        "premiumPaymentTermYears",
        "modalPremiumInr",
        "premiumFrequency",
        "productName",
        "freeLookDays",
        "nomineeSectionLikely",
    )
    conf_parts = [float(conf[k]) for k in _overall_keys if isinstance(conf.get(k), (int, float))]
    if conf_parts:
        conf["overall"] = round(min(0.95, max(0.2, sum(conf_parts) / len(conf_parts))), 2)

    out["lifeSchedule"] = ls
    out["confidence"] = conf
    out["fieldConfidenceUi"] = build_field_confidence_ui(conf)
    out.setdefault("warnings", [])
    _llm_warn = "Some fields were refined by LLM — still verify against your PDFs."
    if conf.get("overall", 1) < 0.45 and _llm_warn not in (out.get("warnings") or []):
        out["warnings"] = list(out.get("warnings") or []) + [_llm_warn]
    return out


def llm_metrics_snapshot() -> dict[str, int]:
    """Operational counters for logs/tests."""
    return dict(_METRICS)
