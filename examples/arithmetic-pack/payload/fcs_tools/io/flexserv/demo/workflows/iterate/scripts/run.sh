set -eu
count=$(printf '%s' "$FCS_INPUT_JSON" | jq '.iterations')
input=$(printf '%s' "$FCS_INPUT_JSON" | jq -c 'del(.iterations)')
result=$(printf '%s' "$input" | jq -c '{value:.a}')
results='[]'
index=0
while [ "$index" -lt "$count" ]; do
    fcs_trace iteration recurrence "$index"
    result=$(tool_expression "$input")
    results=$(jq -nc --argjson results "$results" --argjson result "$result" '$results+[$result]')
    input=$(jq -nc --argjson input "$input" --argjson result "$result" '$input|.a=$result.value')
    index=$((index + 1))
done
jq -nc --argjson result "$result" --argjson results "$results" '{value:$result.value,results:$results}'
