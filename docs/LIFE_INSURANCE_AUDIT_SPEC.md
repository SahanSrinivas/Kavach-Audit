# Life Insurance Audit — Product & Engineering Spec

**Branch:** `insurance-page` (work continues here; merge to `main` when ready)  
**Status:** FY JSON pipeline + trust panel from public data + PDF extraction (heuristic) + Life Schedule page + landing tab persistence  
**Last updated:** 2026-05-04

## 1. Purpose

Deliver a **commission-neutral life insurance audit** parallel to health: **IRDAI-aligned multi-metric “trust” context** (from ingested FY JSON), then **CIS + policy bond** text extraction to a **Life Schedule**, with optional future overlap to the health audit.

## 2. What ships on this branch

| Item | Description |
|------|-------------|
| **FY stat pipeline** | Source of truth: `data/life/index.json` + `data/life/fy-*.json`. Sync to static hosting: `python scripts/ingest_life_stats.py` → copies into `frontend/public/data/life/`. |
| **Trust panel (UI)** | `LifeAuditStart` loads index + selected FY bundle via `fetch` from `/data/life/...` (`@/lib/lifeStats`). |
| **Backend stats API** | `GET /api/life/stats/index`, `GET /api/life/stats/{fy}` — reads the same JSON files under repo `data/life/` (for apps or debugging). |
| **Extraction API** | `POST /api/life/extract` — multipart `cis` + `bond` (PDF only), optional `insurer_id`. PyMuPDF text + heuristic `extract_life_schedule()` (no LLM). |
| **Life Schedule UI** | `/audit/life/schedule` reads `sessionStorage` key `kavachly_life_schedule_v1` populated after successful extract. |
| **Landing persistence** | `sessionStorage` key `kavachly_landing_audit_tab` stores **Health** vs **Life** tab across refresh. |

## 3. Competitor landscape (typical vs Kavachly)

| Actor | What they usually optimise | What they typically lack | Kavachly (target) |
|-------|---------------------------|--------------------------|-------------------|
| Aggregators | Quotes, conversion | Post-issuance bond/CIS audit; neutral IRDAI context | Issued-policy extraction + multi-metric panel |
| Insurer D2C | Premium pay | Cross-insurer benchmarks | FY packs + definitions in-app |
| Banks / agents | Distribution | Independent CIS decode | Same |

## 4. Regulatory inputs (production data sources)

Per FY JSON pack should cite **IRDAI Annual Report** / **Handbook on Indian Insurance Statistics** / **insurer public disclosures**. Replace placeholder narrative in `fy-*.json` `sources[]` when you paste real scrape metadata.

Fields per insurer (current schema): death claim settlement, 30-day settlement, 13th/25th month persistency, solvency ratio.

## 5. Operational checklist (new FY)

1. Add `data/life/fy-YYYY-YY.json` (copy prior FY as template; update numbers + `ingestedAt`).
2. Reference it from `data/life/index.json` → `dataFiles` + `availableFys` + `defaultFy` as needed.
3. Run `python scripts/ingest_life_stats.py` to refresh `frontend/public/data/life/`.
4. Commit **both** `data/life/` and `frontend/public/data/life/` together.
5. Smoke-test trust panel FY selector and disclaimer dates.

## 6. Extraction limitations

- **PDF text layer required** — scanned images need OCR (not in this path).
- **Heuristics** — confidence scores surface in UI; users must verify against originals.
- **No authentication** on `/api/life/extract` today — add rate limits / auth if abused.

## 7. Engineering backlog

1. Grievance normalization + per-lakh metrics when PIF is in the pack.
2. Optional LLM pass for ambiguous bonds (behind feature flag).
3. Persist Life Schedule server-side for logged-in users.
4. Household overlap with health audit (riders vs mediclaim).

## 8. Key files

| Path | Role |
|------|------|
| `data/life/index.json`, `data/life/fy-*.json` | FY packs (source of truth) |
| `frontend/public/data/life/*.json` | Static copies for CRA |
| `scripts/ingest_life_stats.py` | Sync script |
| `frontend/src/lib/lifeStats.js` | Fetch + normalize insurers |
| `frontend/src/pages/LifeAuditStart.jsx` | Trust panel + upload + extract |
| `frontend/src/pages/LifeSchedule.jsx` | Schedule review |
| `backend/services/life/extract_schedule.py` | Heuristic extraction |
| `backend/routers/life_router.py` | Stats + extract routes |
| `backend/tests/test_life_*.py` | Unit + API tests |
