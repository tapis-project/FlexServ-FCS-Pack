# v0.13 Pack format

ToolSet `metadata.visibility` is now an explicit publication ceiling. Omitted Tool
visibility inherits the owner default; hidden tools remain private in debug and
release. Pinned `spec.extends` aliases consult the source's exact
`spec.exposure.allowed_public_tools`; ordinary calls retain invocation authorization.
Verified tool-local patches cannot widen source exposure or remove restrictions.
See the [framework contract](../../FlexServ-FCS/docs/design/V3_VISIBILITY_INHERITANCE_AND_PATCHES.md).

The new `edu.utexas.tacc.flexserv.deployment.vllm` ToolSet is generated with
`scripts/build_deployment_framework_pack.py --server <fresh-fcs-binary>` and ships
beside both existing workflows. The [runtime guide](../../FlexServ-FCS/docs/DEPLOYMENT_FRAMEWORK.md)
documents its initial single-member execution boundary and MCP call sequence.

`pack/manifest.json` uses `flexserv.fcs-pack.v1alpha3`. Tools use `flexserv.tool.v1alpha3`; namespace paths match tool/toolset names. No old FCS release-envelope CLI is required. The distributable ZIP contains the payload directly. See [the catalog README](../README.md).

The authoring references are maintained alongside the implementation in the
[FlexServ-FCS runtime documentation](https://github.com/tapis-project/FlexServ-FCS/tree/feature/new_fcs/docs):
`TOOL_DEFINITION.md` covers Tool fields and step kinds, `TOOLSET_DEFINITION.md`
covers Toolset membership and Pack indexing, and `NATIVE_TOOLS.md` explains
native implementations and YAML wrappers. `PACK_FORMAT.md` is the entry point
for Pack-wide integrity and loading rules. Use the documentation matching the
Capability Server version that will load the Pack.
