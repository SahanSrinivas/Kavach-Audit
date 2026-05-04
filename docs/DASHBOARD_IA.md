# Dashboard IA — post-audit home screen

Information architecture for the post-audit dashboard. Grounds every design
decision in the data that `/audit/latest` and `/policies` actually return
today, and flags the small backend follow-ups needed to ship the redesign
without inventing fake data.

Scope: the screen at [frontend/src/pages/Dashboard.jsx](../frontend/src/pages/Dashboard.jsx)
(route `/dashboard`). Not the audit report (Stage6Audit) or recommendations
(Stage7Recommendations) — both are linked from here but redesigned separately.

---

## 1. Current state — what the API gives us today

### 1.1 Endpoint inventory

| Endpoint | Returns | Used by Dashboard today |
|---|---|---|
| `GET /audit/latest` | `{audit: AuditResult \| null}` | Yes — drives every "filled" zone |
| `GET /policies` | `{policies: Policy[]}` | Yes — policies list |
| `GET /alerts` | `{alerts: Alert[]}` | Yes — inbox |
| `POST /audit/generate` | `{audit: ...}` | Yes — re-audit CTA |
| `POST /family/members` | `{member: ...}` | Yes — add household member |

No new endpoints required for v1 of the redesign. Two enrichments noted in
§1.4 are nice-to-haves, not blockers.

### 1.2 `audit` shape (real engine — `AuditResult` dataclass)

Source: [backend/services/audit/types.py:189-200](../backend/services/audit/types.py#L189-L200).

```
AuditResult {
  id:            str
  user_id:       str
  scores:        { coverage, cost, claim_readiness, gap }   # each int 0-100 OR None
  findings:      Finding[]            # top 3, ranked
  all_findings:  Finding[]            # full ranked list
  portfolio:     PortfolioSummary
  breakdowns:    { coverage, cost, claim_readiness, gap }   # ScoreBreakdown each
  data_version:  str                  # e.g. "wordings-2026.04"
  engine_ms:     int
  generated_at:  str (ISO)
}

Finding {
  id, severity ("red"|"amber"|"info"), type, icon,
  headline, explanation, action,
  score_impact, related_policy_id, cta, recommendation,
  user_proximity, actionability
}

ScoreBreakdown {
  value: int|None, label: str, details: dict
}

PortfolioSummary {
  total_cover, total_premium, active_policies, next_renewal,
  by_type: PortfolioRow[]
}

PortfolioRow { type, current, ideal, ratio }   # ratio is 0-100, capped
```

### 1.3 `policy` shape (per-row)

Source: [backend/services/audit/types.py:89-134](../backend/services/audit/types.py#L89-L134) +
the storage shape from [backend/routers/policies_router.py:103-189](../backend/routers/policies_router.py#L103-L189).

```
Policy {
  id, type, insurer,
  sum_insured: int|None,        # None for wording-only PDFs
  premium:     int|None,        # None for wording-only PDFs
  policy_name, policy_number,
  start_date, end_date,
  parsed_fields: {              # flat shape, engine-readable
    room_rent_cap, icu_cap, copay_percent, ped_waiting_years,
    sub_limits: [{type, cap}], permanent_exclusions: [...],
    network_hospitals, restoration_benefit, ncb_percent, ...
  } | null,                     # null for declared policies
  source: "upload"|"declared",
  is_employer_group: bool,
  policy_nickname: str|None,    # NEW (v0.5.2) — null on first upload
  parser_mode: "real"|"mock",
  parser_output: {...},         # rich shape, frontend ignores
  created_at: ISO
}
```

### 1.4 Gaps — flagged for explicit triage

Each item below is something the redesign would benefit from. **B = backend
fix needed; F = workaroundable in frontend; D = divergence to repair.**

| # | Gap | Class | Resolution |
|---|---|---|---|
| 1 | `make_mock_audit` omits `breakdowns`, `all_findings`, `data_version`, `engine_ms` | D | Backfill the mock fixture so `USE_MOCKS=true` returns the same shape as the real engine. ~10 lines in [backend/mocks/fixtures.py](../backend/mocks/fixtures.py). Without this, any dashboard work that touches breakdowns or the full findings list looks broken in dev. |
| 2 | `Finding.related_policy_id` exists but mock fixture leaves it null | D | Same fixture file — add `"related_policy_id": "<seeded policy id>"` on the room-rent finding so per-policy chips render in dev. |
| 3 | "Underinsured by ₹X" per type | F | Compute on frontend: `max(0, row.ideal - row.current)`. No backend change. |
| 4 | Per-policy red-flag count | F | Filter `audit.findings.filter(f => f.related_policy_id === policy.id)`. Replaces the brittle `parsed_fields?.sub_limits?.length` proxy currently used at [Dashboard.jsx:320](../frontend/src/pages/Dashboard.jsx#L320). |
| 5 | `policy_nickname` unused in UI | F | Render at `PolicyCard` ([Dashboard.jsx:339](../frontend/src/pages/Dashboard.jsx#L339)) as the primary line; demote `insurer` + `policy_name` to a sub-line. |
| 6 | No audit history / score-over-time trend | B (deferred) | Out of scope for v1 — needs `GET /audit/history`. We'll show "last audited X days ago" from `generated_at` instead. |
| 7 | No "show your work" payload surfaced anywhere | B (deferred) | `breakdowns.details` is opaque today — making it human-readable is a content-design problem, not an IA problem. Defer until breakdowns appear in mock (#1). |
| 8 | No per-policy scores (engine outputs aggregate-only) | F | The policy detail view (§2.4) needs a per-policy coverage number. Compute on frontend: `policy.sum_insured / portfolioRow.ideal × 100`. Honest approximation; cost and gap tiles get hidden in the detail view (they're portfolio-level by definition). Per-policy `claim_readiness` is a v1.1 backend concern. |

**Required before merging the redesign:** items 1, 2, 5 (cheap, high signal).
Items 3, 4, 8 are part of the redesign itself. Items 6, 7 are post-v1.

---

## 2. Wireframes

Mobile-first. Every zone reflows to a 12-col desktop grid at `md:` breakpoint.

**Page state.** A single piece of UI state controls which view renders:
`selectedPolicyId: string | "portfolio"`. Default: `"portfolio"` if the user
has 2+ policies, else the single policy id. `"portfolio"` shows §2.1/§2.2;
any policy id shows §2.4. No URL change in v1 (state is component-local).

### 2.1 Mobile (375 px) — vertical scroll

```
┌──────────────────────────────────────┐
│ Header (logo · mobile · logout)      │  ← existing Header.jsx
├──────────────────────────────────────┤
│ A. Hero score band                   │
│   ┌────────────────────────────┐     │
│   │  Your shield               │     │
│   │  ╭───╮ Gap Score: 54       │     │  ← gauge (radial)
│   │  │54 │ "1 critical gap"    │     │
│   │  ╰───╯                     │     │
│   │  Last audited 2 days ago   │     │
│   │  [View full audit →]       │     │
│   └────────────────────────────┘     │
├──────────────────────────────────────┤
│ B. Score grid (4 tiles, 2×2)         │
│   ┌──────┐ ┌──────┐                  │
│   │ Cov. │ │ Cost │                  │
│   │  62  │ │  78  │                  │
│   └──────┘ └──────┘                  │
│   ┌──────┐ ┌──────┐                  │
│   │ Claim│ │ Gap  │                  │
│   │  41  │ │  54  │                  │
│   └──────┘ └──────┘                  │
├──────────────────────────────────────┤
│ C. Top finding (hero)                │
│   ┌────────────────────────────┐     │
│   │ [red-dot] Room rent cap    │     │
│   │ "...40-60% of bill         │     │
│   │  won't be covered"         │     │
│   │ [Fix this →]               │     │
│   └────────────────────────────┘     │
├──────────────────────────────────────┤
│ D. Coverage by type                  │
│   Health     ▓▓▓▓▓▓░░░░  60%         │
│              ₹15L / ₹25L  (-₹10L)    │
│   Term Life  ░░░░░░░░░░   0%         │
│              ₹0 / ₹2Cr   (-₹2Cr)     │
│   ...                                │
├──────────────────────────────────────┤
│ E. Policies                          │
│   "3 active"                  [+ Add]│
│   ┌────────────────────────────┐     │
│   │ Father's policy  [⚠ 2]     │     │  ← nickname is primary
│   │ HDFC ERGO · Health · ₹15L  │     │
│   │ Renews 31 Mar              │     │
│   └────────────────────────────┘     │
├──────────────────────────────────────┤
│ F. Inbox (alerts)                    │
│   [bell] Renewal in 18 days...       │
│   [bell] Home loan added...          │
├──────────────────────────────────────┤
│ G. Quick actions (2-up)              │
│   [+ Add member]  [↻ Re-audit]       │
└──────────────────────────────────────┘
```

### 2.2 Desktop (≥768 px) — 12-col grid

```
┌────────────────────────────────────────────────────────────────┐
│ Header                                                         │
├──────────────────────────────────┬─────────────────────────────┤
│ A. Hero score (8 cols)           │ B. Score tiles (4 cols)     │
│   Big gauge + headline + CTA     │   Stacked 4×1                │
│                                  │   Cov · Cost · Claim · Gap   │
├──────────────────────────────────┴─────────────────────────────┤
│ C. Top finding (12 cols, full-bleed inside container)          │
├──────────────────────────────────┬─────────────────────────────┤
│ D. Coverage by type (7 cols)     │ F. Inbox (5 cols)           │
│   Bar list w/ shortfalls         │   Alert cards               │
├──────────────────────────────────┴─────────────────────────────┤
│ E. Policies (12 cols, 2-col card grid at md, 3-col at lg)      │
├────────────────────────────────────────────────────────────────┤
│ G. Quick actions (12 cols, 2-up centered)                      │
└────────────────────────────────────────────────────────────────┘
```

### 2.3 Zone purpose & priority

| Zone | Purpose | Priority |
|---|---|---|
| A. Hero score | "Am I OK?" — **gap** when `selectedPolicyId === "portfolio"`, **coverage** when a specific policy is selected | P0 |
| B. Score tiles | The four scores. In policy detail view, cost and gap tiles are dimmed + labelled "portfolio-level" (see §6.6) | P0 |
| C. Top finding | The single most actionable problem; routes to Recommendations. In policy detail view, filtered to `findings.filter(f => f.related_policy_id === selectedPolicyId)` | P0 |
| D. Coverage by type | Where the money is vs. where it should be (portfolio view only — hidden in policy detail) | P1 |
| E. Policies | Tappable cards. Tap → switches `selectedPolicyId` to that policy → §2.4 renders | P0 (tap + nickname) / P1 (chip) |
| F. Inbox | Renewals, life events, re-audit nudge (portfolio view only) | P1 |
| G. Quick actions | Add member / Re-audit (portfolio view only) | P2 |

P0 must ship together; P1/P2 can land in follow-up commits.

### 2.4 Policy detail view (when `selectedPolicyId !== "portfolio"`)

```
┌──────────────────────────────────────┐
│ Header                               │
├──────────────────────────────────────┤
│ ← All policies                       │  ← inline breadcrumb, returns to portfolio
├──────────────────────────────────────┤
│ "Father's policy"                    │  ← nickname as h1
│ HDFC ERGO · Health · ₹15L cover      │
├──────────────────────────────────────┤
│ A'. Hero — Coverage score            │
│   ╭───╮  60%                         │  ← single-policy coverage:
│   │60 │  "₹10L short of ideal        │     sum_insured / ideal_for_type
│   ╰───╯   for Mumbai Tier-1"         │
├──────────────────────────────────────┤
│ B'. Tiles (2 active, 2 dimmed)       │
│   [Cov 60] [Claim 41]                │  ← coverage = computed; claim_readiness
│   [Cost  · portfolio-level ]         │     = portfolio value (per-policy is v1.1)
│   [Gap   · portfolio-level ]         │
├──────────────────────────────────────┤
│ C'. Findings for this policy         │
│   • Room rent cap ₹5K/day  [Fix →]   │
│   • PED waiting 3 years    [Fix →]   │
├──────────────────────────────────────┤
│ Policy facts                         │
│   Premium     ₹22,400 / yr           │
│   Renews      31 Mar                 │
│   Network     4,500 hospitals        │
│   Restoration ✓ included             │
│   Sub-limits  Cataract ₹1L · Knee ₹2L│
│   Exclusions  Cosmetic, hazardous… │
└──────────────────────────────────────┘
```

The breadcrumb is a single text button (`<button>← All policies</button>`),
not a separate `Breadcrumb` component — there's only one level of nesting.

---

## 3. Component breakdown

### 3.1 New components (all under `frontend/src/components/dashboard/`)

| Component | Props | Reads from | Notes |
|---|---|---|---|
| `<HeroScore audit />` | `{audit}` | `audit.scores.gap`, `audit.generated_at` | Drives radial gauge + last-audited timestamp |
| `<ScoreTiles scores />` | `{scores}` | `audit.scores` | 2×2 mobile / 4×1 desktop. Each tile clickable — opens `<ScoreBreakdownDrawer score=…>` |
| `<ScoreBreakdownDrawer score breakdown />` | `{score, breakdown}` | `audit.breakdowns[score]` | Radix `Sheet`. Shows `details` dict as plain-English bullets — content-design needed |
| `<TopFindingCard finding />` | `{finding}` | `audit.findings[0]` | Reuses styling from existing `FindingCard.jsx` but with hero treatment |
| `<CoverageByType rows />` | `{rows}` | `audit.portfolio.by_type` | Replaces inline map at [Dashboard.jsx:140-166](../frontend/src/pages/Dashboard.jsx#L140-L166). Adds `(- ₹shortfall)` line |
| `<PolicyCardV2 policy findingsForPolicy onSelect />` | `{policy, findingsForPolicy, onSelect}` | `policies[i]` + filtered `audit.findings` | Nickname-first; chip count from real findings, not `sub_limits.length`. **Now tappable** — calls `onSelect(policy.id)` to enter detail view |
| `<PolicyDetailView policy audit onBack />` | `{policy, audit, onBack}` | one `Policy` + full `audit` | Renders §2.4. Computes per-policy coverage (`sum_insured / ideal × 100`), filters `audit.findings` by `related_policy_id`, dims cost/gap tiles. `onBack` flips `selectedPolicyId` back to `"portfolio"` |
| `<AlertsInbox alerts />` | `{alerts}` | `/alerts` | Refactor of inline section at [Dashboard.jsx:212-247](../frontend/src/pages/Dashboard.jsx#L212-L247) — no behavior change, just extraction |
| `<QuickActions onAddMember onReaudit />` | callbacks | — | Refactor of inline section at [Dashboard.jsx:250-278](../frontend/src/pages/Dashboard.jsx#L250-L278) |

### 3.2 Reused as-is

- `<Header />` — no change
- `<AddMemberModal />` — keep current implementation (lives inside `Dashboard.jsx` today; extract to its own file as a side-cleanup)
- `formatINR` from `lib/currency`
- `api` from `lib/api`

### 3.3 `Dashboard.jsx` after the redesign

Becomes a thin shell: data fetch + composition + view switching.
Target ≤140 lines (down from 466 today).

```jsx
export default function Dashboard() {
  const { user } = useAuth();
  const { audit, policies, alerts, loading } = useDashboardData(user?.has_audit);

  // Default: portfolio if 2+ policies, else jump straight to the single policy.
  const [selectedPolicyId, setSelectedPolicyId] = useState("portfolio");
  useEffect(() => {
    if (policies.length === 1) setSelectedPolicyId(policies[0].id);
  }, [policies]);

  if (!user?.has_audit) return <EmptyState />;
  if (loading) return <DashboardSkeleton />;
  if (!audit) return <DashboardErrorState />;

  if (selectedPolicyId !== "portfolio") {
    const policy = policies.find((p) => p.id === selectedPolicyId);
    if (!policy) {  // edge: policy was deleted in another tab — fall back
      setSelectedPolicyId("portfolio");
      return null;
    }
    return (
      <DashboardLayout>
        <PolicyDetailView
          policy={policy}
          audit={audit}
          onBack={() => setSelectedPolicyId("portfolio")}
        />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <HeroScore audit={audit} />
      <ScoreTiles scores={audit.scores} breakdowns={audit.breakdowns} />
      <TopFindingCard finding={audit.findings[0]} />
      <CoverageByType rows={audit.portfolio.by_type} />
      <PoliciesList
        policies={policies}
        findings={audit.findings}
        onSelect={setSelectedPolicyId}
      />
      <AlertsInbox alerts={alerts} />
      <QuickActions ... />
    </DashboardLayout>
  );
}
```

`useDashboardData` is a small custom hook that wraps the existing
`Promise.all` block — no library, no SWR, no React Query. We don't need
caching for v1.

---

## 4. Chart choices

### 4.1 Decisions

| Zone | Chart | Lib | Rationale |
|---|---|---|---|
| A. Hero score gauge | Radial / arc gauge (1 segment, 0-100) | `recharts` `RadialBarChart` | Most-glanceable for a single big number. ~30 LOC |
| B. Score tiles | Inline mini-bar (no chart lib) | CSS only | A 4-tile grid doesn't warrant a chart lib — just a `<div>` with width % |
| D. Coverage by type | Horizontal bars w/ overflow indicator | CSS only (current approach is fine) | Already implemented; keep for consistency |

### 4.2 Charts considered and rejected

- **Donut for "where the money goes" (premium split by type)** — interesting, but reading premium splits off a donut is hard at small sizes and we don't have user research validating the question. Skip.
- **Line chart for score over time** — would be the right answer, but we don't have audit history exposed (gap #6). Skip until backend lands.
- **Radar chart of all four scores** — visually appealing, low information density vs. score tiles. Skip.

### 4.3 Library check

`recharts@^3.6.0` is **already a dependency** ([frontend/package.json](../frontend/package.json)) but is not currently imported anywhere. Confirmed via grep — zero usages. Adding the gauge is the first user.

Bundle impact: recharts pulls in d3-shape and d3-scale (~80 KB gzipped).
Acceptable given (a) it's already on disk, (b) we'll likely add the score-over-time line in v1.1.

If bundle becomes a concern: `RadialBarChart` is also doable in ~50 LOC with raw SVG and no dependency. Note this as a possible follow-up if recharts ends up being its only consumer.

---

## 5. Library check (full)

Confirmed available in [frontend/package.json](../frontend/package.json):

| Need | Library | Status |
|---|---|---|
| Charts | `recharts@^3.6.0` | Installed, unused — first consumer in this work |
| Animation | `framer-motion@^12.38.0` | Already used in current Dashboard |
| Icons | `lucide-react@^0.507.0` | Already used |
| Drawer/Sheet for `<ScoreBreakdownDrawer>` | `@radix-ui/react-dialog@^1.1.11` | Available; `Sheet` wrapper exists in `components/ui/` |
| Tooltips on score tiles | `@radix-ui/react-tooltip@^1.2.4` | Available |
| Toast | `sonner@^2.0.3` | Already used (`toast.success/error`) |
| Scroll area for long alert list | `@radix-ui/react-scroll-area@^1.2.6` | Available |

**Nothing to install.** Net new dependency count: 0.

---

## 6. Empty states

The dashboard has three empty surfaces, each with a distinct message.

### 6.1 No audit yet (`!user.has_audit`)

Already implemented at [Dashboard.jsx:288-317](../frontend/src/pages/Dashboard.jsx#L288-L317). Keep as-is — copy is good, CTA is clear.

### 6.2 Audit exists, but `audit.scores.coverage === null` etc.

The engine returns `null` for any score it can't compute (e.g., `cost`
needs ≥2 policies to compare). The current Stage6Audit handles this via
`SCORE_LABEL` ([Stage6Audit.jsx:13-31](../frontend/src/pages/Stage6Audit.jsx#L13-L31)).

For dashboard tiles, mirror that pattern:

```
┌──────┐
│ Cost │
│  —   │     ← no big number
│ Need 2+ policies │
│ to compare       │
└──────┘
```

The hero score (gap) should never be null in practice — every audit run
produces a gap score. If it is null, fall back to a non-numeric headline:
"Audit incomplete — re-run with more data."

### 6.3 No policies (`policies.length === 0`)

Show the existing dashed-border CTA at [Dashboard.jsx:198-201](../frontend/src/pages/Dashboard.jsx#L198-L201). No change.

### 6.4 No alerts (`alerts.length === 0`)

Currently the section just renders nothing — there's no "no alerts" message.
Add a quiet line:

```
"No alerts. We'll ping you 30 days before any policy renews."
```

Don't show this section at all if `alerts.length === 0` AND we're space-constrained on mobile — better than a permanent "nothing here" block.

### 6.5 No findings (`audit.findings.length === 0`)

Edge case: a perfect-score user. Replace the top finding card with:

```
[shield-check] "No red flags found in your current cover."
```

In practice this is rare today (most users have ≥1 amber finding) but the
copy needs to exist.

### 6.6 Policy detail view — portfolio-level tiles

In `<PolicyDetailView>`, the cost and gap tiles render dimmed with the label
"portfolio-level only" instead of a number. Tooltip on hover/tap explains:
"This score compares all your policies together. Open the audit report to
see it." The coverage tile shows a frontend-computed value
(`policy.sum_insured / portfolioRow.ideal × 100`); claim_readiness shows
the audit-level value with a small "(portfolio)" tag — per-policy CR is a
v1.1 backend concern (gap #8).

### 6.7 Policy with no findings (`findings filtered to selectedPolicyId is empty`)

The C zone in policy detail view shows:

```
"No red flags specific to this policy."
```

Don't fall back to portfolio findings — that defeats the purpose of the
filter and confuses the user.

---

## 7. Loading states

### 7.1 Initial fetch

Today: a single centered spinner ([Dashboard.jsx:93-97](../frontend/src/pages/Dashboard.jsx#L93-L97)). Replace with a layout-shaped skeleton.

```jsx
<DashboardSkeleton>
  <SkeletonHeroScore />        {/* 200px tall block */}
  <SkeletonScoreTiles count={4} />
  <SkeletonFindingCard />
  <SkeletonCoverageBars rows={5} />
  <SkeletonPolicyList count={3} />
</DashboardSkeleton>
```

Skeleton blocks: `bg-[#E1E5EB]` with `animate-pulse`. No additional library
needed.

Why: the spinner gives no preview of layout. Skeleton lets users start
parsing the page structure ~300ms earlier.

### 7.2 Re-audit in progress

CTA at [Dashboard.jsx:266-277](../frontend/src/pages/Dashboard.jsx#L266-L277) currently does `await api.post → toast → reload`. The user sees nothing for ~5-15s. Replace with:

1. Disable the button + show inline spinner (use the existing `loading` prop on `<BottomCTA>` or equivalent — same pattern as the upload button).
2. On success, instead of `window.location.reload()`, just refetch via the hook. Smoother — no flash of empty layout.

### 7.3 Score breakdown drawer

When user taps a score tile and the drawer opens, `breakdowns` is already
in memory (came with the initial fetch). No loading state needed. If we
later split breakdowns into a separate lazy fetch, add a per-drawer
skeleton.

### 7.4 Per-section error states

If `/policies` 500s but `/audit/latest` succeeds, the policies section
should show its own error:

```
"Couldn't load policies. [Retry]"
```

Today the entire dashboard fails silently if any of the three calls reject
(the `try/finally` swallows the error and `audit` stays null, which renders
as "no audit" — wrong). Wrap each fetch in its own try/catch in the
`useDashboardData` hook.

---

## 8. Implementation order (suggested)

To keep PRs small and reviewable:

1. **Backend fixture parity** — add `breakdowns`, `all_findings`, `related_policy_id` to `make_mock_audit`. ~15 LOC, 2 tests. No frontend change.
2. **Component extraction (no behavior change)** — pull the inline sections in `Dashboard.jsx` into `components/dashboard/*.jsx`. Confirms current behavior survives the refactor.
3. **Nickname rendering** — `PolicyCardV2` uses `policy_nickname` as primary line.
4. **Per-policy finding chip** — replace `sub_limits.length` proxy.
5. **Hero score + score tiles + breakdown drawer** — new zones A & B.
6. **Skeleton loader** — replace spinner.
7. **Per-section error handling** — `useDashboardData` hook.

Each step ships independently, behind no flags. Total: ~7 commits.

---

## 9. Decisions resolved

1. **Multi-policy switcher** — hybrid approach. No dropdown switcher. Default
   to portfolio view; tapping any card in zone E enters the per-policy
   detail view (§2.4). Inline `← All policies` button returns. Page state:
   `selectedPolicyId: string | "portfolio"`.
2. **Hero score is dynamic by view** — `gap` in portfolio view (the engine's
   summary score), `coverage` in policy detail view (frontend-computed for
   the selected policy).
3. **Score tile click → drawer** — Radix `Sheet`, breakdowns served from the
   already-fetched audit object. No additional fetch.
4. **Charts: recharts** — already installed; first consumer is the hero gauge.
5. **Implementation: full 7-commit sequence** — backend fixture parity and
   component extraction (steps 1–2) are prerequisites, not shortcuttable.
   Estimated 5–7 hours total agent time.

Deferred to v1.1+:

- Sticky re-audit CTA on mobile (§2.3 G zone)
- Audit-history line chart (§1.4 gap #6 — needs `GET /audit/history`)
- Per-policy `claim_readiness` score (§1.4 gap #8 — backend work)
- Human-readable rendering of `breakdowns.details` (§1.4 gap #7)
