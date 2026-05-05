"""Unit tests for heuristic life schedule extraction (no PDF)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.life.extract_schedule import extract_life_schedule  # noqa: E402


def test_sum_assured_and_term_from_plain_text():
    cis = "Basic Sum Assured Rs. 1,00,00,000\nModal Premium Rs. 24,000 Annual"
    bond = "Policy Term 35 years\nPremium Paying Term 20 years"
    out = extract_life_schedule(cis, bond)
    ls = out["lifeSchedule"]
    assert ls["sumAssuredInr"] == 10_000_000
    assert ls["policyTermYears"] == 35
    assert ls["premiumPaymentTermYears"] == 20
    assert len(out.get("fieldConfidenceUi") or []) >= 8


def test_nominee_flag():
    cis = "Nominee details as per proposal form"
    bond = ""
    out = extract_life_schedule(cis, bond)
    assert out["lifeSchedule"]["nomineeSectionLikely"] is True
