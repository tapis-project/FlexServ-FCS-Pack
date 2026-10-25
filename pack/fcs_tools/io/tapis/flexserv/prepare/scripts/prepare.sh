# Verified Pack script; no host shell fallback.
set -eu
printf '%s' "$FCS_INPUT_JSON" | jq -e '
 .params as $p | $p.deployment as $d |
 [$d.allocation,$d.queue,$d.private_model_dir,$d.public_model_dir,$d.sif_path,$d.cache_dir] | all(.[]; type=="string" and length>0 and (contains("<<")|not) and (contains("\n")|not))
' >/dev/null || { echo 'Explicit allocation, queue, model, SIF and cache paths are required' >&2; exit 1; }
printf '%s' "$FCS_INPUT_JSON" | jq -e '
 def valid_label: type=="string" and length>0 and length<=128 and (explode | all(.[]; (.>=48 and .<=57) or (.>=65 and .<=90) or (.>=97 and .<=122) or .==45 or .==95 or .==46));
 .params.deployment as $d | ($d.allocation|valid_label) and ($d.queue|valid_label) and (($d.reservation // "") as $r | $r=="" or ($r|valid_label))
' >/dev/null || { echo 'Allocation, queue or reservation label is invalid' >&2; exit 1; }
printf '%s' "$FCS_INPUT_JSON" | jq -e '
 .params as $p |
 ($p.app_overrides.id // $p.app_id)==$p.app_id and ($p.app_overrides.version // "1.4.0")=="1.4.0" and
 ($p.app_overrides.runtime // "ZIP")=="ZIP" and ($p.app_overrides.jobType // "BATCH")=="BATCH" and
 ($p.app_overrides.jobAttributes.execSystemId // $p.system.id)==$p.system.id and
 ($p.job_overrides.appId // $p.app_id)==$p.app_id and ($p.job_overrides.appVersion // "1.4.0")=="1.4.0" and ($p.job_overrides.execSystemId // $p.system.id)==$p.system.id
' >/dev/null || { echo 'Template override conflicts with selected IDs or runtime' >&2; exit 1; }
printf '%s' "$FCS_INPUT_JSON" | jq -e '
 .params as $p | ([$p.app_overrides.jobAttributes.parameterSet.envVariables[]?,$p.job_overrides.parameterSet.envVariables[]?] | all(.[]; .key!="HUGGINGFACE_TOKEN" and .key!="FLEXSERV_TOKEN")) and ([$p.app_overrides.jobAttributes.parameterSet.appArgs[]?,$p.job_overrides.parameterSet.appArgs[]?] | all(.[]; .name!="flexServSecret"))
' >/dev/null || { echo 'Plaintext token overrides are unsupported; use an approved secret consumer' >&2; exit 1; }
printf '%s' "$FCS_INPUT_JSON" | jq '
 def entries($key): if type!="array" then error("Parameter list must be an array") elif any(.[]; (.[$key]|type)!="string" or (.[$key]|length)==0) then error("Parameter key required") elif (map(.[$key])|unique|length)!=length then error("Duplicate parameter key") else . end;
 def merge_entries($base;$over;$key): ($base|entries($key)) as $b | ($over|entries($key)) as $o | [$b[] | . as $x | ($o | map(select(.[$key]==$x[$key])) | .[0]) as $r | if $r==null then . else .+$r end] + [$o[] | . as $x | select(($b | map(.[$key]) | index($x[$key]))==null)];
 def parameters($base;$over): ($base + $over) + {appArgs:merge_entries(($base.appArgs // []);($over.appArgs // []);"name"),envVariables:merge_entries(($base.envVariables // []);($over.envVariables // []);"key"),schedulerOptions:merge_entries(($base.schedulerOptions // []);($over.schedulerOptions // []);"name"),logConfig:(($base.logConfig // {})+($over.logConfig // {}))};
 .params as $p | $p.deployment as $d | .app as $original_app | .job as $original_job | (.app + ($p.app_overrides // {})) as $a | (.job + ($p.job_overrides // {})) as $j |
 ($a | .id=$p.app_id | .version="1.4.0" | .jobAttributes=($original_app.jobAttributes+($p.app_overrides.jobAttributes // {})) | .jobAttributes.execSystemId=$p.system.id | .jobAttributes.execSystemLogicalQueue=$d.queue | .jobAttributes.parameterSet=parameters($original_app.jobAttributes.parameterSet;($p.app_overrides.jobAttributes.parameterSet // {}))) as $app |
 ($j | .appId=$p.app_id | .appVersion="1.4.0" | .execSystemId=$p.system.id | .execSystemLogicalQueue=$d.queue | .parameterSet=parameters($original_job.parameterSet;($p.job_overrides.parameterSet // {}))) as $job |
 {system:$p.system,target:$p.target,ssh_provider:($p.ssh_provider // "rust"),app:$app,job:$job} |
 .app.jobAttributes.parameterSet.appArgs |= map(select(.name!="flexServSecret")) |
 .app.jobAttributes.parameterSet.envVariables |= map(select(.key!="HUGGINGFACE_TOKEN" and .key!="FLEXSERV_TOKEN")) |
 .job.parameterSet.appArgs |= map(select(.name!="flexServSecret")) |
 .job.parameterSet.envVariables |= map(select(.key!="HUGGINGFACE_TOKEN" and .key!="FLEXSERV_TOKEN")) |
 .app.jobAttributes.parameterSet.logConfig=({stdoutFilename:"flexserv.out",stderrFilename:"flexserv.err"} + .app.jobAttributes.parameterSet.logConfig | .stdoutFilename= (if .stdoutFilename=="" then "flexserv.out" else .stdoutFilename end) | .stderrFilename=(if .stderrFilename=="" then "flexserv.err" else .stderrFilename end)) |
 .job.parameterSet.logConfig=({stdoutFilename:"flexserv.out",stderrFilename:"flexserv.err"} + .job.parameterSet.logConfig) |
 .job.parameterSet.envVariables=merge_entries(.job.parameterSet.envVariables;[{key:"PRI_MODEL_HOST",value:$d.private_model_dir},{key:"PUB_MODEL_HOST",value:$d.public_model_dir},{key:"APPTAINER_IMAGE",value:$d.sif_path},{key:"APPTAINER_CACHEDIR",value:$d.cache_dir}];"key") |
 .app.jobAttributes.parameterSet.envVariables=merge_entries(.app.jobAttributes.parameterSet.envVariables;[{key:"PRI_MODEL_HOST",value:$d.private_model_dir},{key:"PUB_MODEL_HOST",value:$d.public_model_dir},{key:"APPTAINER_CACHEDIR",value:$d.cache_dir}];"key") |
 .job.parameterSet.schedulerOptions |= map(select(.name!="Reservation Name" and .name!="TACC Resource Allocation")) |
 .job.parameterSet.schedulerOptions += [{name:"TACC Resource Allocation",include:true,arg:("-A "+$d.allocation)}] |
 if ($d.reservation // "")!="" then .job.parameterSet.schedulerOptions += [{name:"Reservation Name",arg:("--reservation "+$d.reservation)}] else . end |
 if ([.app.jobAttributes.parameterSet.logConfig.stdoutFilename,.app.jobAttributes.parameterSet.logConfig.stderrFilename,.job.parameterSet.logConfig.stdoutFilename,.job.parameterSet.logConfig.stderrFilename] | all(.[]; type=="string" and length>0 and length<=256 and (contains("/")|not) and (contains("\n")|not))) then . else error("Log names must be nonempty filenames") end
'
