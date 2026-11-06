set -eu
a=$(printf '%s' "$FCS_INPUT_JSON" | jq -r '.a')
b=$(printf '%s' "$FCS_INPUT_JSON" | jq -r '.b')
result=$(printf 'scale=324; (%s)-(%s)\n' "$a" "$b" | bc)
jq -nc --arg result "$result" '{value:($result|tonumber)}'
