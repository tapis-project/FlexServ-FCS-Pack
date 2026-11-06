set -eu
items=$(printf '%s' "$FCS_INPUT_JSON" | jq -c '.items')
fcs_map --limit 4 --on-error collect_all tool_expression "$items"
