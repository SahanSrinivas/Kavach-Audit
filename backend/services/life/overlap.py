"""Health vs life overlap hints (education only — not legal advice)."""

from __future__ import annotations

import json
from typing import Any


def _policy_blob_lowercase(pol: dict[str, Any]) -> str:
    """Flatten policy document for keyword scan."""
    try:
        return json.dumps(pol, default=str).lower()
    except Exception:
        return ""


def health_signals(policies: list[dict[str, Any]]) -> dict[str, Any]:
    """Infer rider-like coverage hints from stored health policies."""
    ci = pa = st = False
    for pol in policies:
        if pol.get("type") != "health":
            continue
        blob = _policy_blob_lowercase(pol)
        name = str(pol.get("policy_name") or "").lower()
        if "critical illness" in blob or "critical illness" in name:
            ci = True
        if "personal accident" in blob or "pa rider" in blob or "accident" in name:
            pa = True
        if "super top" in blob or "top-up" in blob or "top up" in blob:
            st = True
    return {
        "criticalIllnessWordingLikely": ci,
        "personalAccidentWordingLikely": pa,
        "superTopUpLikely": st,
    }


def build_overlap_hints(
    life_schedule: dict[str, Any] | None,
    policies: list[dict[str, Any]],
) -> dict[str, Any]:
    """Combine latest life schedule detected riders with health portfolio keywords."""
    riders = list(life_schedule.get("detectedRiders") or []) if life_schedule else []
    rider_set = set(riders)
    hs = health_signals(policies)

    hints: list[dict[str, str]] = []

    if "critical_illness" in rider_set and hs["criticalIllnessWordingLikely"]:
        hints.append(
            {
                "code": "ci_overlap",
                "severity": "info",
                "title": "Critical illness — dual coverage possible",
                "detail": "Your life documents mention a CI rider and your health portfolio may "
                "already include CI-like coverage. Claims usually follow policy-specific "
                "coordination rules — confirm clauses in both contracts.",
            }
        )

    if "personal_accident" in rider_set and hs["personalAccidentWordingLikely"]:
        hints.append(
            {
                "code": "pa_overlap",
                "severity": "info",
                "title": "Personal accident overlap",
                "detail": "PA appears on both sides of your portfolio. Verify sum limits and "
                "whether benefits stack or duplicate.",
            }
        )

    if not policies:
        hints.append(
            {
                "code": "no_health_policies",
                "severity": "info",
                "title": "Add health policies for full overlap view",
                "detail": "Upload your mediclaim in the health audit so we can compare rider "
                "language with your life CIS/bond.",
            }
        )

    return {
        "lifeDetectedRiders": riders,
        "healthSignals": hs,
        "hints": hints,
    }
