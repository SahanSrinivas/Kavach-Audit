# Wordings Database — Design Decisions

Phase 1.5 build-out. Decisions captured here so they don't drift between
implementation sessions. Source: Step 1 situational map review,
2026-05-04.

Strategic context: Pre-parse the top ~30 Indian health insurance wordings
and store the structured extraction. When a user uploads only their
schedule (1-2 page personalized doc), the audit pipeline looks up the
plan's rules from this DB instead of asking the user to upload the full
50-page wording. Better UX (₹3 + 5s vs ₹35 + 30s), better data asset for
Phase 2 comparison engine.

---

## Decision 1 — Fuzzy plan-name matching: stick with `difflib`

**Choice:** Use stdlib `difflib.get_close_matches(cutoff=0.85)` for
fuzzy plan-name matching in `services/wordings.py:lookup_wording()`.
Do NOT add `rapidfuzz` to `requirements.txt`.

**Why:**
- Consistent with the existing canonicalizer pattern at
  [services/parser/insurer_canonicalizer.py:14](../backend/services/parser/insurer_canonicalizer.py#L14).
- Zero new pip dependencies (constraint).
- For ~30 wordings, `difflib` is plenty fast — match is single-pass over
  a tiny list.
- The 0.85 cutoff already works in production for insurer canonicalization;
  same threshold transfers cleanly to plan-name matching.

**When to revisit:** if the wordings DB grows past ~500 entries OR fuzzy
match quality on plan names becomes a real complaint, evaluate
`rapidfuzz` for `WRatio` / partial-token matching.

---

## Decision 2 — Add `plan_name` to `ParsedPolicy` schema

**Choice:** Add `plan_name: Optional[str]` to the parser's `ParsedPolicy`
model. Add a prompt rule asking Claude to extract the product name from
the policy schedule (every schedule has it on the cover page).

**Where it lands:**
- If v0.4-pdf-parser hasn't been committed yet → fold into v0.4.
- If it has been → ships as v0.4.1.

**Why:**
- Without `plan_name`, the wordings lookup has ~0% hit rate. We'd be
  trying to match against `_derive_policy_name()`'s synthesized string
  ("HDFC ERGO General Health Family Floater") instead of the actual
  product name ("Optima Restore", "ReAssure 2.0", etc.).
- Small change (~5 lines: schema field + prompt rule + use in
  `_derive_policy_name`). Doesn't affect any existing test fixtures
  since the field is `Optional`.
- Justifies the scope expansion vs the "don't modify the parser"
  constraint — without this, Phase 1.5 has no usable lookup mechanism.

**Implementation notes when we get there:**
- Schema: add `plan_name: Optional[str] = None` to `ParsedPolicy` in
  [services/parser/types.py](../backend/services/parser/types.py).
- Prompt rule: insert into the `<output_schema>` block as a top-level
  field, AND add a new `<extraction_rules>` entry: "plan_name is the
  marketing/product name as it appears on the policy schedule cover
  page (e.g., 'Optima Restore', 'ReAssure 2.0', 'Star Comprehensive').
  If absent (genuine wording-only doc), set null."
- Update `_derive_policy_name()` in
  [routers/policies_router.py:202](../backend/routers/policies_router.py#L202)
  to prefer `parsed.plan_name` and fall back to the synthesized name.
- Add a unit test asserting `plan_name` survives the validator on a
  realistic Claude response.
- Lookup: in `services/wordings.py:lookup_wording`, normalize the
  incoming plan_name (lowercase, strip non-alphanumeric) and match
  against `wordings.plan_name_normalized`.

---

## Decision 3 — SI tier mismatch: warn, don't block

**Choice:** When a user's schedule has `sum_insured` NOT in the
looked-up wording's `available_sum_insured_lakhs` list:
- Log a warning to `kavach.wordings`
- Set `wording_source: "looked_up_si_mismatch"` on the policy doc
- **Still merge the rules** — do not block the audit

**Why NOT a hard error:**
- Insurers add new SI tiers periodically (e.g., HDFC ERGO adding ₹2 Cr
  in late 2025). Our DB will lag.
- Hard-blocking on mismatch would create user-facing failures that look
  like bugs but are actually stale data. Bad for trust.
- The wording's clauses (room rent cap, copay, exclusions) generally
  apply across all SI tiers of the same plan; the SI-tier list is
  validation metadata, not a primary key.

**Why log it:**
- Frequency of mismatches is the signal that tells us when to refresh
  the wordings DB. Track this as a metric.
- An admin UI alert when the same (insurer, plan, mismatched_si) shows
  up >5 times in a week tells us "go re-parse this wording."

**Provenance values for `wording_source`:**
- `"user_uploaded"` — user uploaded a wording PDF, rules came from their parse
- `"looked_up"` — user uploaded a schedule, rules looked up from wordings DB, SI matched
- `"looked_up_si_mismatch"` — same but schedule SI not in wording's available list (still merged)
- `"missing"` — no wording found AND user didn't upload a wording (engine runs in defensive mode)

---

## Open items that did NOT need a decision yet

These were considered, deferred, or don't materialize until later phases:

1. **Auto-fallback parsing for unknown plans** — when a user's plan isn't
   in our wordings DB, optionally trigger an automated parse-and-store of
   that wording (download from insurer website, parse, mark as
   `qa_status: needs_review`). TODO for Phase 1.5+.

2. **Schedule-vs-wording detection function** — currently a heuristic
   (`sum_insured is None and premium_annual is None`). When we wire the
   merger, formalize as `policy_merger.is_schedule(parsed) -> bool` and
   `policy_merger.needs_wording_lookup(parsed) -> bool`. Pure functions,
   easy to test.

3. **Wording-version drift** — when a wording is re-parsed (insurer
   publishes a revision), keep the old version with
   `qa_status: "superseded"` rather than overwriting. Audit policies
   reference `wording_version` for reproducibility. Will design when we
   hit the first revision in the wild.

4. **Cross-plan wording inheritance** — some insurers have base-plus-
   addon plans where the addon inherits all rules from the base plan and
   only overrides a few. Out of scope for Phase 1.5; revisit if it
   becomes common in our top-30 set.

---

## Operational learnings from first wording parse (HDFC ERGO Optima Restore, 2026-05-04)

Captured after the worked-example dry-run on `optima-restore-revision.pdf`
(755 KB, 50+ pages). These shape the admin runbook.

### Reliably-null fields for wording-only parses

The following parsed_fields are essentially always `null` when parsing a
wording document (vs a schedule), because the data lives in marketing
materials or insurer-specific quote tables, not in the wording PDF
itself:

- `network_hospital_count` — wordings name the cashless TPA but rarely
  state the count; admin must populate from insurer's website / brochure
- `day_care_procedures_count` — wordings list named procedures (often
  100+ entries by name) but rarely give a count
- `available_sum_insured_lakhs` — listed in the "Schedule of Benefits"
  table that's typically a separate brochure document
- `add_ons` — same; lives in product brochures, not the wording

**Don't fail QA on these being null for wording parses.** Future
enhancement: admin PATCH endpoint that takes a small JSON of these
per-insurer marketing fields and merges into the stored wording.

### `parse_confidence: "low"` is NORMAL for wordings

For schedules, `confidence: "low"` is a red flag (means SI/premium/dates
unextractable). For WORDINGS, `low` is the default and expected
state — wordings genuinely lack:

- `sum_insured` (lives on the user's specific schedule)
- `premium_annual` (same)
- `policy_start_date` / `policy_end_date` (same)
- `covered_members` (same)

The validator (correctly) flags these as low-conf because they're missing.
But for wordings, this is by design.

**QA decision rule: ignore `parse_confidence.overall` for wordings.
Make qa_status decisions on whether the RULES BLOCK is accurate** —
specifically: does `room_rent_cap`, `copay_percent`, `ped_waiting_months`,
`permanent_exclusions`, `restoration_benefit`, `ncb_structure`, and
`sub_limits` match the wording document? Those are the lookup payload.

### Admin runbook tl;dr (for the next-session reviewer)

1. `python scripts/parse_wording.py --dry-run --pdf X --insurer Y --plan Z`
   → eyeball the rules block. If it matches what the wording says, proceed.
2. Re-run WITHOUT `--dry-run` to actually store as `auto_parsed`.
3. `python scripts/verify_wording.py --id <id> --notes "QA passed"`
   → promotes to `human_verified`.
4. If rules look wrong (sub-limit miscoded, exclusion missing, etc.),
   either:
   - `verify_wording.py --status needs_review --notes "..."` and queue
     for re-parse, OR
   - re-parse with the same `--insurer` + `--plan` (idempotent — same
     id, replaces rules, resets qa_status to auto_parsed).
