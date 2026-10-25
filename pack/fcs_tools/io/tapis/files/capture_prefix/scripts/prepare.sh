# Verified Pack script; no host shell fallback.
set -eu
printf '%s' "$FCS_INPUT_JSON" | jq '{connection:"tapis",method:"GET",path:(["v3","files","ops",.location.system_id]+.location.segments),query:[["startByte","0"],["count",(.max_bytes|tostring)]],response:"sensitive",timeout_seconds:10} + {capture:{profile:"service_tokens",max_bytes:.max_bytes}}'
