# Verified Pack script; no host shell fallback.
set -eu
j=$(printf '%s' "$FCS_INPUT_JSON" | jq -c '.job')
s=$(printf '%s' "$FCS_INPUT_JSON" | jq -r '.output.source')
case "$s" in
 application) loc=$(jq -nc --argjson j "$j" --argjson p "$FCS_INPUT_JSON" '{system_id:$j.exec_system_id,base:$j.exec_system_output_dir,path:$p.output.file}') ;;
 stdout) loc=$(printf '%s' "$j" | jq '{system_id:.exec_system_id,base:.exec_system_exec_dir,path:.stdout_filename}') ;;
 archive) loc=$(printf '%s' "$FCS_INPUT_JSON" | jq '{system_id:.job.archive_system_id,base:.job.archive_system_dir,path:.output.file}') ;;
 *) echo 'Unsupported output source' >&2; exit 1 ;;
esac
if ! printf '%s' "$loc" | jq -e '.system_id!=null and .base!=null and .path!=null' >/dev/null; then printf '%s\n' '{"available":false}'; exit 0; fi
if [ "$s" = archive ] && [ "$(printf '%s' "$j" | jq -r '.status')" != FINISHED ]; then printf '%s\n' '{"available":false}'; exit 0; fi
r=$(tool_system "$(printf '%s' "$loc" | jq '{system_id:.system_id}')")
tool_confirm "$(jq -nc --argjson r "$r" '{response:$r}')" >/dev/null
path=$(tool_path "$(jq -nc --argjson l "$loc" --argjson r "$r" '{root:($r.body.result.rootDir // "/"),base:$l.base,path:$l.path}')")
jq -nc --argjson l "$loc" --argjson p "$path" '$p + {available:true,system_id:$l.system_id}'
