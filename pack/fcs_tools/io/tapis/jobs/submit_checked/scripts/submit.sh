# Verified Pack script; no host shell fallback.
set -eu
r=$(tool_submit "$(printf '%s' "$FCS_INPUT_JSON" | jq '{request:.definition}')")
tool_confirm "$(jq -nc --argjson r "$r" '{response:$r}')" >/dev/null
printf '%s' "$r" | jq -e '.body.result.uuid | type=="string" and length>0 and length<=256 and (contains("/")|not)' >/dev/null || { echo 'Missing or invalid job UUID' >&2; exit 1; }
printf '%s' "$r" | jq '{job_uuid:.body.result.uuid}'
