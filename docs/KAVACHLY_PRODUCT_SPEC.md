# Kavachly — Product & Engineering Spec

**Version:** 1.0  
**Last updated:** May 5, 2026  
**Founders:** Sahan (health audit) + co-founder (life audit)  
**Status:** Pre-merge of `pdf-parser` + `insurance-page`. Heading to v0.7-multi-product-audit.

This is the single source of truth for what Kavachly is, what's built, and what we're shipping next. Scope is deliberately narrow: **Health and Life insurance only, India only, until v1.0 ships.** Other verticals (motor, home) and other geographies (Indonesia, Philippines) are explicitly deferred.

---

## 1. What Kavachly Is

**Kavachly is the audit layer for Indian household insurance.**

Tagline: *"Insurance, audited."*

We translate dense insurance policy documents into structured, honest assessments of what users actually have, what they're missing, and what will happen when they file a claim.

**Two products, one platform:**
- **Health insurance audit** — schedule + wording → structured audit
- **Life insurance audit** — CIS + bond → structured audit

**Who we serve:** Indian households with one or more existing health and/or life policies who suspect their coverage may not be what they think it is.

**Who we don't serve:** First-time buyers (aggregators serve them), insurance companies (B2B audit firms serve them), motor/home insurance owners (deferred to v2.0).

---

## 2. Why This Exists — The Five Gaps

These are the structural problems we address. Each gap maps to a feature we're building.

### Gap 1: Post-purchase intelligence
PolicyBazaar and aggregators sell policies and disappear. Insurer apps bill and claim but don't tell you if your policy is good. Generic AI gives generic answers. Nobody systematically audits what you already own.

**Our answer:** "Your policy doesn't end at purchase. Audit, monitor, optimize."

### Gap 2: Claim-time advocacy
~30% of Indian health insurance claims face partial deductions or rejections. Users have no advocate at claim time. Agents are unreachable. Insurers are adversarial.

**Our answer:** Pre-flight checks, document checklists, rejection analysis, structured appeals.

### Gap 3: Honest comparison
Aggregators sort by price (commission-driven). Advisors give opinions ($). Generic AI hallucinates. Nobody answers "should I switch?" honestly — including the answer "no, you're fine."

**Our answer:** Structured comparison engine that recommends staying when switching doesn't help.

### Gap 4: Life-stage intelligence
Insurance needs change with life events (marriage, baby, home loan, parent aging) but products don't auto-adjust. Users buy at 28 single, never re-evaluate at 35 married with kids.

**Our answer:** Life-event-triggered re-audit. The engagement loop that brings users back.

### Gap 5: Indian-specific household insurance
Indian households are multi-generational, with dependent siblings, joint financial obligations, and tax-driven product choices. Western frameworks don't capture this.

**Our answer:** "Built for Indian households" as defensible positioning.

---

## 3. What's Built (As of v0.6.1-preflight + insurance-page)

### 3.1 Health Insurance Audit Pipeline

| Component | Status | Where it lives |
|-----------|--------|----------------|
| Multi-stage user funnel (identity, family, money, policies, lifestyle) | ✅ Done | `frontend/src/pages/Stage*.jsx` |
| PDF parser (Claude Sonnet 4) | ✅ Done | `backend/services/parser/pdf_parser.py` |
| Pre-flight PDF validation (5-stage filter, <50ms reject) | ✅ Done | `backend/services/parser/preflight.py` |
| Audit engine (4 scores: coverage, cost, claim_readiness, gap) | ✅ Done | `backend/services/audit/` |
| Findings system (severity, action, recommendation, score impact) | ✅ Done | `backend/services/audit/findings.py` |
| Wordings DB infrastructure (Phase 1.5 prep) | ✅ Done (not yet integrated) | `backend/services/wordings.py`, admin endpoints, CLI scripts |
| Multi-policy support with nicknames | ✅ Done | `policy_nickname` field, frontend UI |
| Dashboard with portfolio + per-policy detail views | ✅ Done | `frontend/src/pages/Dashboard.jsx` + `components/dashboard/*` |
| Public landing page | ✅ Done | `frontend/src/pages/Landing.jsx` |

**Test count:** 539 backend tests passing.  
**Tagged release:** v0.6.1-preflight on `pdf-parser` branch.

### 3.2 Life Insurance Audit Pipeline

| Component | Status | Where it lives |
|-----------|--------|----------------|
| CIS + bond PDF extraction (heuristic + Haiku fallback) | ✅ Done | `backend/services/life/extract_schedule.py` |
| OCR fallback (Tesseract for scanned PDFs) | ✅ Done | `backend/services/life/pdf_text.py` |
| Per-field confidence UX (high/medium/low + verifyInPdf badges) | ✅ Done | `backend/services/life/extract_schedule.py`, `LifeSchedule.jsx` |
| Optional LLM refinement (cost-conscious, threshold-gated) | ✅ Done | `backend/services/life/llm_schedule.py` |
| Rate limiting (in-memory + optional Redis-shared) | ✅ Done | `backend/services/rate_limit.py` |
| Storage (life_schedules collection) | ✅ Done | `db.life_schedules` |
| FY stats data pipeline (CSV → JSON → trust panel) | ✅ Done | `data/life/`, `scripts/build_life_fy_json.py` |
| Trust panel (IRDAI multi-metric: CSR, persistency, solvency, grievances) | ✅ Done | `frontend/src/components/life/LifeTrustPanel.jsx` |
| Life schedule review page with field confidence | ✅ Done | `frontend/src/pages/LifeSchedule.jsx` |
| Education-only health/life overlap hints | ✅ Done | `backend/services/life/overlap.py` |
| Operational documentation (deploy, QA, spec) | ✅ Done | `docs/LIFE_*.md`, `docs/DEPLOY_LIFE.md` |

**Test count:** +13 tests (all green) on insurance-page branch.  
**Branch:** `insurance-page` (descends from `pdf-parser`, ready to merge).

---

## 4. What's Missing — The Completion Gap

Both pipelines extract and display today. Neither yet **audits** in the full sense (score, find problems, recommend actions). This is the v1.0 completion work, split between founders.

### 4.1 Life pipeline needs to match Health's depth

| Capability | Health has it | Life needs it |
|-----------|--------------|---------------|
| Audit engine with scores | ✅ 4 scores | ❌ Build life equivalent |
| Findings system | ✅ Structured | ❌ Build life findings |
| Recommendations | ✅ Stage 7 page | ❌ Build life recommendations |
| Benchmarks (income-based ideal) | ✅ Health benchmarks | ❌ Add life benchmarks |
| Pre-flight reject for non-policy PDFs | ✅ Built | ❌ Add to life endpoint |

### 4.2 Health pipeline can learn from Life

| Capability | Life has it | Health needs it |
|-----------|-------------|-----------------|
| Per-field confidence badges | ✅ Built | ❌ Backport pattern |
| Cost-conscious LLM gating | ✅ Built | ⚠️ Health uses Sonnet always (premium accuracy intentional, but worth reviewing for non-critical paths) |
| Operational metrics surfaces | ✅ Built | ⚠️ Health has less observability |

### 4.3 Both pipelines need shared features

These are the strategic differentiators. Built once, work for both health and life.

| Feature | Why it matters | Complexity |
|---------|---------------|-----------|
| Claim simulator | Highest-emotional-value output users will share | High |
| Renewal negotiator | Drives recurring engagement (60-day pre-renewal) | Medium |
| Life event re-audit | Engagement loop — why users come back | Low-Medium |
| Claim pre-flight | Save users from claim rejections | Medium |
| Cross-product household view | The moment "audit your insurance" beats "audit one policy" | Medium-High |

---

## 5. Phase Roadmap (Health + Life Only)

Strict scope. No motor, no home, no other geographies until v1.0 ships.

### Phase 1: Validation (this week — Sahan owns)

**Goal:** Confirm health audit works on real friend PDFs.

**Tasks:**
- Real Session 2 dogfood with 5 friend health PDFs (USE_MOCKS=false)
- Capture bugs in DOGFOOD_NOTES.md with real numbers
- Triage critical + high severity, fix before Phase 2 starts

**Owner:** Sahan  
**Time budget:** 2-3 days  
**Success criteria:**
- Parser succeeds on 5 of 5 real PDFs
- Audit produces sensible scores
- ≤5 critical bugs surfaced; all fixed

### Phase 2: Multi-product audit completion (weeks 2-3 — both founders)

**Goal:** Complete the audit loop on both health and life. v0.7 ships.

**Track A — Sahan owns (health):**
- Wordings DB integration (`policy_merger.py` + `policies_router` wiring)
- Schedule-only upload flow works end-to-end
- Manually QA-parse 10 priority wordings (HDFC, Niva Bupa, Star, Care, Aditya Birla, ICICI, Tata AIG, Bajaj, ManipalCigna, New India)
- Backport per-field confidence pattern from life
- Bug fixes from dogfood

**Track B — co-founder owns (life):**
- Life audit engine: 4 scores parallel to health
  - Coverage: sum assured vs income/dependents (10-15x rule)
  - Cost: premium-to-cover ratio benchmarked against age + term
  - Claim Readiness: nominee setup, rider coverage, document completeness
  - Gap: missing critical illness rider, missing accidental death cover, term too short
- Life findings system (structured findings parallel to health)
- Life recommendations (Phase 7-equivalent for life)
- Life benchmarks data (income-based ideal sum assured, term length recommendations, premium ratio caps)
- Pre-flight validation on `/life/extract` (port from health preflight)

**Joint:**
- Merge `insurance-page` → `pdf-parser` → `main`
- Tag v0.7-multi-product-audit
- Update PRODUCT_VISION.md together

**Success criteria:**
- Health: 539+ tests still passing, schedule-only flow works
- Life: 4 scores produce sensible output for real life policies
- Combined: dashboard shows both health and life policies in one view

### Phase 3: Shared engagement features (weeks 4-6)

**Goal:** Build the features that turn one-time audit into recurring product.

In priority order (build sequentially, each week):

**Week 4: Life event re-audit**
- Smallest, highest-leverage. Users mark life events (marriage, baby, home loan, etc.)
- Triggers automatic re-evaluation with new context
- Email/SMS nudge: "Major life change detected — re-audit recommended"
- Owner: Both (life events affect both health and life policies)

**Week 5: Claim pre-flight**
- Before user files a claim, walk through specific policy rules
- Health: room rent caps, waiting periods, sub-limits, documentation
- Life: nominee verification, document checklist, beneficiary setup
- Owner: Sahan (health side) + co-founder (life side)

**Week 6: Renewal negotiator**
- 60 days before renewal, automatic re-audit + comparison with current market
- "Here's what changed since you bought. Here's what to negotiate."
- Owner: Joint

### Phase 4: Beta launch (week 7)

**Goal:** Real users, in production.

- GCP deployment to asia-south1 (Mumbai)
- MSG91 SMS integration
- Cloudflare DNS + custom domain (kavachly.com)
- Sentry + UptimeRobot monitoring
- Beta waitlist + invite flow (50-100 users initially)

**Success criteria:**
- Production stable for 7 days
- 30+ beta users completed audits (mix of health and life)
- ≤5 critical bugs in beta
- p95 audit response time <60s

### Phase 5: Claim simulator + Cross-product household view (weeks 8-10)

**Goal:** Strategic differentiators that no competitor has.

**Claim simulator:**
- Health: "If you got hospitalized for ₹3L tomorrow at Apollo Mumbai, this is what your policy actually pays vs what you pay out of pocket."
- Life: "If something happened to you tomorrow, this is what your family receives after taxes and processing time."

**Cross-product household view:**
- Single dashboard showing all household insurance
- "For your stage of life (32, 1 kid, ₹15L income, Mumbai), you should have ₹25L health + ₹2Cr term. Here's the gap."
- Multi-member coverage map
- Identifies redundancy and gaps across products

### Phase 6: Claim rejection analyzer (weeks 11-12)

The "killer feature" — high-emotional-value, defensible, no licensing required.

- User uploads rejection letter
- System explains rejection in plain language
- Evaluates legitimacy based on user's specific policy wording
- Generates structured appeal template
- Provides escalation paths (insurer's grievance redressal officer → IRDAI ombudsman)

### What's NOT in scope (until v1.0 ships)

Explicit non-goals to prevent scope creep:

- ❌ Motor insurance audit
- ❌ Home insurance audit
- ❌ Travel insurance audit
- ❌ Mutual fund audit
- ❌ Credit card audit
- ❌ Other geographies (Indonesia, Philippines, Vietnam)
- ❌ B2B SaaS for agents
- ❌ Insurance broking license
- ❌ Direct claim filing on user's behalf

These are explicitly deferred. Once v1.0 (Phases 1-6 complete) ships and we have user data, we revisit.

---

## 6. Co-founder Action Items (Cursor-ready prompts)

### Priority 1: Life Audit Engine

Build the life-side equivalent of the health audit engine. Parallel architecture to `backend/services/audit/`.

**Files to create:**
- `backend/services/life/audit/__init__.py`
- `backend/services/life/audit/types.py` — `LifeAuditResult`, `LifeFinding`, `LifeScoreBreakdown` dataclasses
- `backend/services/life/audit/coverage.py` — Coverage Score logic
- `backend/services/life/audit/cost.py` — Cost Score logic
- `backend/services/life/audit/claim_readiness.py` — Claim Readiness Score logic
- `backend/services/life/audit/gap.py` — Gap Score logic
- `backend/services/life/audit/findings.py` — Findings generator
- `backend/services/life/audit/benchmarks.py` — Income-based ideal coverage, term length, premium ratios
- `backend/services/life/audit/runner.py` — Orchestrator
- `backend/tests/test_life_audit_*.py` — Test files (one per score)

**Cursor prompt for co-founder:**

```
Build life insurance audit engine, parallel to backend/services/audit/ 
(health). Read the health audit engine first to understand the pattern, 
then build life equivalent.

Inputs to LifeAudit:
- LifeSchedule (existing structure from extract_schedule.py)
- User profile: age, gender, dependents, annual_income, city_tier, smoker

Outputs:
- LifeAuditResult dataclass with:
  - scores: {coverage, cost, claim_readiness, gap} each 0-100 or null
  - findings: ranked list of LifeFinding (severity, type, headline, action)
  - all_findings: full ranked list
  - breakdowns: per-score details with reasoning
  - data_version: "life-2026.05"
  - engine_ms: int
  - generated_at: ISO

Scoring rules:

COVERAGE SCORE (0-100):
- Sum assured / annual income ratio
  - 15x+ → 100
  - 10-15x → 80
  - 5-10x → 60
  - <5x → 40
- Adjust for dependents (more dependents need higher multiple)
- Adjust for liabilities (home loan adds to required cover)

COST SCORE (0-100):
- Premium / sum assured (should be benchmarked against age + term)
- Use IRDAI mortality tables as baseline
- Flag overpriced products (endowment plans where ULIP+term combo is cheaper)
- 100 = at or below market median; 0 = >2x market

CLAIM READINESS SCORE (0-100):
- Nominee set: +30 (else 0)
- Contingent nominee set: +10
- All riders documented: +20
- CSR of insurer >95%: +20 (else proportional)
- Free look period not expired: +10
- Premium auto-pay set up: +10

GAP SCORE (0-100):
- Missing critical illness rider: -20
- Missing accidental death cover: -15
- Term ends before age 60: -25
- Sum assured below 10x income: -20
- No personal accident cover anywhere: -10
- Single life policy when family has dependents: -10
- (Score = 100 minus deductions, floor 0)

LIFE FINDINGS - generate from these patterns:
- "underinsured_life": Sum assured <10x income
- "missing_critical_illness": No CI rider
- "missing_accidental_death": No AD rider
- "term_too_short": Coverage ends before age 60
- "endowment_returns_low": Endowment policy with <6% IRR
- "no_nominee": Nominee not set or invalid
- "premium_overweight": Premium >5% of annual income
- "single_dependent_risk": Only spouse as nominee, no contingent

Each finding has:
- severity: "red" | "amber" | "info"
- type: string (one of above)
- icon: lucide icon name
- headline: 1-line plain English
- explanation: 2-3 line context
- action: 1-line what to do
- score_impact: dict mapping score type to deduction
- related_policy_id: from life_schedules
- recommendation: "buy_term_top_up" | "add_ci_rider" | "increase_term" | etc

Tests required:
- Each score function tested with known input → known output
- Findings tests: synthetic policies trigger expected findings
- Edge cases: missing data, null scores, age boundaries
- ~30-40 tests total

Constraints:
- Match the architectural patterns of backend/services/audit/ (health side)
- Pure functions, deterministic, sub-millisecond runtime
- No Claude API calls in the audit engine itself
- All thresholds as named constants at top of each module
- mypy strict clean

When done, integrate into life_router.py as a new endpoint:
POST /api/life/audit — runs audit on saved schedule for current user
GET /api/life/audit/latest — returns most recent audit

Show me the diff per file before merging.
```

### Priority 2: Life Recommendations Engine

Parallel to health's Stage 7 recommendations, but for life.

**Files to create:**
- `backend/services/life/recommendations.py` — Recommendations generator
- `backend/tests/test_life_recommendations.py`
- `frontend/src/pages/LifeRecommendations.jsx` — UI for showing recommendations

**Cursor prompt for co-founder:**

```
Build life insurance recommendations engine. Generates ranked product 
suggestions based on audit findings.

Reads:
- LifeAuditResult (from new life audit engine)
- User profile

Outputs:
- LifeRecommendation list (ranked by fit)
- Each recommendation: product type, suggested provider tier, sum assured, 
  term, estimated premium, reasoning

Recommendation rules:

If finding "underinsured_life":
- Recommend term top-up
- Suggested SA = (10x income) - current SA
- Term = until age 60 minimum

If finding "missing_critical_illness":
- Recommend CI rider OR standalone CI policy
- Suggested cover = 50% of income or ₹25L (whichever lower)

If finding "endowment_returns_low":
- Recommend "term + mutual fund" combo
- Show projected returns over 20 years vs current endowment

If no findings:
- "Your life cover looks healthy. Re-audit at next life event."

Constraints:
- DO NOT recommend specific insurer products (we're commission-neutral)
- Recommend product TYPES and TIERS (e.g. "top-CSR insurer", "₹2Cr term, 
  age-60 expiry")
- User can manually compare specific products in Phase 5 comparison engine
- Honest "stay with current" when audit finds no issues

UI (LifeRecommendations.jsx):
- Hero: "Based on your audit, here's what we'd suggest"
- Each recommendation card: type, sum assured, term, est. premium, 
  reasoning, "How to act on this" CTA
- "No recommendations" state when audit is clean: "Your cover is solid"

Tests: 
- ~15 tests covering each recommendation rule
- Tests for "no findings → stay with current" honest case

Show me the diff before merging.
```

### Priority 3: Pre-flight on Life Endpoint

Port the health preflight algorithm to life.

**Cursor prompt for co-founder:**

```
Add pre-flight PDF validation to /api/life/extract endpoint. Read 
backend/services/parser/preflight.py from pdf-parser branch as reference.

Goal: Reject non-policy PDFs (resumes, bank statements, invoices) before 
spending compute on extraction + optional LLM call.

Reuse the health preflight module if possible — it's already generalized:
- Stage 1: Structural (magic bytes, page count, encryption, size)
- Stage 2: Text extraction via pymupdf (already a dep)
- Stage 3: Multi-signal scoring (vocab, regulatory, structure, brand, 
  negative)
- Stage 4: Decision matrix (≥50 accept, 30-49 borderline defer, <30 reject)
- Stage 5: Reject envelope with detected_type_hint

For life-specific tuning:
- Add life-vocabulary indicators: "sum assured", "policy term", "premium 
  payment term", "nominee", "free look period", "rider", "CIS"
- Add life-insurer canonical names (LIC, HDFC Life, ICICI Pru Life, SBI 
  Life, Max Life, Tata AIA Life, Bajaj Allianz Life, Aditya Birla Sun Life, 
  Kotak Life, Canara HSBC, etc.)
- Threshold tuning: life CIS docs are more standardized than health, so 
  ACCEPT threshold can be slightly higher (55 vs 50) without false 
  rejections

Wire into life_router.py:
- Run preflight BEFORE extraction
- On reject: 400 with structured envelope (same shape as health)
- Log to parse_attempts collection with preflight_outcome

Tests:
- ~10 tests covering positive cases (real CIS docs), negative cases 
  (resume, bank statement), edge cases (scanned PDF defers to extraction)

Show me the diff before merging.
```

### Priority 4 (optional, this weekend if time permits): Field-level confidence backport to health

Take the per-field confidence pattern from life and apply to health's parsed policies.

**Cursor prompt for co-founder:**

```
Backport per-field confidence pattern from life to health.

Reference: backend/services/life/extract_schedule.py:build_field_confidence_ui()
and frontend/src/pages/LifeSchedule.jsx:FieldConfidenceBadge component.

Goal: Health's parsed policies should also surface per-field confidence 
with high/medium/low tiers + verifyInPdf flag.

Backend changes:
- Modify backend/services/parser/pdf_parser.py to compute per-field 
  confidence based on Claude's output (extracted_fields_with_low_confidence 
  array already exists — extend to full field-level scoring)
- Add field_confidence_ui to ParsedPolicy output

Frontend changes:
- Reuse FieldConfidenceBadge component (move to shared components folder)
- Add to Stage6Audit and policy detail views

Tests:
- ~5 tests for the backport
- Snapshot tests that field_confidence_ui structure matches life's

Show me the diff before merging.
```

---

## 7. Sahan's Action Items

### Priority 1: Health dogfood (this weekend)

**Files affected:** `docs/DOGFOOD_NOTES.md`, possibly bug fixes across backend/frontend

**Tasks:**
1. Real Session 2 dogfood with 5 friend PDFs on Mac
2. USE_MOCKS=false, watch backend logs
3. Capture real numbers in DOGFOOD_NOTES.md:
   - Parse times (real ₹35/parse, real 5-15s)
   - Confidence levels
   - Score outputs
   - Bugs surfaced
4. Triage bugs by severity
5. Fix critical + high before Phase 2 starts

### Priority 2: Wordings DB integration (week 2)

**Files affected:** `backend/services/policy_merger.py` (new), `backend/routers/policies_router.py` (modify), `frontend/src/pages/Stage4Policies.jsx` (modify)

**Tasks:**
1. Build `policy_merger.py` — merges schedule fields with looked-up wording rules
2. Wire into `policies_router._build_parsed_policy`: after schedule parse, lookup wording, merge if found
3. Schedule-required UX: when only wording uploaded, gracefully request schedule
4. End-to-end test: schedule-only upload produces full audit using merged wording rules

### Priority 3: Manual wording QA (weeks 1-3, ongoing)

**Tasks:**
1. Download Tier 1 wordings (5 PDFs already downloaded via scripts/download_wordings.py)
2. Run `parse_wording.py --dry-run` on each
3. Review JSON output for accuracy
4. Promote to `human_verified` via verify_wording.py
5. Manually correct via admin PATCH if needed
6. Target: 10 verified wordings by end of Phase 2

---

## 8. Joint Founder Decisions Pending

Items that need a real conversation, not delegation:

| Item | Decision needed | Stakes |
|------|-----------------|--------|
| Equity arrangement | Document founder equity in writing | Future-critical; do in next 30 days |
| Working rhythm | Weekly sync? Daily standup? Async only? | Productivity |
| Decision rights | Who decides what? Solo vs joint? | Avoid future friction |
| Storage convergence | Keep `policies` and `life_schedules` separate, or merge? | Phase 5 work depends on this |
| Domain registration | Register kavachly.com? | Pre-Phase 4 launch |
| Anonymous vs auth-required | Life extract is public, health is auth. Unified pattern? | Architectural consistency |
| Beta launch timing | Confidence threshold to invite first users | Phase 4 trigger |

---

## 9. Decision Principles

When facing a roadmap decision, ask:

1. **Does this fit the audit positioning?** If we're auditing, we're honest. Anything that compromises this is rejected.
2. **Does this require us to break commission neutrality?** If yes, no.
3. **Does this work for the median Indian household, not just the top 5%?** Premium concierge tier is fine; not the core product.
4. **Does this only serve health/life, or does it expand scope?** If expansion, defer until v1.0 ships.
5. **Does this create more lock-in for users, or more freedom?** We win by being trustworthy.

---

## 10. North Star Metrics

**Primary:** Number of households that trust Kavachly to audit their insurance.

**Leading indicators:**
- Audit completion rate (uploads → finished audits)
- Re-audit rate (one-time → recurring)
- Recommendation follow-through (audit → action taken)
- Cross-product audit rate (health-only users → health+life users)

**Lagging indicators:**
- Beta survey NPS
- Subscription conversion (Phase 6+)
- Concierge tier adoption (Phase 6+)

**Anti-metrics (avoid optimizing for these):**
- Volume of policies "switched" through Kavachly (compromises neutrality)
- Engagement time on dashboard (we're an audit tool, not a social product)
- Number of features shipped (we ship for outcomes, not for shipping)

---

## 11. Strategic Differentiation

| Competitor | What they are | Why they don't replace us |
|-----------|---------------|--------------------------|
| PolicyBazaar | Sales-driven aggregator | Sells policies; sorts by price; structural commission incentive |
| Coverfox / InsuranceDekho | Same as PolicyBazaar | Same |
| Ditto Insurance | Advisor-led, human-driven | Doesn't scale beyond human throughput |
| ChatGPT / Claude | Generic AI | No PDF fidelity, no wordings DB, no Indian benchmarks, no accountability |
| Deloitte / Big 4 | Statutory audits of insurance companies | Different customer (insurers), B2B, ₹50K+/hour |
| Insurer apps | Bills, claims | Don't audit if your policy is good |
| Independent advisors | Personal advisors | ₹2,000-5,000/consultation, accessible only to top 5% |

**Our moat:**
1. **Wordings DB** — curated, verified, current. Replicating requires the same QA work.
2. **Indian-context benchmarks** — CSR data, city tier multipliers, ideal-coverage formulas.
3. **Commission neutrality** — structural, not promotional.
4. **Multi-product integration** — health + life in one platform; no competitor does this honestly.
5. **Consumer trust + brand** — takes years to build, defensible once established.

---

## Appendix: Document History

- **2026-05-05:** Initial unified spec post-`insurance-page` review. Both founders' work captured in single document.
- *Future updates here as decisions are made.*
