#!/usr/bin/env python3
"""Generate the five-executor arithmetic demonstration as a standalone Pack."""
import argparse
import json
from pathlib import Path
import tempfile

import yaml

from package_pack import checksums

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = "io.flexserv.demo.arithmetic"
WORKFLOWS = "io.flexserv.demo.workflows"
NUMBER = {"type": "number", "minimum": -1e12, "maximum": 1e12}


def object_schema(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


OPERANDS = object_schema({"a": NUMBER, "b": NUMBER})
VALUE = object_schema({"value": NUMBER})
EXPRESSION = object_schema({key: NUMBER for key in "abcde"})
BATCH = object_schema({"items": {"type": "array", "items": EXPRESSION, "maxItems": 16}})
ITERATION = object_schema({**EXPRESSION["properties"], "iterations": {
    "type": "integer", "minimum": 0, "maximum": 8}})

SCRIPTS = {
    "subtract": r'''set -eu
a=$(printf '%s' "$FCS_INPUT_JSON" | jq -r '.a')
b=$(printf '%s' "$FCS_INPUT_JSON" | jq -r '.b')
result=$(printf 'scale=324; (%s)-(%s)\n' "$a" "$b" | bc)
jq -nc --arg result "$result" '{value:($result|tonumber)}'
''',
    "expression": r'''set -eu
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
''',
    "batch": r'''set -eu
count=$(printf '%s' "$FCS_INPUT_JSON" | jq '.items|length')
results='[]'
for index in $(seq 0 $((count - 1))); do
    fcs_trace iteration sequential_batch "$index"
    input=$(printf '%s' "$FCS_INPUT_JSON" | jq -c --argjson i "$index" '.items[$i]')
    result=$(tool_expression "$input")
    results=$(jq -nc --argjson results "$results" --argjson result "$result" '$results+[$result]')
done
jq -nc --argjson results "$results" '{results:$results}'
''',
    "iterate": r'''set -eu
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
''',
    "parallel_batch": r'''set -eu
items=$(printf '%s' "$FCS_INPUT_JSON" | jq -c '.items')
fcs_map --limit 4 --on-error collect_all tool_expression "$items"
''',
}


def reference(name):
    return {"name": name, "version": VERSION}


def build(destination):
    """Write deterministic, checksum-indexed definitions without modifying other Packs."""
    destination = Path(destination)
    toolsets = []
    descriptions = {
        "add": "Add using the governed host bc CLI executable",
        "subtract": "Subtract using BashKit's in-process bc builtin",
        "divide": "Divide through the outbound Streamable HTTP MCP adapter",
        "square": "Square through the outbound REST adapter",
        "expression": "Combine all five executors with conditional and concurrent execution",
        "batch": "Run complete expressions in a bounded sequential for loop",
        "iterate": "Feed expression results through a bounded while loop",
        "parallel_batch": "Map complete expressions concurrently with ordered collected results",
        "status": "Observe an owned arithmetic workflow",
        "result": "Read the execution report of an owned arithmetic workflow",
        "cancel": "Cancel and join an owned arithmetic workflow",
    }
    for namespace, names in [(OPERATIONS, ["add", "subtract", "divide", "square"]),
                             (WORKFLOWS, ["expression", "batch", "iterate", "parallel_batch", "status", "result", "cancel"])]:
        owner_path = Path("fcs_tools", *namespace.split("."))
        entries = []
        for name in names:
            full_name = namespace + "." + name
            path = destination / owner_path / name
            path.mkdir(parents=True, exist_ok=True)
            control = name in ("status", "result", "cancel")
            # Reuse the authoritative generated native workflow contracts. The
            # dispatcher verifies exact schemas before publishing control roles.
            control_schemas = ROOT / "pack/fcs_tools/io/flexserv/deployments/status/schemas"
            input_schema = json.loads((control_schemas / "input.json").read_text()) if control else {"add": OPERANDS, "subtract": OPERANDS, "divide": OPERANDS,
                            "square": VALUE, "expression": EXPRESSION, "batch": BATCH,
                            "parallel_batch": BATCH, "iterate": ITERATION}[name]
            output_schema = json.loads((control_schemas / "output.json").read_text()) if control else VALUE if name in ("add", "subtract", "divide", "square", "expression") else {"type": "object"}
            spec = {"contract": {"description": descriptions[name], "parameters_schema": input_schema,
                                 "output_schema": output_schema},
                    "skills": [f"skill://{full_name}/{VERSION}/{name}/SKILL.md"],
                    "policy": {"derive": "dependencies"}, "steps": []}
            if control:
                spec["policy"] = {}
                spec["steps"] = [{"id": "control", "kind": "call", "tool": {"name": "workflow." + name, "version": "1.0.0"},
                                  "input": "{{params}}"}]
            elif name == "add":
                spec["policy"] = {"programs": ["bc"], "filesystem": {"read": ["/"], "write": []}}
                spec["steps"] = [{"id": "execute", "kind": "process", "process": "calculator"}]
                spec["processes"] = {"calculator": {"type": "command", "execution_profile": "arithmetic_bc",
                    "program": "bc", "argv": [], "cwd": "{{host.ARITHMETIC_CWD}}",
                    "stdin": "({{params.a|decimal}})+({{params.b|decimal}})\n",
                    "environment": {}, "timeouts": {"execution_seconds": 5}, "output": {"mode": "number"}}}
                spec["result"] = {"value": "{{steps.execute.value}}"}
            elif name == "divide":
                spec["policy"] = {}
                spec["steps"] = [{"id": "execute", "kind": "mcp", "action": "call", "request": {
                    "connection": "arithmetic-demo-mcp", "tool": "divide", "arguments": "{{params}}",
                    "timeout_seconds": 10}}]
                spec["result"] = "{{steps.execute.response.structuredContent}}"
            elif name == "square":
                spec["policy"] = {}
                spec["steps"] = [{"id": "execute", "kind": "rest", "caller": "http", "request": {
                    "connection": "arithmetic-demo-rest", "method": "POST", "body": {"type": "json", "value": "{{params}}"},
                    "response": "json", "timeout_seconds": 10}}]
                spec["result"] = "{{steps.execute.body}}"
            else:
                if name == "subtract":
                    spec["policy"] = {}
                uses = {}
                if name == "expression":
                    uses = {"tool_" + operation: reference(OPERATIONS + "." + operation)
                            for operation in ["add", "subtract", "divide", "square"]}
                    uses["tool_multiply"] = reference("io.flexserv.demo.native.multiply")
                elif name != "subtract":
                    uses = {"tool_expression": reference(WORKFLOWS + ".expression")}
                parameters = {"a": "{{params.a|decimal}}", "b": "{{params.b|decimal}}"} if name == "subtract" else "{{params}}"
                spec["steps"] = [{"id": "execute", "kind": "bashkit", "script": "scripts/run.sh",
                                  "input": parameters, "uses": uses}]
                spec["result"] = "{{steps.execute}}"
                (path / "scripts").mkdir(exist_ok=True)
                (path / "scripts/run.sh").write_text(SCRIPTS[name])
            if namespace == WORKFLOWS and not control:
                # Script bodies can have effects beyond their declared tool calls;
                # the registry therefore requires an explicit ancestor ceiling.
                spec["policy"] = {"programs": ["bc"], "filesystem": {"read": ["/"], "write": []}}
                spec["execution"] = {"mode": "background", "timeout_seconds": 90, "max_calls": 256}
            document = {"schema_version": "flexserv.tool.v1alpha3", "kind": "Tool",
                        "metadata": {"name": full_name, "version": VERSION, "visibility": True,
                                     "labels": {"demo": "arithmetic", "operation": name}}, "spec": spec}
            (path / "tool.yaml").write_text(yaml.safe_dump(document, sort_keys=False))
            skill = path / "skills" / name
            skill.mkdir(parents=True, exist_ok=True)
            (skill / "SKILL.md").write_text(f"---\nname: {name.replace('_', '-')}\ndescription: {descriptions[name]}\n---\n\n"
                f"# {name.replace('_', ' ').title()}\n\n{descriptions[name]}.\n\n"
                "Use the published input schema and a fresh single FCS target. Calls use pinned tool references. "
                "Arithmetic values must be finite and within +/-1e12. Division by zero is an error. "
                "The recorded execution report is authoritative for ordering and timings; replay does not execute tools.\n")
            entries.append({"name": full_name, "version": VERSION, "path": name})
        document = {"schema_version": "flexserv.toolset.v1alpha3", "kind": "ToolSet",
                    "metadata": {"name": namespace, "version": VERSION, "visibility": True},
                    "spec": {"description": "Five-executor arithmetic demonstration", "tools": entries}}
        (destination / owner_path / "toolset.yaml").write_text(yaml.safe_dump(document, sort_keys=False))
        toolsets.append({"name": namespace, "version": VERSION, "path": str(owner_path)})
    manifest = {"schema_version": "flexserv.fcs-pack.v1alpha3", "name": "flexserv-arithmetic-demo",
                "version": VERSION, "target": "any", "toolsets": toolsets}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (destination / "checksums.sha256").write_text(checksums(destination))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("examples/arithmetic-pack/payload"))
    parser.add_argument("--check", action="store_true", help="Fail when generated files differ, without changing the destination")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="arithmetic-pack-check-") as temporary:
            expected = Path(temporary)
            build(expected)
            inventory = lambda root: {str(path.relative_to(root)): path.read_bytes()
                                      for path in root.rglob("*") if path.is_file()}
            if inventory(expected) != inventory(args.output):
                raise SystemExit("Arithmetic Pack differs from its generator; regenerate explicitly")
    else:
        build(args.output)


if __name__ == "__main__":
    main()
