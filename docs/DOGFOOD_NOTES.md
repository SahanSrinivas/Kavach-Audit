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

---

# Session 1 — Infrastructure shakedown (founder, 2026-05-04 evening)

## Setup pain (one-off, environment-only)

These are fixed for the next session — capturing for the runbook:

1. **Venv-vs-system Python conflict** — `pip install -r requirements.txt` fails on
   the dead `emergentintegrations==0.1.0` line, leaving the venv with NO packages.
   The shell's `python` alias points at system Python 3.14, so `python -c "import x"`
   tests succeed against system, but `which uvicorn` resolves to a different Python
   (3.10) entirely. Result: parser raises `missing_dependency` for `anthropic` even
   though it "appears installed."
   - **Fix landed:** `sed` removed the broken line.
   - **TODO for next commit:** delete `emergentintegrations==0.1.0` from
     [backend/requirements.txt](../backend/requirements.txt) permanently. One line.

2. **`USE_MOCKS=false` doesn't persist across uvicorn restarts** — has to be
   re-exported every time, OR set in `.env`. Recommend flipping the default
   `.env` entry once you're past dogfood-1.

3. **The frontend never passes `?beta=audit-real`** — confirmed during this
   session. To dogfood the real engine via the UI you have to flip
   `USE_MOCKS=false` globally; the beta-gate plumbing only matters for shared
   backends. Note for Phase 1.5+ if we want UI-driven beta opt-in.

## Parser observations on the eBID PDF (44 KB, ~2 pages)

**Result:** `parser.success` after one 429 retry cycle.
- Total wall-clock: **72.8 seconds** (mostly the 56-second 429 backoff).
  Without the 429, Claude's actual processing was ~16 seconds — at the high
  end of the 5-15s target.
- Insurer canonicalized to: **`_UNKNOWN`** ⚠
- Confidence: **low**, with **3 warnings**.

**Things to investigate in Mongo for this row** (commands below):

- `insurer_name_raw` — what did Claude actually see? If it's a real insurer
  in our list with a slight name variation, we need to add an alias to
  [canonical_vocabulary.py:INSURER_ALIASES](../backend/services/parser/canonical_vocabulary.py).
  If it's an insurer NOT in our top-19 list (e.g., LIC, SBI Life, Kotak
  General), we need to expand the canonical list.
- `parse_confidence.warnings` — the 3 warnings tell us what Claude was
  uncertain about; that's the next prompt-tuning input.
- `parser_output.policy_type` — did Claude correctly identify it as
  health/life/motor/etc.?

## Bugs and UX issues confirmed this session

| # | Sev | Stage | Description | Repro | Suspected cause |
|---|---|---|---|---|---|
| 1 | medium | 4 (upload) | 429 from Anthropic → user sees generic 502 with no retry hint. 56-second backoff happens silently. | Upload a 50+ page PDF on Tier-1 Anthropic account; or upload many in <1 min. | `policies_router.py` maps `ParseFailureError(api_unavailable)` to 502 generic. Should map 429-after-retry to 503 with `Retry-After` header + a user-facing "throttled, please retry in N seconds" message. |
| 2 | low | 4 (upload) | No progress indicator during 5-30s parse — UI shows "Reading sub-limits…" rotation but user doesn't know real elapsed time. Acceptable for now, painful at the high end. | Watch the spinner during a 70-second parse. | Frontend timer in [Stage4Policies.jsx](../frontend/src/pages/Stage4Policies.jsx). |
| 3 | medium | 4 (upload) | `_UNKNOWN` insurer on a real Indian insurance PDF. Engine falls back to `_DEFAULT` CSR (0.85) → silent `-15` deduction on every audit using this policy. User has no idea their insurer wasn't recognized. | Upload eBID_SA609099_BI_12042021090251.pdf | Either insurer not in canonical list, or alias map missing the surface form. Need to inspect `insurer_name_raw`. |
| 4 | low | env | Parser performance target (<15s) hard to hit — even small PDFs taking 16s. Token throughput on Tier-1 Anthropic + image-mode PDF processing is the floor. | Parse any PDF with cold cache. | Inherent to Claude Sonnet 4 PDF mode + Tier 1; will improve with higher tiers. |

## Wordings DB candidates (from this PDF)

- N/A — this PDF was a life-insurance benefit illustration, not a health policy.

## What the eBID upload was actually

| Field | Value |
|---|---|
| `insurer_name_raw` | Exide Life Insurance |
| `insurer (canonical)` | `_UNKNOWN` ⚠ |
| `policy_type` | `endowment` |
| `sum_insured` | 391,547 (maturity benefit, not health cover) |
| `premium` | 100,000 |
| `parse_confidence.overall` | low |
| Warnings | "Document is a life insurance benefit illustration, not a health insurance policy" + 2 more |

Audit produced: `coverage=0, cost=null, claim_readiness=null, gap=40`.

Top 3 findings:
1. ✓ "You have no health insurance" — TRUE (this user genuinely has no health policy)
2. ✗ "Your term cover is ₹1 Cr but your family needs ~₹2 Cr" — FALSE; user has ₹3.9L endowment, not ₹1 Cr term. Template floor bug (see Bug B below).
3. ✓ "You own a vehicle but have no own-damage motor insurance" — TRUE (depends on lifestyle flag set in Stage 5).

## Real bugs surfaced this session

| ID | Sev | Issue | Where to fix |
|---|---|---|---|
| **A** | high | "Exide Life Insurance" → `_UNKNOWN` insurer. All Indian life insurers (LIC, Exide Life, HDFC Life, ICICI Pru, Max Life, Tata AIA, SBI Life, Bajaj Allianz Life, Aditya Birla Sun Life, Kotak Life, PNB MetLife) missing from canonical list AND CSR_TABLE. Engine falls through to `_DEFAULT` (silent `-15`). | Add life insurers to [canonical_vocabulary.py:CANONICAL_INSURER_NAMES](../backend/services/parser/canonical_vocabulary.py) + [csr_table.py:CSR_TABLE](../backend/services/audit/constants/csr_table.py). Note: life CSR is a different metric (death-claim settlement) — IRDAI publishes it separately. |
| **B** | medium | `underinsured_life` finding template displays "₹1 Cr cover" when actual cover is sub-crore due to `max(1, ...)` floor in [findings.py:_from_coverage](../backend/services/audit/findings.py). | Switch finding text to format-in-lakhs when actual_cr < 1 (e.g., "₹4 Lakh cover" instead of "₹1 Cr cover"). |
| **C** | debatable | Endowment fully satisfies the "term_life" gap requirement in [gap.py:_HAS_PROTECTION](../backend/services/audit/gap.py). A ₹3.9L endowment shouldn't equal "user has term life cover" — should require some minimum SI (e.g., 5× annual income) before satisfying. | Add a per-category SI floor in `gap._has()` for type=endowment/ulip → term_life mapping. |
| **D** | medium | `plan_name: "_UNKNOWN Endowment"` synthesized garbage — parser doesn't extract real plan names today. Already documented in [docs/WORDINGS_DESIGN_NOTES.md](WORDINGS_DESIGN_NOTES.md) Decision 2. Blocks the wordings DB lookup mechanism. | Add `plan_name: Optional[str]` to ParsedPolicy + prompt rule. |
| **E** | medium | Engine should detect "user uploaded only life insurance, no health" and produce a structured "no_health_uploaded" message, not numeric scores of 0/null/null/40. Same family as the existing TODO(audit-schedule-required) in engine.py. | Same defer location — bundle with Issue 4 from v0.4 review. |

## Surface forms / aliases to add (next prompt-tuning pass)

If we're keeping a single canonical insurer table, add these life insurer aliases (mirror the health pattern):

```python
# Life insurers — add to CANONICAL_INSURER_NAMES + INSURER_ALIASES
"LIC":                      ["LIC", "Life Insurance Corporation", "LIC of India"],
"HDFC Life":                ["HDFC Life", "HDFC Standard Life", "HDFC Life Insurance"],
"ICICI Prudential Life":    ["ICICI Pru", "ICICI Prudential", "ICICI Prudential Life"],
"Max Life":                 ["Max Life", "Max Life Insurance"],
"Tata AIA Life":            ["Tata AIA", "Tata AIA Life Insurance"],
"SBI Life":                 ["SBI Life", "SBI Life Insurance"],
"Bajaj Allianz Life":       ["Bajaj Allianz Life", "Bajaj Allianz Life Insurance"],
"Aditya Birla Sun Life":    ["ABSLI", "Aditya Birla Sun Life", "Birla Sun Life"],
"Kotak Life":               ["Kotak Life", "Kotak Mahindra Life", "Kotak Life Insurance"],
"PNB MetLife":              ["PNB MetLife", "MetLife"],
"Exide Life":               ["Exide Life", "Exide Life Insurance"],   # acquired by HDFC Life Jan 2023 — note for canonicalizer
```

(Exide Life was acquired by HDFC Life and merged in Jan 2023; existing Exide policies are honored under HDFC Life. Decide: alias to `HDFC Life` or keep as legacy `Exide Life` for accuracy on older policies.)

## Decision needed before continuing dogfood

**This run hit a wrong-document-type case** (life insurance, not health). The engine handled it gracefully but produced 1 false finding. To continue dogfood meaningfully, options:

1. **Pause real uploads, fix Bug A + B first**, then re-run on the same PDF and confirm fixes.
2. **Continue with HEALTH PDFs only** — eBID happened to be life. Get a real health schedule (yours or a friend's) and dogfood that.
3. **Test more wrong-document-types deliberately** — upload a motor insurance, a travel policy, a totally non-insurance PDF — see how the engine degrades.

Recommend (2) for next, since the v0.4 work was scoped to health and we should validate the happy path on a real health schedule before iterating on edges.

