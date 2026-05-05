# Kavachly — Product Vision

**Last updated:** May 4, 2026  
**Status:** Pre-beta. v0.6.1-preflight tagged on `pdf-parser` branch.  
**Owner:** Sahan Kolluri

This is the one-stop document for what Kavachly is, why it exists, what gaps 
it fills, and how we get from here to a real product. Roadmap below is 
sequenced — phases build on each other. Don't skip ahead.

---

## 1. What Kavachly Is

**Kavachly is the audit layer for Indian household insurance.**

Tagline: *"Insurance, audited."*

We translate dense insurance policy documents into structured, honest 
assessments of what users actually have, what they're missing, and what 
will happen when they file a claim. We're commission-neutral, AI-powered, 
and built specifically for the Indian market.

**Who we're for:** Indian households with one or more insurance policies 
(health, term life, motor) who suspect their coverage may not be what they 
think it is.

**Who we're not for:** Insurance companies (we're not a B2B audit firm), 
agents (we don't replace them), or users looking to buy their first policy 
(we audit what you have; aggregators sell what you don't).

---

## 2. The Six Gaps Kavachly Fills

These are the structural problems in Indian insurance that Kavachly addresses. 
Pick 2-3 for landing-page positioning; rotate over time.

### Gap 1 — "I have insurance, am I actually covered?"

90 million Indian households have health insurance. Most have no idea what 
their policy actually covers until they file a claim. By then, room rent 
caps, sub-limits, PED waiting periods, and proportionate deductions hit them 
at the worst possible moment.

**Kavachly translates the 50-page wording into "here's what will happen 
when you claim."**

### Gap 2 — "I trust my agent"

Indian insurance distribution runs on commission. Your agent earns more by 
selling you a more expensive policy, or a different policy at renewal — not 
by telling you your current one is fine. Every "advisor" in the system has 
structurally misaligned incentives.

**Kavachly is commission-neutral.** The audit is honest because we don't 
make money on what you do next.

### Gap 3 — "I can't compare apples to apples"

Sum insured ₹10L from HDFC ERGO ≠ sum insured ₹10L from Star Health ≠ sum 
insured ₹10L from Niva Bupa. Different room rent rules, different PED 
waiting, different sub-limits, different CSR.

Aggregator sites like PolicyBazaar sort by price because it's the only field 
directly comparable. **Kavachly's wordings DB makes the actual coverage 
comparable.**

### Gap 4 — "I don't know what good looks like"

A 32-year-old in Mumbai with ₹15L income — what's the right sum insured? 
Is ₹18,500 a reasonable premium? Should PED waiting be 2 years or 3? Most 
users have no benchmark.

**Kavachly encodes Indian-context benchmarks** — city tier multipliers, 
income-based ideal coverage, IRDAI claim settlement ratios, peer-percentile 
comparisons — so users see their position in context.

### Gap 5 — "I bought it once and forgot"

Insurance isn't set-and-forget. Coverage gaps emerge with life events 
(marriage, kids, parents aging, home purchase). Policies change at renewal. 
New products launch. Most households audit their insurance once a decade — 
when something goes wrong.

**Kavachly's renewal negotiator and life-event re-audit make it 
continuous** (Phase 3+).

### Gap 6 — "ChatGPT can do this"

Generic AI gives generic advice on stale training data. No PDF parsing 
fidelity, no benchmark data, no wordings DB, no accountability, no 
persistence. **Kavachly is the vertical specialization layer** — Indian 
insurance domain knowledge encoded as deterministic rules, current data, 
structured outputs.

ChatGPT is your friend who knows insurance. Kavachly is the audit.

---

## 3. The Claim Rejection Opportunity

Three different products live under "claim rejection." Each has different 
costs, risks, and timing. Build them in order C → A → B.

### Interpretation A — Pre-flight Claim Check

User is about to file a claim. Before they submit, Kavachly walks through 
their specific policy's rules and warns them:

- "Your room rent cap is ₹5,000. The hospital you're at charges ₹12,000. 
  Expect 40-60% proportionate deduction."
- "This is for a knee replacement. Your policy has a 24-month waiting 
  period for orthopedic procedures. Have you had this policy for 24+ months?"
- "Get pre-authorization within 24 hours of admission."
- "Keep these specific documents: discharge summary, original bills, 
  investigation reports, prescription history."

**Type:** Claim prevention.  
**Build complexity:** Medium.  
**Dependencies:** Phase 1.5 wordings DB, Phase 2 comparison engine.  
**When:** Phase 3.

### Interpretation B — Automated Claim Filing/Appeals

User had a claim rejected. Kavachly automatically generates the appeal 
letter, files it with the insurer, follows up, escalates to IRDAI ombudsman 
if needed.

**Type:** Claim resolution (acting on user's behalf).  
**Build complexity:** Very high.  
**Dependencies:** Legal/regulatory expertise, document handling, possibly 
licensed authorization to act on user's behalf, direct insurer relationships.  
**When:** Phase 4+ Insurance CFO concierge tier. Possibly never as a 
self-serve product.

### Interpretation C — Claim Rejection Analyzer ⭐

User uploads their rejection letter. Kavachly:

1. Explains why it was rejected in plain language ("Your insurer is 
   invoking Sub-clause 4.3, which says...")
2. Evaluates whether the rejection is legitimate or appealable based on the 
   user's specific policy wording
3. Generates a structured appeal template the user can file themselves
4. Provides escalation paths (insurer's grievance redressal officer → 
   IRDAI ombudsman) with timelines and required documents

**Type:** Claim analysis + self-service appeal support.  
**Build complexity:** Medium-high.  
**Dependencies:** Phase 1.5 wordings DB.  
**When:** Phase 3 (likely the most strategic single feature in Phase 3).

**Why C is the killer feature:** Differentiated, high-emotional-value, 
defensible, no licensing required, no insurer integration required. "Helped 
10,000 Indians overturn wrongful claim rejections" is exactly the proof 
point that builds Indian consumer trust faster than any audit feature.

---

## 4. Roadmap — Phased Implementation

Each phase has explicit success criteria. Don't move to the next phase 
until the current phase's criteria are met.

### Phase 0 — Foundation (DONE as of v0.6.1-preflight)

**Status:** Shipped.

- ✅ PDF parser (Claude-powered, with preflight gatekeeper)
- ✅ Audit engine (deterministic, sub-millisecond runtime)
- ✅ Scoring system: Coverage, Cost, Claim Readiness, Gap
- ✅ Wordings DB infrastructure (Phase 1.5 prep)
- ✅ Multi-policy support with nicknames
- ✅ Dashboard with portfolio + per-policy detail views
- ✅ 539 backend tests passing, mypy strict clean
- ✅ Real friend PDF dogfood pending (Sunday)

### Phase 1 — Real-World Validation (current week)

**Goal:** Confirm the engineered product works on real user data.

**Tasks:**
1. Real Session 2 dogfood with 3 friend PDFs (USE_MOCKS=false)
2. Bug triage and fixes (critical + high severity only)
3. Update DOGFOOD_NOTES.md with real numbers, real findings, real bugs

**Success criteria:**
- Parser succeeds on 3 of 3 real friend PDFs
- Audit produces sensible scores (no obviously-wrong outputs)
- ≤5 critical bugs surfaced; all fixed within the week
- Dashboard renders correctly with real multi-policy data

**Time budget:** 4-6 days.

**If failing:** Stop and fix the engine. Don't move to Phase 1.5 with a 
broken parser.

### Phase 1.5 — Wordings DB Population + Integration (week 2)

**Goal:** Schedule-only uploads produce full audits via wordings lookup.

**Tasks:**
1. Manually QA-parse 10 priority wordings via CLI scripts:
   - HDFC ERGO Optima Restore
   - Niva Bupa ReAssure
   - Star Health Comprehensive
   - Care Supreme
   - ICICI Lombard Complete Health
   - Max Bupa Health Companion
   - Aditya Birla Activ Health
   - ManipalCigna ProHealth
   - Tata AIG MediCare
   - New India Assurance Mediclaim
2. Build `policy_merger.py` and integrate into `policies_router`
3. Schedule-required UX (gracefully request schedule when only wording 
   uploaded)
4. End-to-end test: upload schedule alone, get full audit using merged 
   wording rules

**Success criteria:**
- 10 verified wordings in production DB
- Schedule-only upload flow works end-to-end
- Audit quality matches schedule+wording uploads
- Comparison foundation in place for Phase 2

**Time budget:** 7-10 days. Bottleneck is manual wording QA (founder time, 
not delegable).

### Phase 2 — Comparison Engine (weeks 3-5)

**Goal:** Answer "should I switch?" honestly.

**Tasks:**
1. Build comparison service:
   - Input: user's profile (age, city, income, family) + current policy
   - Output: ranked list of alternative policies with structured trade-offs
2. Honest "stay with current" recommendations when switching doesn't help
3. Side-by-side comparison UI in dashboard
4. Specific reasoning per recommendation ("Care Supreme is cheaper but PED 
   waiting is 24 months — bad if you have diabetes")

**Success criteria:**
- 30+ wordings in DB (post-Phase 1.5 manual QA expansion)
- Comparison runs against full DB in <2s
- 70%+ of users say recommendations feel "honest, not salesy" in beta 
  surveys

**Strategic note:** This is the moat vs PolicyBazaar (sales-driven) and 
Ditto (advisor-led, doesn't scale). When this ships, Kavachly stops being 
"audit my one policy" and becomes "audit my situation."

**Time budget:** 14-21 days.

### Phase 2.5 — Beta Launch (week 6)

**Goal:** First real users, in production, on real infrastructure.

**Tasks:**
1. GCP deployment to asia-south1 (Mumbai region)
   - Backend: FastAPI on Cloud Run
   - Frontend: React + nginx on Cloud Run
   - DB: MongoDB Atlas M0 free tier (M10 ~₹5K/mo at 5K-10K users)
   - Secrets: GCP Secret Manager
2. MSG91 SMS integration (DLT compliance, Indian deliverability)
3. Cloudflare DNS + custom domain (kavachly.com)
4. Sentry + UptimeRobot monitoring
5. Beta waitlist + invite flow (20-50 users initially)

**Success criteria:**
- Production stable for 7 days
- 30+ beta users completed audits
- ≤5 critical bugs in beta
- p95 audit response time <60s including parser

**Time budget:** 5-7 days infrastructure + ongoing beta operations.

### Phase 3 — Recurring Engagement (months 2-3)

**Goal:** Turn one-time audit into recurring product. This is where 
monetization unlocks.

**Tasks (in priority order):**

#### 3a. Claim Rejection Analyzer (Interpretation C above)
The killer feature. User uploads rejection letter, system evaluates 
legitimacy, generates appeal template, provides escalation paths.

#### 3b. Renewal Negotiator
60 days before policy expires:
- Re-audit current policy against latest market
- Identify gaps that have emerged in the last year
- Generate negotiation script for renewal call
- Suggest alternatives with structured comparison

#### 3c. Life Event Re-audit
Triggered manually or by user-reported events:
- "Just had a baby" → re-audit household coverage with new dependent
- "Bought a house" → flag home insurance gap, term life adequacy review
- "Parents moved in" → re-audit health coverage for senior citizen needs
- "Got married" → joint cover analysis, term life beneficiary update

#### 3d. Pre-flight Claim Check (Interpretation A above)
Before user files a claim:
- Walk through their specific policy's rules
- Warn about caps, waiting periods, deductions
- Generate documentation checklist
- Pre-auth reminder

#### 3e. Policy Memory
- 5-year history of audits, claims, renewals
- Year-over-year coverage drift visualization
- "What changed at last renewal" summary

**Monetization:**
- Free tier: One audit per quarter, basic dashboard
- Subscription: ₹999-2,499/year for renewal negotiator, life event 
  re-audit, claim rejection analyzer, priority parsing
- Concierge tier (Phase 4): ₹9,999-19,999/year for human-assisted claim 
  appeals, multi-product household management

**Success criteria:**
- 30%+ of free users convert to subscription within 6 months
- Renewal negotiator drives ≥1 user-reported "saved money on renewal" 
  testimonial per week
- Claim rejection analyzer used by 100+ users in first 3 months

**Time budget:** 8-10 weeks.

### Phase 4 — Insurance CFO (months 4-6)

**Goal:** Become the trusted financial advisor for Indian households' 
entire insurance footprint.

**Tasks:**
1. Multi-product household coverage:
   - Health (current strength)
   - Term life
   - Motor (auto)
   - Home
   - Travel (situational)
   - Personal accident
2. Annual review cycle (automated reminders, scheduled re-audits)
3. Concierge tier:
   - Human-assisted claim filing (Interpretation B, manually)
   - Disputed claim escalation to IRDAI ombudsman
   - High-value claim advocacy (>₹5L)
4. Family financial planning integration (term life adequacy ↔ income, 
   liabilities, dependents)

**Success criteria:**
- 50%+ of subscription users have 2+ product types covered
- Concierge tier serves 100+ users per month
- "Insurance CFO" brand resonates in beta surveys

**Strategic note:** This is when Kavachly stops being "an audit tool" and 
becomes "the trusted financial advisor for Indian households." 
Differentiation from Ditto sharpens here — Ditto is human-led at small 
scale; Kavachly is AI-led at large scale with human concierge for 
high-stakes moments.

**Time budget:** 8-12 weeks.

### Phase 5+ — Expansion (year 2)

**Geographic expansion:**
- Markets with similar agent-mediated insurance dynamics:
  - Indonesia
  - Philippines
  - Vietnam
  - Egypt
  - Mexico
- Same playbook: vertical specialization layer + commission-neutral audit

**Vertical expansion:**
- Mutual funds (audit fund choices vs goals)
- Credit cards (audit fee structures, reward optimization)
- Home loans (audit interest rates, refinance opportunities)
- Same "honest audit" framework applied to other financial products

**Distribution expansion (B2B2C):**
- Banks integrate Kavachly's audit engine for their customers' insurance 
  cross-sell
- Employers offer Kavachly audits as employee benefits
- Independent financial advisors use Kavachly as their analytical layer

**Time budget:** 12-18 months. Don't plan beyond directional bets.

---

## 5. What We're NOT Building

Explicit non-goals to prevent scope creep:

- **B2B insurance company audits** (that's Deloitte's territory)
- **Insurance sales / brokerage** (we'd lose commission-neutrality)
- **Direct claim filing on user's behalf** until Phase 4 concierge tier
- **Generic financial planning** (insurance audit is the wedge)
- **Insurance company partnerships that compromise audit honesty**
- **Crypto, NFTs, gamification, or other 2021-era tech distractions**

---

## 6. Strategic Differentiation Summary

| Competitor | What they are | Why they don't replace us |
|-----------|---------------|--------------------------|
| PolicyBazaar | Sales-driven aggregator | Sells policies; sorts by price (the only directly comparable field). Structural commission incentive. |
| Coverfox / InsuranceDekho | Same as PolicyBazaar, smaller | Same structural incentive. |
| Ditto Insurance | Advisor-led, human-driven | Doesn't scale beyond human throughput. Charges per advisory call. We're AI-led at scale, free for basic. |
| ChatGPT / Claude | Generic AI | No PDF fidelity, no wordings DB, no Indian benchmarks, no accountability, no persistence. |
| Deloitte / Big 4 | Statutory audits of insurance companies | Different customer (insurers), different audit type, ₹50K+/hour pricing. |
| AetherLabs (Flow) | B2B SaaS for insurance agents | Different ICP. Sells to agents; we serve consumers. |
| Independent financial advisors | Personal advisors | ₹2,000-5,000/consultation, accessible only to upper middle class. We're for the 95%. |

**Our moat:**
1. **Wordings DB** — curated, verified, current. Replicating requires the 
   same QA work.
2. **Indian-context benchmarks** — CSR data, city tier multipliers, 
   ideal-coverage formulas. Not in general training data.
3. **Commission neutrality** — structural, not promotional.
4. **Consumer trust + brand** — takes years to build, defensible once 
   established.

What gets commoditized over time:
- Generic PDF understanding
- Free-form natural language interaction
- Basic "tell me about my insurance" Q&A

What stays defensible:
- The vertical specialization layer on top of AI
- The data assets we curate
- The consumer relationship and brand

---

## 7. Decision Principles

When facing a roadmap decision, ask:

1. **Does this fit the audit positioning?** If we're auditing, we're 
   honest. If we're recommending, the recommendation must be in the user's 
   interest. Anything that compromises this is rejected.

2. **Does this require us to break commission neutrality?** If yes, no.

3. **Does this work for the median Indian household, not just the top 5%?** 
   Premium concierge is fine as a tier; it's not the core product.

4. **Can this be delivered with current technology and reasonable cost per 
   user?** Anything that requires per-user manual labor is concierge tier 
   only.

5. **Does this create more lock-in for users, or more freedom?** Kavachly 
   wins by being trustworthy. Users should feel free to leave; they stay 
   because we're useful.

---

## 8. Open Questions for Future Resolution

- **IRDAI relationship:** Should Kavachly pursue regulatory partnership 
  status? Could be a moat or a constraint. Defer until Phase 4.
- **Insurance company licenses:** Do we need any to operate as we're 
  building? Currently no, but IRDAI rules around "insurance advice" are 
  evolving.
- **Marketplace dynamics:** Phase 2 comparison engine could evolve into a 
  marketplace where users buy through us. That breaks commission 
  neutrality. Decide in Phase 2.
- **B2B2C distribution:** When and which partners? Banks? Employers? 
  Defer until Phase 5.
- **International expansion sequencing:** Indonesia first or Philippines? 
  Don't decide until Phase 5 in clear sight.

---

## 9. North Star Metric

**Primary:** Number of households that trust Kavachly to audit their 
insurance.

**Leading indicators:**
- Audit completion rate (uploads → finished audits)
- Re-audit rate (one-time → recurring)
- Recommendation follow-through (audit → action taken)
- Net Promoter Score in beta surveys

**Lagging indicators:**
- Subscription conversion rate
- Concierge tier adoption
- Multi-product coverage rate (1-product → 2+ products)

**Anti-metrics (avoid optimizing for these):**
- Volume of policies "switched" through Kavachly (compromises neutrality)
- Engagement time on dashboard (we're an audit tool, not a social product)
- "Insurance score" anxiety-driven behavior

---

## Appendix: Document History

- 2026-05-04: Initial vision document. v0.6.1-preflight tagged.
- [Future updates here]