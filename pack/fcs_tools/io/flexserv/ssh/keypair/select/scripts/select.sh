# Verified Pack script; no host shell fallback.
set -eu
profile=$(printf '%s' "$FCS_INPUT_JSON" | jq -r '.target.secret_profile')
provider=$(printf '%s' "$FCS_INPUT_JSON" | jq -r '.provider')
case "$provider" in
 rust) tool_rust "$(jq -nc --arg p "$profile" '{profile:$p}')" ;;
 cli) tool_cli "$(printf '%s' "$FCS_INPUT_JSON" | jq '{profile:.target.secret_profile,workspace_profile:.target.workspace_profile}')" ;;
 *) echo 'Unsupported key provider' >&2; exit 1 ;;
esac
