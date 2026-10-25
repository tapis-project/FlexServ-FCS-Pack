# Verified Pack script; no host shell fallback.
set -eu
p=$(printf '%s' "$FCS_INPUT_JSON" | jq -c '.definition')
r=$(printf '%s' "$FCS_INPUT_JSON" | jq -c '.response.body.result')
jq -ne --argjson p "$p" --argjson r "$r" '($r|type)!="object" or (($r.id // $p.id)==$p.id)' >/dev/null || { echo 'Created ID differs from request' >&2; exit 1; }
printf '%s' "$p" | jq '{system_id:.id}'
