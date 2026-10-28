# FlexServ Capability Pack

`feature/new_fcs` is the canonical v0.13 `flexserv.fcs-pack.v1alpha2` catalog. One source catalog
contains the Tapis provisioning workflows under `io.tapis`, deployment workflows
under `io.flexserv.deployments`, and reusable SSH and path tools under
`io.flexserv`. Loading a Pack never installs a key, submits a job or deploys a model.

The Tapis-owned credential scanner is now the hidden tool
`io.tapis.access.credentials.scan_to_secret`; its implementation uses the unchanged
general native primitive `content.scan_to_secret`. Custom workflows migrating to
this Pack must update references to the former `io.flexserv.content.scan_to_secret`.
Previously published Pack archives are unchanged.

```bash
python3 scripts/split_packs.py
# Load the verified extracted payload using the current Capability Server.
flexserv-capability-server --pack pack --check-pack --allow-unsigned-demo
```

The development flag is only for local inspection. Slurm uses the host-approved
SHA-256 of `checksums.sha256`, not the demo flag. The complete inventory covers
all scripts, schemas, JSON assets, skills and definitions. A changed payload
requires an explicit checksum refresh and review:

```bash
python3 scripts/package_pack.py pack --refresh-checksums
python3 -m unittest discover -s tests -p 'test_packaging.py'
```

Each ZIP contains `manifest.json`, `checksums.sha256` and `fcs_tools/` at its
root. Packaging is deterministic and requires no Rust packaging executable.
Runtime approvals are generated from the exact installed Capability Server and
selected Packs; do not reuse old standalone Tapis poll pins.

GitHub Actions publishes two standalone archives: `tapis-workflow-pack.zip`
(Tapis namespaces plus reusable SSH/path tools) and `vllm-pack.zip`
(deployment tools). Their toolsets are disjoint. They derive from this catalog;
definitions are not maintained twice. Each archive has a fresh manifest and full
inventory. `pack-source.json` identifies the source commit and Pack versions, and
`release-assets.sha256` covers every release asset. Push an existing `pack-v*` tag
or manually publish a pre-created tag at the selected commit.

The deployment archive records the chosen Pack release tag; the Capability Server
prepares and validates the individual ZIPs at startup. Each Pack keeps its own
provenance and toolset context; conflicts are rejected. The raw Packs are
architecture-independent; host policy remains specific to the deployment and binary.

The original pre-v0.13 catalog remains in the repository's previous branches.
It is not loaded alongside this catalog. Configure Tapis connections and SSH
resources explicitly before using those tools; discovery needs no Tapis token.
