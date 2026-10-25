# FlexServ Capability Pack

This branch is the canonical v0.13 `flexserv.fcs-pack.v1alpha2` catalog. One Pack
contains the Tapis provisioning workflows under `io.tapis`, deployment workflows
under `io.flexserv.deployments`, and reusable SSH, path and content tools under
`io.flexserv`. Tool names, versions, visibility and physical toolset contexts are
preserved. Loading a Pack never installs a key, submits a job or deploys a model.

```bash
bash scripts/package_fcs_pack.sh
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

`dist/flexserv-capability-pack.zip` contains `manifest.json`, `checksums.sha256`
and `fcs_tools/` at its root. Packaging is deterministic and requires no Rust
packaging executable. Runtime approvals are generated from the exact installed
Capability Server and merged Pack; do not reuse old standalone Tapis poll pins.

GitHub Actions builds the ZIP and checksum. The Deployer pins this repository's
commit, includes that ZIP with two architectures of Gateway and FCS, and records
all selected revisions in `BUILD.json`. The raw Pack is architecture-independent;
its host policy remains specific to the deployment and binary.

The original pre-v0.13 catalog remains in the repository's previous branches.
It is not loaded alongside this catalog. Configure Tapis connections and SSH
resources explicitly before using those tools; discovery needs no Tapis token.
