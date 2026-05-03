# Kavach — Product Requirements Doc

## Original Problem
AI-powered insurance audit platform for India ("Kavach"). Brand promise: "Find out if your insurance is actually protecting you." Commission-neutral, AI-native, 60-second audit. 8 stages from landing → identity → family → money → policies (with PDF parsing) → lifestyle → audit report → recommendations → dashboard.

## Architecture
- **Frontend**: React 19, Tailwind, shadcn/ui, Lucide, Framer Motion, react-router 7. Mobile-first PWA-ready.
- **Backend**: FastAPI + Motor (async MongoDB), bcrypt, PyJWT, anthropic (Phase 2).
- **Auth**: phone+OTP only. JWT access (24h httpOnly cookie), random+bcrypt refresh (90d, MongoDB sessions), CSRF double-submit cookie.
- **Storage**: MongoDB collections — users, sessions, otp_attempts, policies, audits, alerts, recommendations.

## User personas
- **The newly-employed 28-yr-old**: bought a corporate health plan, doesn't know if it covers their parents.
- **The 35-yr-old parent of two**: has 4 LIC policies via uncle, suspects they're overpaying.
- **The 55-yr-old retiree**: nearing renewal, premium hiked 30%, looking for alternatives.
- **The frustrated diaspora returnee**: wants Western-grade transparency in Indian insurance.

## Core requirements (static)
- Indian ₹ formatting (lakhs/crores)
- Mobile-first, PWA-installable
- 60-second flow target
- Commission-neutral framing — never push purchase before audit

## Implemented (as of 2026-05-03)
### Phase 1 ✅ COMPLETE
- Stage 0 landing hook (`/`) — hero, single CTA, navy→teal gradient, brand voice copy
- Stage 1 identity (`/audit/identity`) — age stepper, city auto-detect (Nominatim) + manual search of 50 cities, +91 mobile + OTP, paste-strips +91 prefix
- Authentication: `/api/auth/request-otp`, `/api/auth/verify-otp` (replay-guard, wrong→401, lock 423 after 5/10min, rate-limit 3/hr), `/api/auth/refresh` (with rotation), `/api/auth/logout`, `/api/auth/logout-all`, `/api/auth/sessions`, `/api/auth/sessions/{id}` revoke. CSRF double-submit on all mutations.
- `/login` return-visit screen with `?next=` redirect
- `/dashboard` empty-state for new users + protected route guard
- `/dashboard/settings` — current mobile + active sessions list + revoke + logout-all
- `/r/{token}` deep-link resolver — handles authed/unauthed/invalid
- `/api/admin/users` Bearer-gated debug endpoint
- `/api/health` (db status), `/api/version`
- 6-dot sticky progress bar component (used Stage 1; Stages 2-6 pending)
- 36/36 backend pytest passing, frontend Playwright validated

## Backlog
### Phase 2 (next)
- Stage 2 — Family snapshot (chip cards, conditional follow-ups)
- Stage 3 — Money snapshot (3 sliders)
- Stage 4 — Existing Policies (Upload + Claude PDF parse / Quick declare / Skip)
- Stage 5 — Lifestyle quickfire (5 yes/no chips)
- "Save and continue later" snapshot per stage

### Phase 3
- Stage 6 — Audit Report (4 score cards, top 3 findings, portfolio summary)
- /backend/services/audit.py — Coverage / Cost / Claim-Readiness / Gap scoring engines
- Shareable audit image card (WhatsApp/Twitter)
- Anthropic Claude (claude-sonnet-4) for finding explanations

### Phase 4
- Stage 7 — Recommendations (3 cards: Best/Cheapest/Highest, mocked purchase)
- Stage 8 — Continuous Engagement dashboard (alerts inbox, household, renewal nudges)
- WhatsApp/email mocked alert dispatch
- PWA manifest + service worker

## Deferred (waiting on user)
- ANTHROPIC_API_KEY (user will provide before Phase 2)
- MSG91/Twilio SMS/WhatsApp integration (currently mocked, OTP=123456)
- Riskcovry quote engine (Phase 4 stub now)
