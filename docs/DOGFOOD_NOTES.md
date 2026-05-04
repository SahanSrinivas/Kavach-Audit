# Dogfood Notes — Real Engine + Real Parser

Started: <fill in date>
Operator: founder
Setup: <USE_MOCKS=false local | beta-gate via curl | other>
Backend version: <git rev-parse HEAD>

This file is the spec for the next iteration. Fill in every weird score,
confusing message, parser error, or UX moment that felt off as you walk
through the flow. Don't filter — capture everything; we triage later.

---

## Test fixtures uploaded

| # | Document | Insurer | Plan | Doc type (schedule/wording/brochure) | Source |
|---|---|---|---|---|---|
| 1 | <filename> | | | | <friend / your own / sample PDF> |
| 2 | | | | | |
| 3 | | | | | |

---

## Per-stage observations

Walk through Stage 0 → 8 fresh with one persona. Note anything off.

### Stage 0 — Hook screen
- [ ] Loaded cleanly?
- Notes:

### Stage 1 — Identity (age, city)
- [ ] City auto-detect worked?
- [ ] Tier classification correct? (Mumbai → tier-1, etc.)
- Notes:

### Stage 2 — Family
- [ ] Composition options match a real Indian household?
- [ ] PEC selector covers the conditions you'd expect?
- Notes:

### Stage 3 — Money
- [ ] Income / EMI / expenses sliders feel right?
- Notes:

### Stage 4 — Policies (upload + declare)
- For each upload, capture:

#### Upload #1 — <filename>
- Document type detected by parser: <schedule / wording / brochure>
- Time to parse: ___ s
- Insurer canonicalized to: <canonical name or _UNKNOWN>
- Plan name extracted: <or "synthesized from type" — flag if so>
- sum_insured extracted: ____ (null if wording)
- premium_annual extracted: ____ (null if wording)
- confidence.overall: <high/medium/low>
- confidence.warnings: <paste>
- Anything weird in the rich `parser_output`?
- Anything weird in the flat `parsed_fields`?

#### Upload #2 — <filename>
(repeat structure)

#### Upload #3 — <filename>
(repeat structure)

### Stage 5 — Lifestyle
- [ ] Two-wheeler / intl-travel / smoker questions exhaustive?
- Notes:

### Stage 6 — Audit (the moment of truth)
- Total time from "Generate audit" click to scores rendered: ___ s
- Scores returned (paste from /api/audit/latest):
  - coverage: ___
  - cost: ___ (or null)
  - claim_readiness: ___ (or null)
  - gap: ___
- Engine mode: <real / mock>
- Beta invocation: <true / false>

#### Score sanity check
For each of the 4 scores:
- Does the number feel directionally right given what you uploaded?
- If wrong, by how much, and what would the correct score be?
- What field/rule do you suspect drove the wrong score?

#### Findings (top 3)
| # | Type | Severity | Headline | Felt right? | If not — why? |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

#### Findings (the rest)
- Any findings missing that you'd have expected?
- Any findings present that don't match what you uploaded?

### Stage 7 — Recommendations
- [ ] Cards relevant to the findings?
- [ ] Mock recommendations are still mock — confirm; nothing claims to be real
- Notes:

### Stage 8 — Dashboard / re-audit
- [ ] Portfolio summary correct?
- [ ] Re-audit button works?
- Notes:

---

## Bugs & UX issues (running list)

Sev = critical (data wrong) | high (UX broken) | medium (UX confusing) | low (cosmetic)

| # | Sev | Stage | One-line description | Repro | Suspected cause |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |

---

## Parser-specific findings

(things to feed back into prompt or canonicalizer)

- [ ] Insurers that didn't canonicalize: <list>
- [ ] Permanent exclusions that didn't canonicalize but should have: <list>
- [ ] Sub-limit categories the parser missed: <list>
- [ ] Plan-name extraction — did Claude extract real product names or synthesized garbage?

---

## Engine-specific findings

(things to feed back into deduction rules / formulas)

- [ ] Scores you'd want recalibrated: <which fixture, which score, by how much>
- [ ] Findings template wording that landed wrong: <paste>
- [ ] Rule that fired when it shouldn't have (or didn't fire when it should have): <which rule, which policy>

---

## Wordings DB candidates

Wordings I'd want pre-parsed first based on my own + family's policies:

1.
2.
3.

---

## End-of-session summary

After 30-60 min of dogfood, write 3-5 bullets here:

- Top issue:
- Surprised by:
- Most disappointing finding:
- Most accurate finding:
- One thing to fix before any external user sees this:
