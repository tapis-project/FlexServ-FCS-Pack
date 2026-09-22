# Extraction provenance

Source: FlexServ, branch `feature/1.5.0`, commit
`df650043eb29d7c9c004f10b74611653b0bb365c`.

`git subtree split --prefix=flexserv/fcs/sample_pack` preserved the collection's
history. The extracted files were relocated to `pack/`; all 10 toolsets and
their tool, policy, patch, script, schema, and skill assets are retained.
The pack version starts at 0.1.0. Runtime prerequisites remain specific to
each tool; the declarative distribution itself is architecture independent.
