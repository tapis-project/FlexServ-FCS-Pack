# Verified Pack script; no host shell fallback.
set -eu
j=$(tool_inspect "$(printf '%s' "$FCS_INPUT_JSON" | jq '{job_uuid:.job_uuid}')")
s=$(printf '%s' "$j" | jq -r '.status')
case "$s" in
 FAILED|CANCELLED) jq -nc --argjson j "$j" '{done:true,job:$j,token_found:false,token_ref:null,reason:("job_"+($j.status|ascii_downcase)),truncated:false}'; exit 0 ;;
 RUNNING|FINISHED) ;;
 *) jq -nc --argjson j "$j" '{done:false,job:$j,token_found:false,token_ref:null,reason:"job_not_ready",truncated:false}'; exit 0 ;;
esac
l=$(tool_location "$(jq -nc --argjson j "$j" --argjson p "$FCS_INPUT_JSON" '{job:$j,output:$p.output}')")
if [ "$(printf '%s' "$l" | jq -r '.available')" != true ]; then jq -nc --argjson j "$j" '{done:false,job:$j,token_found:false,token_ref:null,reason:"output_location_unavailable",truncated:false}'; exit 0; fi
c=$(tool_capture "$(jq -nc --argjson l "$l" --argjson p "$FCS_INPUT_JSON" '{location:$l,max_bytes:$p.output.max_bytes}')")
if [ "$(printf '%s' "$c" | jq -r '.status')" = 404 ]; then jq -nc --argjson j "$j" '{done:false,job:$j,token_found:false,token_ref:null,reason:"file_not_created",truncated:false}'; exit 0; fi
printf '%s' "$c" | jq -e '.ok==true' >/dev/null || { echo 'Output request failed (body omitted)' >&2; exit 1; }
r=$(tool_scan "$(jq -nc --argjson c "$c" --argjson p "$FCS_INPUT_JSON" '{content_ref:$c.content_ref,marker:$p.output.marker,match:$p.output.match,max_lines:$p.output.max_lines}')")
jq -nc --argjson j "$j" --argjson r "$r" '{done:$r.found,job:$j,token_found:$r.found,token_ref:$r.token_ref,reason:(if $r.found then "token_captured_not_readiness" else "marker_not_found_in_prefix" end),truncated:$r.truncated}'
