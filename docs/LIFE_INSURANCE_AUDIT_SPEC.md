# Life Insurance Audit — Product & Engineering Spec

**Branch:** `feature/life-insurance-audit`  
**Status:** MVP UI + trust panel + document placeholders (extraction pipeline next)  
**Last updated:** 2026-05-04

## 1. Purpose

Deliver a **commission-neutral life insurance audit** parallel to health: **IRDAI-aligned multi-metric “trust” context**, then **issued-document–grounded** understanding (CIS + policy bond), eventually **Life Schedule** JSON and overlap with the existing health audit.

## 2. What shipped in this iteration

| Item | Description |
|------|-------------|
| Landing | Two tabs: **Health insurance audit** / **Life insurance audit**; CTAs route to `/audit/start` vs `/audit/life/start`. |
| Route | `GET /audit/life/start` → `LifeAuditStart.jsx`. |
| Trust panel | `LifeTrustPanel` + `frontend/src/data/lifeInsurerStats.js` — **illustrative sample rows** for UI; replace with IRDAI ingest (see §6). |
| Documents | Client-side file pickers for CIS + policy bond (filename only in state; **no upload** to backend yet). |
| Continue CTA | Disabled until extraction + downstream audit stages exist. |

## 3. Competitor landscape (typical vs Kavachly)

| Actor | What they usually optimise | What they typically lack | Kavachly (target) |
|-------|---------------------------|--------------------------|-------------------|
| Aggregators (e.g. PolicyBazaar-style) | Quotes, conversion, commissions | Post-issuance **bond/CIS audit**; neutral **multi-metric** IRDAI context | Evidence-led **issued policy** view + trust panel **without** lead-gen |
| Insurer D2C apps | Premium pay, basic policy view | **Cross-insurer** benchmarks; **rider vs health** overlap | Household-level bridge when health audit exists |
| Banks / agents | Distribution | Structured **CIS/bond** decoding independent of incentive | Same |
| Marketing surveys (e.g. IPQ-style) | Awareness PR | **Personal** policy truth | User-specific documents + regulator metrics |

**Positioning:** Aggregators help you **buy**; Kavachly helps you **understand and maintain** what you already hold, with **definitions** and **no commission**.

## 4. Regulatory inputs (production data sources)

Do **not** rely on a single number (health ICR ≠ life economics). Plan to ingest per FY:

- IRDAI **Annual Report** / **Handbook on Indian Insurance Statistics**
- **Death claim settlement** and **timeliness** where disclosed
- **Persistency** (13th / 25th month) — standardized IRDAI methodology
- **Solvency** margin / ratio context
- **Grievances** — prefer **normalized** (e.g. per lakh policies) when PIF available

**Non-regulatory:** “Protection Quotient” style indices are **commercial surveys**, not substitutes for the above.

## 5. Near-term engineering backlog

1. **FY ingest pipeline** — versioned JSON (`life_stats_fy2024.json`) + admin refresh checklist.
2. **PDF extraction** — CIS + policy bond → **Life Schedule** schema (sum assured, term, PPT, riders, exclusions pointers).
3. **Auth optional path** — align with health: anonymous vs logged-in retention rules.
4. **Household integration** — link riders (CI, PA) to health audit for overlap flags.
5. **Enable “Continue to Life Schedule”** when extraction API exists.

## 6. Data disclaimer

`lifeInsurerStats.js` contains **placeholder-style figures** for layout and copy QA. Production deployment **must** replace them with values traced to **IRDAI / insurer public disclosure** and display the **FY label** and **source links** in the UI.

## 7. Files touched (this iteration)

- `frontend/src/pages/Landing.jsx` — tabs + dynamic CTAs + FAQ/footer links  
- `frontend/src/App.js` — `/audit/life/start`  
- `frontend/src/pages/LifeAuditStart.jsx`  
- `frontend/src/components/life/LifeTrustPanel.jsx`  
- `frontend/src/data/lifeInsurerStats.js`  
- `docs/LIFE_INSURANCE_AUDIT_SPEC.md` (this file)
