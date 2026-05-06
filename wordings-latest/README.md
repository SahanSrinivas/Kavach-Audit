# `wordings-latest/` — current policy wordings (batch)

This folder holds **official policy wording PDFs** for the Kavachly reference
portfolio. Files are **not committed** (repo-wide `*.pdf` gitignore).

## Generate

From the repository root, with `requests` installed (see `backend/requirements.txt`):

```bash
python scripts/download_wordings_latest.py
```

- Successful downloads go to `wordings-latest/<insurer_slug>/<plan_slug>.pdf`.
- A run log is written to `wordings-latest/_download_log.txt`.
- If direct HTTP fails (403, timeout), the script can fall back to **Firecrawl**
  when `FIRE_CRAWL` is set in `backend/.env` (same as `scripts/download_wordings.py`).

## What was “fixed” vs the older `wordings/` batch

| Plan | Change in this batch |
|------|----------------------|
| **Star Comprehensive** | Prefer **Star CloudFront** `star-comprehensive-policy-clause-new-1.pdf`, then IRDAI `SHAHLIP22028…` mirror. |
| **Star Senior Citizens Red Carpet** | Prefer IRDAI **`SHAHLIP22040…`** filing, then legacy `SHAHLIP22199…`. *Confirm UIN inside the PDF matches your filing.* |
| **ManipalCigna ProHealth Prime** | Prefer IRDAI **`MCIHLIP23022V032223`**, then Ditto Protect wording S3, then older `MCIHLIP22224…`. |
| **United India Family Medicare** | Prefer **UIIC** `20240311_Policy_Wordings_FMP.pdf` (**UIIHLIP24090V052324** block), then older IRDAI `UIIHLIP22070…`. |
| **Oriental Happy Family Floater** | Prefer **Ditto S3** full policy wording, then older IRDAI `OICHLIP22010…`. |

## Still manual / watch-list

- **OICHLIP25046V062425 (2024-25 “HFF Gold” revision)** — IRDAI Liferay UUID was not
  pinned in automation; when `irdai.gov.in` lists it, add that URL as the first
  entry in `LATEST_TARGETS` for Oriental in `scripts/download_wordings_latest.py`.
- **403 / flaky PSU hosts** — IRDAI mirrors may still be the only stable fetch from
  some networks; re-run from a residential IP or enable Firecrawl.

## Source-of-truth reminder

Always **open the PDF** and verify **UIN + version** in the header/footer before using
in compliance-critical workflows. URLs rotate and insurers file revisions often.
