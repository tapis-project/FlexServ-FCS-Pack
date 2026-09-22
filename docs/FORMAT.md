# FCS Pack format

An FCS Pack is a versioned, integrity-checked distribution of namespaced
capabilities for the FlexServ Capability Server. Normally install its GitHub
artifact URL through the CLI or web interface. `FLEXSERV_FCS_TOOL_DIR` can point
to a verified release envelope as an initial fallback before managed installation.
The layout below describes `payload/` inside that envelope; see
[release trust](RELEASE_TRUST.md) for the required outer manifest and signature.

## Layout

```text
payload/
├── manifest.json
├── checksums.sha256
└── fcs_tools/
    ├── edu/utexas/tacc/vllm/
    │   ├── toolset.yaml
    │   ├── .skills/       # optional toolset-level skills
    │   ├── single-node/
    │   │   ├── tool.yaml
    │   │   ├── scripts/      # optional helper scripts
    │   │   ├── skills/       # optional leaf tool skills
    │   │   ├── signatures/   # optional tool/asset signatures
    │   │   ├── policies/     # optional policy artifacts
    │   │   ├── schemas/      # optional schemas
    │   │   └── patches/      # optional YAML overlays for tool.yaml
    │   ├── multi-node/
    │   │   └── tool.yaml
    │   └── pd/
    │       └── tool.yaml
    └── io/tapis/jobs/
        ├── toolset.yaml
        ├── .skills/README.md
        ├── submit/tool.yaml
        ├── get/tool.yaml
        ├── cancel/tool.yaml
        └── logs/tool.yaml
```

The required `tool.yaml` identity must match its reverse-DNS namespace and
directory. For example, `metadata.name:
edu.utexas.tacc.vllm.single-node` has exactly one valid directory:
`fcs_tools/edu/utexas/tacc/vllm/single-node`.

A `toolset.yaml` is a group index, not an executable tool. It declares a parent
namespace and references child directories:

```yaml
schema_version: flexserv.toolset.v1alpha1
kind: ToolSet
metadata:
  name: edu.utexas.tacc.vllm
  version: 0.1.0
spec:
  description: TACC vLLM deployment capabilities.
  tools:
    - name: edu.utexas.tacc.vllm.single-node
      version: 0.1.0
      path: single-node
    - name: edu.utexas.tacc.vllm.multi-node
      version: 0.1.0
      path: multi-node
```

Child `path` values are normalized namespace segments and may be nested, such
as `outputs/read`. FCS converts path separators to dots, derives the expected
child name as `<toolset name>.<child namespace>`, and rejects mismatches.

Toolset-level skills live in `.skills/` so they do not collide with child tool
directories. Leaf tool skills live in `skills/`. Both directories are optional,
both are covered by `checksums.sha256`, and FCS indexes their UTF-8 file content
at startup.

The FCS Pack currently declares these toolsets and leaf tools:

```text
edu.utexas.tacc.vllm
├── single-node
├── multi-node
└── pd

edu.utexas.tacc.node
└── snapshot

io.tapis.agentic
├── model
└── control-flow

io.tapis.jobs
├── submit
├── get
├── cancel
└── logs

io.tapis.apps
├── create
└── get

io.tapis.systems
├── create
├── get
├── update
└── delete

tapis-core
├── io.tapis.context.get
├── io.tapis.access.check
├── io.tapis.systems.search
├── io.tapis.systems.get
├── io.tapis.apps.search
└── io.tapis.apps.get

tapis-files
├── io.tapis.files.list
├── io.tapis.files.stat
├── io.tapis.files.read
├── io.tapis.files.stage
├── io.tapis.files.transfer
└── io.tapis.files.mkdir

tapis-jobs
├── io.tapis.jobs.prepare
├── io.tapis.jobs.submit
├── io.tapis.jobs.search
├── io.tapis.jobs.inspect
├── io.tapis.jobs.wait
├── io.tapis.jobs.cancel
├── io.tapis.jobs.outputs.list
├── io.tapis.jobs.outputs.read
└── io.tapis.jobs.outputs.download

tapis-pods
├── io.tapis.pods.search
├── io.tapis.pods.deploy_from_template
├── io.tapis.pods.inspect
├── io.tapis.pods.wait
├── io.tapis.pods.logs
├── io.tapis.pods.start
├── io.tapis.pods.stop
├── io.tapis.pods.restart
└── io.tapis.pods.delete
```

The official-style Tapis catalog lives alongside the existing tools under
`fcs_tools/io/tapis`. Toolsets may declare normalized nested child paths, so
`io.tapis.jobs.outputs.read` is owned by `io.tapis.jobs` at
`outputs/read`. Catalog grouping is also recorded in each new tool's `pack`
label. Capability namespace segments accept lowercase letters, digits, hyphens,
and underscores.

## Manifest

`manifest.json` uses `schema_version: flexserv.fcs-pack.v1alpha1`. It can
declare direct executable `tools`, namespace `toolsets`, or both. Every entry
declares `name`, `version`, and `path`. Direct tool names and versions must
match the effective `tool.yaml`; toolset names and versions must match
`toolset.yaml`. The JSON Schemas are at
`FlexServ-FCS/schemas/fcs-pack-manifest.schema.json` and
`FlexServ-FCS/schemas/fcs-pack-toolset.schema.json`.

```json
{
  "schema_version": "flexserv.fcs-pack.v1alpha1",
  "name": "flexserv-fcs-pack",
  "version": "0.1.0",
  "target": "any",
  "toolsets": [
    {
      "name": "edu.utexas.tacc.vllm",
      "version": "0.1.0",
      "path": "fcs_tools/edu/utexas/tacc/vllm"
    },
    {
      "name": "edu.utexas.tacc.node",
      "version": "0.1.0",
      "path": "fcs_tools/edu/utexas/tacc/node"
    },
    {
      "name": "io.tapis.agentic",
      "version": "0.1.0",
      "path": "fcs_tools/io/tapis/agentic"
    }
  ]
}
```

## Tool execution types

FCS currently supports four execution categories. A single leaf `tool.yaml` can
still be a multi-step pipeline and can mix step kinds when the policy allows it.

| FCS type | YAML step kind | Typical policy control |
| --- | --- | --- |
| `LOCAL` | `cmd` | sandbox, executable allowlist, filesystem roots, resources |
| `REST` | `rest` | host/scheme allowlist, TLS requirement, rate limits, secret refs |
| `MCP` | `mcp` | server/tool allowlist and caller policy |
| `BUILTIN` | `native` | in-process built-in registry and scoped inputs |

REST tools use `secret_refs` to request values from FCS's in-memory secret
vault. For example, the Tapis examples refer to `tapis.base_url` and
`tapis.access_token`; neither value is stored in the pack.

## Skills API

FCS exposes pack skills through signed service APIs. The API returns only skill
files that were indexed during pack loading; it does not read arbitrary paths at
request time.

List every indexed skill and its content:

```http
GET /fcs/v1/skills
```

Fetch one skill by owner path and relative skill path:

```http
GET /fcs/v1/skills/content?owner_path=fcs_tools/edu/utexas/tacc/vllm&skill_path=README.md
```

The response shape is:

```json
{
  "skill": {
    "owner_kind": "tool_set",
    "owner_name": "edu.utexas.tacc.vllm",
    "owner_path": "fcs_tools/edu/utexas/tacc/vllm",
    "skill_path": "README.md",
    "content": "# TACC vLLM toolset skills\n..."
  }
}
```

## Checksums and filesystem safety

`checksums.sha256` uses the standard SHA-256 text format:

```text
<64 lowercase hex characters>  manifest.json
<64 lowercase hex characters>  fcs_tools/edu/utexas/tacc/vllm/toolset.yaml
<64 lowercase hex characters>  fcs_tools/edu/utexas/tacc/vllm/single-node/tool.yaml
```

Every regular file in the pack except `checksums.sha256` must appear exactly
once. Extra entries, missing entries, digest mismatches, absolute/traversal
paths, symbolic links, and non-regular files make FCS startup fail.

Files under a leaf tool's optional `signatures/` directory are currently opaque,
checksummed assets. The `v1alpha1` loader does not yet select trust roots or
verify a signature format, so `checksums.sha256` provides consistency checking,
not publisher authenticity.

## YAML patches

Files directly under a tool's `patches/` directory must end in `.yaml` or
`.yml`. FCS applies them in lexical filename order before validating and
registering the tool. Mappings merge recursively, scalar and sequence values
replace the previous value, and `null` removes a mapping key. The effective
name and version must still match the manifest.

Prefix patches numerically when order matters, for example
`10-site-defaults.yaml` and `20-cluster-overrides.yaml`.

## Packaging

The packaging helper refreshes `checksums.sha256`, rejects symlinks, and creates
an archive containing the pack directory:

```bash
scripts/package_fcs_pack.sh \
  pack \
  dist/flexserv-fcs-pack-0.1.0-any.tar.gz
```

## Compatibility

The existing flat directory of `*.yaml` tool definitions and optional
`fcs-config.yaml` is still accepted for migration. A directory containing
either `manifest.json` or `fcs_tools/` is treated as a pack and must satisfy the
complete pack contract; incomplete packs do not fall back to legacy loading.

See `pack` for a loadable hierarchical pack example.
