# Beta Allowlist — Operations Runbook

Per-user opt-in to real (vs mock) services. Used to dogfood the real audit engine + Claude PDF parser on a small allowlist of users before flipping `USE_MOCKS=false` globally.

## Features

| Feature ID | Affects | Effect when allowlisted + `?beta=<id>` |
|---|---|---|
| `audit-real` | `POST /api/audit/generate?beta=audit-real` | Real `services.audit.engine` runs (else mock fixture) |
| `parser-real` | `POST /api/policies/upload?beta=parser-real` | Real Claude PDF parser runs (else mock parsed_policy) |
| `claims-advocate` | (forward-compat, not implemented) | n/a |

Unset env defaults: `USE_MOCKS=true`, `PARSER_FALLBACK_TO_MOCK_ON_ERROR=false`.

Cache TTL is 60 seconds — adding/removing a user takes effect within 60 s.

## Add a user

```bash
# 1. Find the user_id (admin token in $ADMIN_PASSWORD)
curl -H "Authorization: Bearer $ADMIN_PASSWORD" \
  https://your-backend/api/admin/users | jq '.data.users[] | {id, mobile}'

# 2. Add to the audit-real allowlist
curl -X POST -H "Authorization: Bearer $ADMIN_PASSWORD" \
     -H "Content-Type: application/json" \
     -d '{"user_id":"<id>","feature":"audit-real","notes":"founder dogfood"}' \
     https://your-backend/api/admin/beta-allowlist
```

Response: `{success: true, data: {added: true, entry: {...}}}`. Returns `409 already_allowlisted` if the (user_id, feature) pair already exists (the unique compound index in `beta_allowlist` prevents duplicates).

## Remove a user

```bash
curl -X DELETE -H "Authorization: Bearer $ADMIN_PASSWORD" \
     -H "Content-Type: application/json" \
     -d '{"user_id":"<id>","feature":"audit-real"}' \
     https://your-backend/api/admin/beta-allowlist
```

Returns `404 not_allowlisted` if the row doesn't exist.

## List allowlisted users

```bash
# All features
curl -H "Authorization: Bearer $ADMIN_PASSWORD" \
     https://your-backend/api/admin/beta-allowlist | jq

# Filter by feature
curl -H "Authorization: Bearer $ADMIN_PASSWORD" \
     "https://your-backend/api/admin/beta-allowlist?feature=audit-real" | jq
```

## Inspect Mongo for which audits ran real vs mock

Every audit row in `db.audits` carries two observability fields:

| Field | Type | Meaning |
|---|---|---|
| `engine_mode` | `"real"` \| `"mock"` | Which engine actually ran for this audit |
| `beta_invocation` | `bool` | `true` iff the real path ran via per-user beta opt-in (vs global `USE_MOCKS=false` flip) |

Same two fields on `db.policies` rows from PDF uploads, named `parser_mode` and `beta_invocation`. Future analytics queries will key on these — they are the source of truth for "was this audit produced by the real engine?"

```js
// Find all real-engine audits in the last 7 days:
db.audits.find(
  { engine_mode: "real",
    generated_at: { $gte: new Date(Date.now() - 7*86400000).toISOString() } },
  { user_id: 1, generated_at: 1, beta_invocation: 1, scores: 1 }
).sort({ generated_at: -1 })

// Count beta-invoked vs forced-real audits:
db.audits.aggregate([
  { $match: { engine_mode: "real" } },
  { $group: { _id: "$beta_invocation", count: { $sum: 1 } } }
])
// → [{_id: true, count: N},   ← real engine via beta opt-in
//    {_id: false, count: M}]  ← real engine because USE_MOCKS=false globally

// Count audits by mode in last 24 h
db.audits.aggregate([
  { $match: { generated_at: { $gte: new Date(Date.now() - 86400000).toISOString() } } },
  { $group: { _id: { engine_mode: "$engine_mode", beta: "$beta_invocation" }, n: { $sum: 1 } } }
])

// All audits run via beta opt-in (vs the global USE_MOCKS flip)
db.audits.find({ beta_invocation: true }, { user_id: 1, generated_at: 1, scores: 1 })

// Last 10 real-engine audits across the fleet
db.audits.find({ engine_mode: "real" }).sort({ generated_at: -1 }).limit(10)

// Same shape works for db.policies (PDF uploads):
db.policies.find({ parser_mode: "real" }, { user_id: 1, insurer: 1, parse_confidence: 1 })
db.policies.aggregate([
  { $match: { parser_mode: { $exists: true } } },
  { $group: { _id: "$parser_mode", count: { $sum: 1 } } }
])
```

## Rollback: pull a user off the real engine cleanly

If the real engine produces a bad audit for a beta user:

1. **Remove from allowlist** (above curl). Their next `POST /audit/generate?beta=audit-real` falls through to mock.
2. **Optionally delete the bad audit row** so `GET /audit/latest` returns the previous good audit:
   ```js
   db.audits.deleteOne({ user_id: "<id>", engine_mode: "real",
                          generated_at: "<bad-audit-iso-timestamp>" });
   ```
3. **Have them re-run the audit** (without `?beta=` → mock fixture) so the dashboard repopulates.

If the engine breaks for **all** beta users at once: clear everyone with one shot.

```js
db.beta_allowlist.deleteMany({ feature: "audit-real" });
```

(In-process cache invalidates within 60 s; in the meantime existing requests in-flight finish on whatever path they started on.)

## End-to-end dogfood flow (founder, tonight)

```bash
# 0. Confirm USE_MOCKS=true on the deployment (so the only way to get real
#    is via the beta allowlist; safer than flipping the global)
curl https://your-backend/api/health | jq '.use_mocks'

# 1. Find your user_id
curl -H "Authorization: Bearer $ADMIN_PASSWORD" \
  https://your-backend/api/admin/users | jq '.data.users[] | select(.mobile=="<your10digits>") | .id'

# 2. Add yourself to the audit-real allowlist
curl -X POST -H "Authorization: Bearer $ADMIN_PASSWORD" \
     -H "Content-Type: application/json" \
     -d '{"user_id":"<your-id>","feature":"audit-real","notes":"founder dogfood"}' \
     https://your-backend/api/admin/beta-allowlist

# 3. Authenticate as yourself (use the existing OTP flow; cookies into cookies.txt)
curl -c cookies.txt -X POST -H "Content-Type: application/json" \
     -d '{"mobile":"<your10digits>"}' https://your-backend/api/auth/request-otp
curl -c cookies.txt -b cookies.txt -X POST -H "Content-Type: application/json" \
     -d '{"mobile":"<your10digits>","otp":"123456"}' https://your-backend/api/auth/verify-otp
CSRF=$(awk '$6=="kavach_csrf"{print $7}' cookies.txt)

# 4. POST /audit/generate WITH the beta flag → real engine
curl -b cookies.txt -X POST -H "X-CSRF-Token: $CSRF" \
     "https://your-backend/api/audit/generate?beta=audit-real" | jq

# 5. Sanity check: POST WITHOUT the flag → mock
curl -b cookies.txt -X POST -H "X-CSRF-Token: $CSRF" \
     https://your-backend/api/audit/generate | jq '.data.audit.engine_mode'
# expect: "mock"

# 6. Verify Mongo
mongosh "$MONGO_URL/$DB_NAME" --eval \
  'db.audits.find({user_id:"<your-id>"},{engine_mode:1,beta_invocation:1,generated_at:1}).sort({generated_at:-1}).limit(2)'
```

When you're satisfied: keep the allowlist for 1-2 weeks of dogfood, then flip `USE_MOCKS=false` globally and clear the allowlist with `db.beta_allowlist.deleteMany({})`.
