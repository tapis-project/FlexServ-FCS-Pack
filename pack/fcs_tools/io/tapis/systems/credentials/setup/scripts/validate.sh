# Verified Pack script; no host shell fallback.
set -eu
printf '%s' "$FCS_INPUT_JSON" | jq -e '.system.host == .target.host and (.system.port // 22) == .target.port and .system.defaultAuthnMethod == "PKI_KEYS" and .system.effectiveUserId == .target.login_user' >/dev/null || { echo 'System does not match approved SSH target' >&2; exit 1; }
printf '%s\n' '{"validated":true}'
