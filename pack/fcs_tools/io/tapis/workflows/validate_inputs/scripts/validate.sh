# Verified Pack script; no host shell fallback.
set -eu
printf '%s' "$FCS_INPUT_JSON" | jq -e '
 .params as $p | .target as $t |
 ($p.system.id|type)=="string" and ($p.system.id|length)>0 and
 $p.system.systemType=="LINUX" and $p.system.canExec==true and $p.system.defaultAuthnMethod=="PKI_KEYS" and
 ($p.system|has("authnCredential")|not) and $p.system.host==$t.host and ($p.system.port // 22)==$t.port and
 $p.system.effectiveUserId==$t.login_user and
 ($p.system.jobWorkingDir|type)=="string" and ($p.system.jobWorkingDir|contains("${JobUUID}")) and
 ($p.system.jobWorkingDir|split("/")|all(.[]; .!=".." and .!=".")) and
 ($p.system.jobWorkingDir|explode|all(.[]; .>=32 and .!=127 and .!=92)) and
 (($p.system.owner // $t.tapis_user)==$t.tapis_user or $p.system.owner=="${apiUserId}") and
 (($p.app.owner // $t.tapis_user)==$t.tapis_user or $p.app.owner=="${apiUserId}") and
 ($p.app.id|type)=="string" and ($p.app.id|length)>0 and ($p.app.version|type)=="string" and
 ($p.job.appId // $p.app.id)==$p.app.id and ($p.job.appVersion // $p.app.version)==$p.app.version and
 ($p.job.execSystemId // $p.system.id)==$p.system.id and ($p.app.jobAttributes.execSystemId // $p.system.id)==$p.system.id and
 (($p.job.name|type)=="string") and
 (($p.output.source // "application") as $s | ["application","stdout","archive"]|index($s)!=null) and
 (($p.output.match // "after_literal") as $m | ["prefix","after_literal"]|index($m)!=null) and
 ($p.output.max_bytes // 65536)>0 and ($p.output.max_bytes // 65536)<=65536 and
 ($p.output.max_lines // 200)>0 and ($p.output.max_lines // 200)<=200 and
 (($p.output.file // "flexserv_access_info.txt") as $f | ($f|startswith("/")|not) and ($f|contains("%")|not) and ($f|contains("${")|not) and ($f|contains("HOST_EVAL(")|not) and ($f|split("/")|all(.[]; .!="" and .!="." and .!="..")) and ($f|explode|all(.[]; .>=32 and .!=127 and .!=92)))
' >/dev/null || { echo 'Workflow definitions do not match the approved target or IDs' >&2; exit 1; }
printf '%s' "$FCS_INPUT_JSON" | jq '.params | .ssh_provider=(.ssh_provider // "rust") | .job.appId=.app.id | .job.appVersion=.app.version | .job.execSystemId=.system.id | .app.jobAttributes.execSystemId=.system.id | .output=({source:"application",file:"flexserv_access_info.txt",marker:"FlexServ token: ",match:"after_literal",max_bytes:65536,max_lines:200}+(.output // {}))'
