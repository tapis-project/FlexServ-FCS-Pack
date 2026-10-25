# Verified Pack script; no host shell fallback.
set -eu
printf '%s' "$FCS_INPUT_JSON" | jq '.last + {observation:{stop_reason:.stop_reason,attempts:.attempts}}'
