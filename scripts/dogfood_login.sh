#!/bin/bash
# Dogfood auth helper.
#   Usage: ./scripts/dogfood_login.sh <10-digit-mobile> [http://localhost:8000]
# Requests an OTP, verifies with the dev OTP "123456", saves cookies + the
# CSRF token to /tmp/kavach_dogfood_*. Prints two `export` lines you can
# eval to use the session in subsequent curl calls.
#
# Example:
#   eval "$(./scripts/dogfood_login.sh 9999999999)"
#   curl -b "$KAVACH_COOKIES" -H "X-CSRF-Token: $KAVACH_CSRF" \
#        -X POST "$KAVACH_HOST/api/audit/generate?beta=audit-real"
#
# The dev backend accepts OTP "123456" for any mobile when running with
# the default OTP_DEV_MODE; see backend/otp_service.py.

set -euo pipefail

MOBILE="${1:?usage: $0 <10-digit-mobile> [host]}"
HOST="${2:-http://localhost:8000}"
COOKIE_JAR="/tmp/kavach_dogfood_cookies_${MOBILE}.txt"
CSRF_FILE="/tmp/kavach_dogfood_csrf_${MOBILE}.txt"

if ! [[ "$MOBILE" =~ ^[0-9]{10}$ ]]; then
  echo "ERROR: mobile must be 10 digits" >&2
  exit 1
fi

# 1. Request OTP
otp_resp=$(curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mobile\":\"$MOBILE\"}" \
  "$HOST/api/auth/request-otp")
if ! echo "$otp_resp" | grep -q '"success":true'; then
  echo "ERROR: request-otp failed: $otp_resp" >&2
  exit 2
fi

# 2. Verify OTP (dev = 123456)
verify_resp=$(curl -sS -c "$COOKIE_JAR" -X POST -H "Content-Type: application/json" \
  -d "{\"mobile\":\"$MOBILE\",\"otp\":\"123456\"}" \
  "$HOST/api/auth/verify-otp")
if ! echo "$verify_resp" | grep -q '"success":true'; then
  echo "ERROR: verify-otp failed: $verify_resp" >&2
  exit 2
fi

# 3. Extract CSRF token from cookie jar (Netscape format: cols 1-7 = domain, ..., name, value)
csrf=$(awk '$6=="kavach_csrf" {print $7}' "$COOKIE_JAR" | tail -1)
if [ -z "$csrf" ]; then
  echo "ERROR: no kavach_csrf cookie set; verify-otp likely failed silently" >&2
  exit 3
fi
echo "$csrf" > "$CSRF_FILE"

# 4. Fetch user_id + has_audit
me_resp=$(curl -sS -b "$COOKIE_JAR" "$HOST/api/user/me")
user_id=$(echo "$me_resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['user']['id'])" 2>/dev/null || echo "?")

# 5. Print exports + a quick reference
cat <<EOF
# Login OK for mobile $MOBILE
# user_id: $user_id
# Run:  eval "\$(./scripts/dogfood_login.sh $MOBILE)"
export KAVACH_HOST="$HOST"
export KAVACH_COOKIES="$COOKIE_JAR"
export KAVACH_CSRF="$csrf"
export KAVACH_USER_ID="$user_id"

# --- Common follow-ups ---
# Profile patch (Stage 1):
#   curl -sS -b "\$KAVACH_COOKIES" -H "X-CSRF-Token: \$KAVACH_CSRF" -H "Content-Type: application/json" \\
#        -X PATCH -d '{"age":34,"city":"Mumbai"}' "\$KAVACH_HOST/api/user/me"
#
# Audit (with beta flag — only fires if you're allowlisted):
#   curl -sS -b "\$KAVACH_COOKIES" -H "X-CSRF-Token: \$KAVACH_CSRF" \\
#        -X POST "\$KAVACH_HOST/api/audit/generate?beta=audit-real" | jq '.data.audit | {engine_mode,beta_invocation,scores}'
#
# Get latest audit:
#   curl -sS -b "\$KAVACH_COOKIES" "\$KAVACH_HOST/api/audit/latest" | jq '.data.audit.scores'
EOF
