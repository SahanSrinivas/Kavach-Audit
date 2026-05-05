# Life FY stats pack — QA checklist

Use this before committing a new `data/life/fy-*.json` (built from CSV via `scripts/build_life_fy_json.py`).

## Source traceability

- [ ] Each numeric column is tied to a **named IRDAI or insurer public disclosure** (Annual Report table, Handbook, company disclosure PDF).
- [ ] `sources[].note` in the JSON names the **table / page / section** (not only “IRDAI”).
- [ ] FY key matches the reporting period (e.g. `2023-24` for claims experience published for that year).

## Row sanity

- [ ] Every `id` is **stable** across FY updates (do not rename casually — breaks UI defaults).
- [ ] Ratios are in **percentage points** as stored (e.g. `98.6` means 98.6%), consistent with prior packs.
- [ ] Solvency ratio uses the same **definition** as prior files (regulatory ratio vs requirement).

## Technical

- [ ] Ran `python scripts/ingest_life_stats.py` so `frontend/public/data/life/` matches `data/life/`.
- [ ] Spot-check trust panel in the app: insurer dropdown, FY label, no console errors.

## Sign-off

| Role        | Name | Date |
|-------------|------|------|
| Data entry  |      |      |
| Review      |      |      |
