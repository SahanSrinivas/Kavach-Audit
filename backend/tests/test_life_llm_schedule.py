"""Tests for optional LLM life schedule refinement."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.life.llm_schedule import merge_heuristic_and_llm  # noqa: E402


def test_merge_adds_warning_when_overall_low():
    base = {
        "lifeSchedule": {"sumAssuredInr": None, "detectedRiders": []},
        "confidence": {
            "sumAssuredInr": 0.1,
            "policyTermYears": 0.1,
            "premiumPaymentTermYears": 0.1,
            "modalPremiumInr": 0.1,
            "premiumFrequency": 0.1,
            "productName": 0.1,
            "freeLookDays": 0.1,
            "nomineeSectionLikely": 0.1,
            "overall": 0.1,
        },
        "warnings": [],
    }
    llm = {
        "lifeSchedule": {"sumAssuredInr": 2_500_000},
        "confidence": {"sumAssuredInr": 0.3},
    }
    out = merge_heuristic_and_llm(base, llm, threshold=0.9)
    assert out["lifeSchedule"]["sumAssuredInr"] == 2_500_000
    assert any("refined by LLM" in w for w in out["warnings"])

