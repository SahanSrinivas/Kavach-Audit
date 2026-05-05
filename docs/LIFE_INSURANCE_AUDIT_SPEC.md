# Life Insurance Audit — Product & Engineering Spec

**Branch:** `insurance-page` (merge to `main` when ready)  
**Status:** Trustworthy MVP slice — FY CSV→JSON pipeline, OCR-aware PDF text, rate limits, Mongo persistence (logged-in), field-confidence UX  
**Last updated:** 2026-05-04

## 1. Purpose

Deliver a **commission-neutral life insurance audit** parallel to health: **IRDAI-aligned multi-metric “trust” context** (from ingested FY JSON), then **CIS + policy bond** extraction to a **Life Schedule**, with optional future overlap to the health audit.

## 2. What ships

| Item | Description |
|------|-------------|
| **FY stat pipeline** | Source of truth: `data/life/index.json` + `data/life/fy-*.json`. Build from CSV: `python scripts/build_life_fy_json.py --fy YYYY-YY --csv path/to.csv`. Sync to CRA static: `python scripts/ingest_life_stats.py`. QA: `docs/LIFE_STATS_QA_CHECKLIST.md`. |
| **Trust panel** | `LifeAuditStart` loads `/data/life/...` via `@/lib/lifeStats`. |
| **Backend stats** | `GET /api/life/stats/index`, `GET /api/life/stats/{fy}`. |
| **Extract** | `POST /api/life/extract` — PDFs only; PyMuPDF text + **OCR fallback** (pytesseract; requires **Tesseract** system binary). Heuristic `extract_life_schedule()` + **`fieldConfidenceUi`** for the UI. |
| **Rate limits** | Sliding window per IP on `/extract` (default **12/min**, env `LIFE_EXTRACT_RATE_PER_MIN`). Set `DISABLE_RATE_LIMIT=true` for local tests. |
| **Persistence** | `POST /api/life/schedules` (auth + CSRF) saves a schedule. `GET /api/life/schedules`, `GET /api/life/schedules/{id}`. Collection: `life_schedules`. |
| **Life Schedule UI** | Per-field confidence badges; `?id=` loads saved doc for logged-in users; else `sessionStorage` `kavachly_life_schedule_v1`. |
| **Landing tab** | `kavachly_landing_audit_tab` in `sessionStorage`. |

## 3. OCR / deployment

- **Python:** `pytesseract`, `Pillow` (see `backend/requirements.txt`).
- **System:** install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (`brew install tesseract` on macOS, `apt install tesseract-ocr` on Debian). If Tesseract is missing, OCR is skipped; text-layer PDFs still work.

## 4. Competitor landscape (short)

| Actor | Gap we address |
|-------|----------------|
| Aggregators | Post-issuance truth, not quote funnels |
| Insurer D2C | Cross-insurer FY context + document decode |

## 5. Operational checklist (new FY from IRDAI tables)

1. Paste numbers into a CSV from `data/life/source_templates/insurers_fy_template.csv` (add rows for all insurers).
2. `python scripts/build_life_fy_json.py --fy 2024-25 --csv your.csv --note "IRDAI AR table …"`.
3. Update `data/life/index.json` (`dataFiles`, `availableFys`, `defaultFy`).
4. `python scripts/ingest_life_stats.py`.
5. Follow `docs/LIFE_STATS_QA_CHECKLIST.md` and commit `data/life/` + `frontend/public/data/life/`.

## 6. Extraction limitations

- OCR quality depends on scan DPI and Tesseract; users should **verify** low-confidence fields (badges in UI).
- `/extract` remains **public** but **rate-limited**; persistence requires **login**.

## 7. Engineering backlog

1. Grievance normalization (per lakh PIF).
2. Optional LLM pass when confidence &lt; threshold.
3. Household overlap with health audit (riders).

## 8. Key files

| Path | Role |
|------|------|
| `scripts/build_life_fy_json.py` | CSV → `fy-*.json` |
| `scripts/ingest_life_stats.py` | Copy `data/life/` → `frontend/public/data/life/` |
| `backend/services/life/pdf_text.py` | Text + OCR |
| `backend/services/rate_limit.py` | Extract rate limit |
| `backend/services/life/extract_schedule.py` | Heuristics + `fieldConfidenceUi` |
| `backend/routers/life_router.py` | Stats, extract, schedules |
| `frontend/src/pages/LifeSchedule.jsx` | Confidence badges |
