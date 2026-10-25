# Verified Pack script; no host shell fallback.
set -eu
r=$(tool_inspect "$FCS_INPUT_JSON")
tool_confirm "$(jq -nc --argjson r "$r" '{response:$r}')" >/dev/null
jq -ne --argjson r "$r" --argjson p "$FCS_INPUT_JSON" '($r.body.result.uuid // $p.job_uuid)==$p.job_uuid and ($r.body.result.status|type)=="string"' >/dev/null || { echo 'Invalid job observation' >&2; exit 1; }
printf '%s' "$r" | jq --argjson p "$FCS_INPUT_JSON" '.body.result | {job_uuid:$p.job_uuid,status:(.status|ascii_upcase),condition:(.condition // null),last_message:(.lastMessage // .last_message // null),exec_system_id:(.execSystemId // null),exec_system_exec_dir:(.execSystemExecDir // null),exec_system_output_dir:(.execSystemOutputDir // null),archive_system_id:(.archiveSystemId // null),archive_system_dir:(.archiveSystemDir // null),stdout_filename:(.parameterSet.logConfig.stdoutFilename // null)}'
