# v0.13 Pack format

`pack/manifest.json` uses `flexserv.fcs-pack.v1alpha2`. Tools use `flexserv.tool.v1alpha2`; namespace paths match tool/toolset names. No old FCS release-envelope CLI is required. The distributable ZIP contains the payload directly. See [the catalog README](../README.md).

The authoring references are maintained alongside the implementation in the
[FlexServ-FCS runtime documentation](https://github.com/tapis-project/FlexServ-FCS/tree/feature/new_fcs/docs):
`TOOL_DEFINITION.md` covers Tool fields and step kinds, `TOOLSET_DEFINITION.md`
covers Toolset membership and Pack indexing, and `NATIVE_TOOLS.md` explains
native implementations and YAML wrappers. `PACK_FORMAT.md` is the entry point
for Pack-wide integrity and loading rules. Use the documentation matching the
Capability Server version that will load the Pack.
