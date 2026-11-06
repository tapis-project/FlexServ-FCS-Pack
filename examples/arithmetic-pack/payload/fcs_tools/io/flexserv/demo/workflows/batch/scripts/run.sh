set -eu
count=$(printf '%s' "$FCS_INPUT_JSON" | jq '.items|length')
results='[]'
for index in $(seq 0 $((count - 1))); do
    fcs_trace iteration sequential_batch "$index"
    input=$(printf '%s' "$FCS_INPUT_JSON" | jq -c --argjson i "$index" '.items[$i]')
    result=$(tool_expression "$input")
    results=$(jq -nc --argjson results "$results" --argjson result "$result" '$results+[$result]')
done
jq -nc --argjson results "$results" '{results:$results}'
