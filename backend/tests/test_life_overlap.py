"""Life vs health overlap hints (education-only)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.life.overlap import build_overlap_hints  # noqa: E402


def test_ci_overlap_hint():
    life = {"detectedRiders": ["critical_illness"]}
    policies = [{"type": "health", "policy_name": "Critical illness rider plan"}]
    out = build_overlap_hints(life, policies)
    codes = [h["code"] for h in out["hints"]]
    assert "ci_overlap" in codes


def test_no_health_policies_hint():
    life = {"detectedRiders": []}
    out = build_overlap_hints(life, [])
    codes = [h["code"] for h in out["hints"]]
    assert "no_health_policies" in codes


def test_pa_overlap():
    life = {"detectedRiders": ["personal_accident"]}
    policies = [{"type": "health", "policy_name": "Personal accident cover"}]
    out = build_overlap_hints(life, policies)
    assert any(h["code"] == "pa_overlap" for h in out["hints"])
