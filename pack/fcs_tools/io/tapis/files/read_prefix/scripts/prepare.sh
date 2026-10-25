# Verified Pack script; no host shell fallback.
set -eu
printf '%s' "$FCS_INPUT_JSON" | jq '{connection:"tapis",method:"GET",path:(["v3","files","ops",.location.system_id]+.location.segments),query:[["startByte","0"],["count",(.max_bytes|tostring)]],response:"text",timeout_seconds:10}'
