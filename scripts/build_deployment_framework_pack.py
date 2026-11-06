#!/usr/bin/env python3
"""Generate the new public deployment tools from authoritative native contracts."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import yaml
from package_pack import checksums

COMMON = "edu.utexas.tacc.flexserv.deployment"
PUBLIC = COMMON + ".vllm"
VERSION = "1.0.0"


def build(server, source):
    """Add the new ToolSet without modifying either existing deployment workflow."""
    exported = json.loads(subprocess.check_output([str(server), "--export-native-contracts"]))
    contracts = {tool["name"]: tool for tool in exported["tools"]}
    relative = Path("fcs_tools", *PUBLIC.split("."))
    root = source / relative
    entries = []
    definitions = {
        "environment.inspect": "environment.inspect",
        "recipe.resolve": "recipe.resolve",
        "prepare": "prepare",
        "plan": "planning.reserve",
        "execute": "execution.start",
        "monitor": "monitor",
        "cancel": "cancel",
    }
    for public, native_suffix in definitions.items():
        native = COMMON + "." + native_suffix
        contract = contracts[native]
        path = root.joinpath(*public.split("."))
        path.mkdir(parents=True, exist_ok=True)
        spec = {}
        if public in ("monitor", "cancel"):
            # Explicit re-export: checked against the native source's exposure list.
            spec["extends"] = {"name": native, "version": contract["version"]}
        else:
            parameters = contract["parameters_schema"]
            schema = copy.deepcopy(parameters["properties"]["input"])
            if "$defs" in parameters:
                schema["$defs"] = copy.deepcopy(parameters["$defs"])
            if "$ref" in schema:
                definition = schema["$ref"].removeprefix("#/$defs/")
                schema = dict(schema["$defs"][definition], **{"$defs": schema["$defs"]})
            (path / "schemas").mkdir(exist_ok=True)
            (path / "schemas/input.json").write_text(json.dumps(schema, indent=2) + "\n")
            (path / "schemas/output.json").write_text(json.dumps(contract["output_schema"], indent=2) + "\n")
            spec = {
                "contract": {"description": contract["description"], "parameters_schema": "schemas/input.json", "output_schema": "schemas/output.json"},
                "policy": {"derive": "dependencies", "resources": ["local_vllm"]},
                "steps": [{"id": "operation", "kind": "call", "tool": {"name": native, "version": contract["version"]}, "input": {"profile": "local_vllm", "input": "{{params}}"}}],
                "result": "{{steps.operation}}",
            }
            if public == "prepare":
                spec["execution"] = {"mode": "background", "timeout_seconds": 7200, "max_calls": 512}
        (path / "tool.yaml").write_text(yaml.safe_dump({
            "schema_version": "flexserv.tool.v1alpha3", "kind": "Tool",
            "metadata": {"name": PUBLIC + "." + public, "version": VERSION, "visibility": True}, "spec": spec,
        }, sort_keys=False))
        guide = path / "skills/deployment/SKILL.md"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text(f"---\nname: deployment-{public.replace('.', '-')}\ndescription: Use the reviewed vLLM deployment tools through an authorized FCS target.\n---\n\n# {PUBLIC}.{public}\n\nUse this tool with one authorized FCS target. "
                         "Retain owner-bound references from inspect and prepare; plan returns the exact reviewed "
                         "revision and digest. Execute accepts those references, never a caller-supplied command. "
                         "Monitor can poll or return an authenticated event subscription. Cancel handles startup "
                         "cancellation and stopping a ready deployment. The new executor currently supports "
                         "single-node TP/PP; use the retained reviewed workflow for other layouts.\n")
        entries.append({"name": PUBLIC + "." + public, "version": VERSION, "path": "/".join(public.split("."))})
    (root / "toolset.yaml").write_text(yaml.safe_dump({
        "schema_version": "flexserv.toolset.v1alpha3", "kind": "ToolSet",
        "metadata": {"name": PUBLIC, "version": VERSION, "visibility": True},
        "spec": {"description": "Evidence-based reviewed vLLM deployment", "tools": entries},
    }, sort_keys=False))
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["toolsets"] = [entry for entry in manifest["toolsets"] if entry["name"] != PUBLIC]
    manifest["toolsets"].append({"name": PUBLIC, "version": VERSION, "path": str(relative)})
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (source / "checksums.sha256").write_text(checksums(source))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("pack"))
    arguments = parser.parse_args()
    build(arguments.server.resolve(), arguments.source)
