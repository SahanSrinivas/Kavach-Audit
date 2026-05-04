"""Audit engine data version.

Bumped whenever the deduction tables, CSR figures, premium benchmarks,
or scoring formulas change. Stamped onto every AuditResult so we can
identify scores generated against stale data (spec Section 9 risks).

Format: YYYY.MM.DD-v{n} where n increments within a day.
"""
DATA_VERSION = "2026.05.03-v1"
