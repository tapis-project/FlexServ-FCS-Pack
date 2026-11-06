set -eu
if printf '%s' "$FCS_INPUT_JSON" | jq -e '.e == 0' >/dev/null; then
    fcs_trace branch zero_divisor
    printf '%s\n' 'Division by zero' >&2
    exit 1
else
    fcs_trace branch nonzero_divisor
fi
jobs=$(printf '%s' "$FCS_INPUT_JSON" | jq -c '[{id:"add",tool:"tool_add",input:{a:.a,b:.b}},{id:"subtract",tool:"tool_subtract",input:{a:.c,b:.d}}]')
joined=$(fcs_parallel --limit 4 --on-error fail_fast "$jobs")
operands=$(printf '%s' "$joined" | jq -c '{a:.results[0].value.value,b:.results[1].value.value}')
product=$(tool_multiply "$operands")
divisor=$(printf '%s' "$FCS_INPUT_JSON" | jq '.e')
quotient=$(tool_divide "$(jq -nc --argjson p "$product" --argjson e "$divisor" '{a:$p.value,b:$e}')")
tool_square "$quotient"
