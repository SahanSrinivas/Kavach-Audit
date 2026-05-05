# Deploying life audit features

This note covers **OCR**, **optional Redis-backed rate limits**, and **optional LLM refinement** for `/api/life/extract`.

## Tesseract (scanned PDFs)

Text extraction falls back to OCR when embedded text is missing. The runtime needs the **Tesseract** binary (PyMuPDF + `pytesseract` call into it).

- **Debian / Ubuntu (Docker-friendly)**

  ```bash
  apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-eng
  ```

- **macOS (local)**

  ```bash
  brew install tesseract
  ```

- **Dockerfile snippet** (adjust base image as needed):

  ```dockerfile
  RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
  ```

Ensure `tesseract` is on `PATH`. Set `TESSDATA_PREFIX` only if you use a non-default tessdata location.

## Shared rate limits (multi-instance)

`LIFE_EXTRACT_RATE_PER_MIN` (default `12`) limits `/api/life/extract` per client IP. The limiter is applied as a route dependency; the dependency function must use a `Request` type annotation (see `services/rate_limit.py`) so FastAPI does not treat the parameter as a query string field.

- **Without `REDIS_URL`**: an in-memory sliding window applies **per process** — not shared across replicas.

- **With `REDIS_URL`**: a fixed-window counter per UTC minute is stored under keys like `kavach:life_extract:{ip}:{minute}` so all workers share the same budget.

Optional bypass for emergencies:

- `DISABLE_RATE_LIMIT=true`

Python dependency: `redis` is listed in `backend/requirements.txt`.

## Optional LLM refinement

When heuristic extraction confidence is low, you can enable an Anthropic text call to suggest field values (merged only where the heuristic is below a threshold).

| Variable | Purpose |
|----------|---------|
| `LIFE_EXTRACT_LLM_FALLBACK` | `true` / `1` / `yes` to enable |
| `LIFE_EXTRACT_LLM_THRESHOLD` | Trigger LLM when overall heuristic confidence is **below** this (default `0.45`) |
| `LIFE_EXTRACT_LLM_MERGE_THRESHOLD` | Replace heuristic fields when per-field confidence is **below** this (default `0.45`) |
| `ANTHROPIC_API_KEY` | Required when fallback is on |
| `LIFE_LLM_MODEL` | Model id (default `claude-3-5-haiku-20241022`) |

If the API key or package is missing, extraction still succeeds using heuristics only.

## Production rollout checklist

1. **Secrets manager / environment**
   - Set `REDIS_URL` for shared limits across replicas.
   - Set `ANTHROPIC_API_KEY` only if enabling LLM fallback.
   - Set `LIFE_EXTRACT_LLM_FALLBACK=true` only after validating cost and quality in staging.
2. **Runtime image**
   - Install `tesseract-ocr` (and language packs) in the backend image.
   - Keep `pytesseract` + `Pillow` in Python requirements (already present).
3. **Staging validation**
   - Upload at least one scanned PDF and one text PDF.
   - Confirm `/api/life/extract` returns 200 for both.
   - Confirm rate limiting is shared by issuing requests from two app instances with the same client IP.

### Example deployment env block

```bash
REDIS_URL=redis://redis:6379/0
LIFE_EXTRACT_RATE_PER_MIN=12
LIFE_EXTRACT_LLM_FALLBACK=true
LIFE_EXTRACT_LLM_THRESHOLD=0.45
LIFE_EXTRACT_LLM_MERGE_THRESHOLD=0.45
LIFE_LLM_MODEL=claude-3-5-haiku-20241022
```

## Runtime monitoring hooks

- `services/rate_limit.py` now exposes counters via `rate_limit_metrics_snapshot()` and logs blocked requests with rate-limit state.
- `services/life/llm_schedule.py` now tracks `attempted/used/skipped/api_errors/bad_json` via `llm_metrics_snapshot()` and logs successful usage.
- `routers/life_router.py` includes these snapshots in extract-path logs (`life.extract.ok` and `life.extract.llm_skipped_or_failed`) for operational visibility.

## Grievance metric in FY JSON

Insurer bundles built via `scripts/build_life_fy_json.py` support an optional CSV column **`grievancesPerLakhPolicies`**. When present in JSON, the trust panel shows **Grievances (per lakh policies)** for that insurer row.
