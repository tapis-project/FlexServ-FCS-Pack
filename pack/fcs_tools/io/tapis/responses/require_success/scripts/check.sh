# Verified Pack script; no host shell fallback.
set -eu
printf '%s' "$FCS_INPUT_JSON" | jq -e '.response.ok == true and (.response.body.status | ascii_downcase) == "success"' >/dev/null || { echo 'Tapis request was not confirmed successful (body omitted)' >&2; exit 1; }
printf '%s\n' '{"accepted":true}'
