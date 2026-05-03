# Kavach — Product Requirements Doc

## Original Problem
AI-powered insurance audit platform for India ("Kavach"). Brand promise: "Find out if your insurance is actually protecting you." Commission-neutral, AI-native, 60-second audit. 8 stages from landing → identity → family → money → policies (with PDF parsing) → lifestyle → audit report → recommendations → dashboard.

## Architecture
- **Frontend**: React 19, Tailwind, shadcn/ui, Lucide, Framer Motion, html2canvas, react-router 7. Mobile-first PWA-ready.
- **Backend**: FastAPI + Motor (async MongoDB), bcrypt, PyJWT.
- **Auth**: phone+OTP only. JWT access (1h httpOnly cookie), random+bcrypt refresh (90d, MongoDB sessions), CSRF double-submit cookie.
- **Skeleton mode (`USE_MOCKS=true`)**: all "intelligent" endpoints (PDF parse, audit scoring, recommendations, alerts) return hardcoded fixtures from `/app/backend/mocks/fixtures.py`. Live integrations (Anthropic Claude PDF parse, real audit engine, Riskcovry quote engine, WhatsApp/SendGrid alert dispatch) are deferred for post-export development.

## User personas
- **The newly-employed 28-yr-old**: bought a corporate health plan, doesn't know if it covers their parents.
- **The 35-yr-old parent of two**: 4 LIC policies via uncle, suspects they're overpaying.
- **The 55-yr-old retiree**: nearing renewal, premium hiked 30%.
- **The frustrated diaspora returnee**: wants Western-grade transparency in Indian insurance.

## Implemented (as of 2026-05-03)

### Phase 1 ✅
Stage 0 landing, Stage 1 identity, full OTP+JWT auth, login, dashboard empty state, settings, deep-link `/r/{token}`, admin debug, .env.example, gitignore, JWT_SECRET production guard. 36/36 backend pytest passing.

### Phase 2 ✅ (skeleton-first per user pivot)
- **Stage 2 Family** — 5 chip cards + conditional spouse-age slider, kids segmented control + youngest age, parents mother/father age sliders + multi-select PEC chips
- **Stage 3 Money** — 3 sliders (income log-scale, EMIs, monthly expenses) with live ₹ formatting (lakhs/crores)
- **Stage 4 Policies** — 3 paths: Upload (drag-drop, multi-file, 4s simulated parse with rotating hints, parsed-policy result card), Quick declare (type chips → insurer search → sum/premium sliders), Skip
- **Stage 5 Lifestyle** — 4 yes/no segmented controls + multi-select planned-events chips. Generate triggers 3s loading screen with rotating reassurance, then transitions to audit
- **Stage 6 Audit Report** — 4 colour-coded score cards (green ≥75 / amber 50-74 / red <50), expandable Top 3 findings with Tell-me-more modal + Fix-this CTA, portfolio header (4 stats), coverage-by-type bar chart, "Share my audit" via html2canvas (Web Share API on mobile, download fallback), Re-run audit
- **Stage 7 Recommendations** — 3 ranked cards (Best Match / Lowest Premium / Highest Coverage) with insurer, sum, premium, features, CSR%, fit reason, transparent commission disclosure + direct insurer link, "Buy 1-tap" → Phase-2-coming-soon modal with email capture into `early_access` collection
- **Stage 8 Dashboard** — Portfolio header (4 stats), coverage-by-type bar chart, policies list with red-flag badges, alerts inbox (3 mocked alerts → renewal, life event, re-audit), Add household member modal (persists to `family_members`), Re-run audit CTA

### Mocked endpoints (all in skeleton mode)
- `POST /api/policies/upload` → 4s sleep + `make_mock_parsed_policy()` (HDFC ERGO Optima, ₹15L, ₹22,400 premium, room-rent cap ₹5,000, co-pay 10%, PED 3y, 3 sub-limits) — TODO(claude-api)
- `POST /api/policies/declare` + `GET /api/policies` + `DELETE /api/policies/{id}`
- `POST /api/audit/generate` + `GET /api/audit/latest` → fixed scores 62/78/41/54, 3 findings, portfolio summary — TODO(audit-engine)
- `GET /api/recommendations` → 3 fixed cards — TODO(real-quotes)
- `POST /api/recommendations/early-access` (real persistence)
- `GET /api/alerts` + `POST /api/alerts/{id}/read` → 3 hardcoded alerts seeded on first read
- `POST /api/family/members` + `GET /api/family/members`

## TODO markers (post-GitHub export)
| File | Tag | What |
|---|---|---|
| `/app/backend/routers/policies_router.py` | `TODO(claude-api)` | Replace `_parse_pdf_with_claude` stub with real `anthropic.AsyncAnthropic` call using `claude-sonnet-4-*` and base64 PDF document content blocks. Rate-limit and parse_failures collection are already wired. Cache by SHA256 already wired. |
| `/app/backend/routers/audit_router.py` | `TODO(audit-engine)` | Build `/backend/services/audit.py` with Coverage/Cost/Claim-Readiness/Gap scoring per spec. |
| `/app/backend/routers/recommendations_router.py` | `TODO(real-quotes)` | Riskcovry (or equivalent) quote engine integration. Personal info collection endpoint for the chosen quote. |
| `/app/backend/routers/alerts_router.py` | `TODO(alert-triggers)` | Renewal cron (T-60d), life-event watcher, annual re-audit cron, WhatsApp Business API + SendGrid delivery. |

## Skipped per user instruction
- Real Anthropic Claude integration (no SDK installed; key blank in `.env`)
- Real audit scoring engine
- Background scheduler / alert triggers / WhatsApp / email
- Iterative testing-agent runs (user will smoke-test post-export)

## UI areas needing polish (out of scope for skeleton)
- The "Made with Emergent" preview badge — Emergent overlay, not app code
- Insurer logos are placeholder building icons
- Stage 2 PEC chips don't yet validate against parsed parent age cohort
- Stage 4 declared-policies don't yet support edit/delete inline (only via dashboard delete in Phase 3+)
- Stage 7 commission disclosure line shows a synthesized direct-link (`<insurer>.com`) — replace with curated URL table
- Share-card layout could be richer (currently shares just the 4 score cards)

## Backlog beyond this build
- PWA manifest + service worker
- Replace mocked alerts with seeded short-token rows so the deep-link flow can be exercised end-to-end
- Household-aggregate audit + per-member policy mapping
- Re-audit history + score-over-time chart
- Annual re-audit nudge email
