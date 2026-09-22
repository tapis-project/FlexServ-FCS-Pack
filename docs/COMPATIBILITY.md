# FCS pack loading compatibility

The daily workflow tests current `main` pack contents against the latest
successful FCS `main` build. It does not select the latest version-tagged pack
release. Manual dispatch accepts independent `fcs_branch` and `pack_branch`
inputs, both defaulting to `main`.

FCS defaults to `OWNER/FlexServ-FCS`, where OWNER is this repository's owner.
Set repository variable `FCS_REPOSITORY` to override it. For a private FCS
repository, configure secret `FCS_ARTIFACT_READ_TOKEN` with Actions read access.
The built-in workflow token reads this repository's temporary pack artifact.
The FCS build workflow file must be named `build.yml`.

The workflow records the exact FCS commit/run and pack commit. On Linux amd64,
Linux arm64, macOS amd64, and macOS arm64 it verifies binary metadata/checksums,
starts a fresh FCS, installs the pack using the uploaded GitHub artifact URL,
checks REST/MCP tool and skill discovery, and restarts FCS to verify persistence.
No deployment, model download, GPU workload, or Tapis request is executed.

Expired or missing build artifacts fail explicitly. A failing newest build is
not selected; the summary identifies the successful revision actually tested.
The schedule becomes active when this workflow is published on the default
branch. Failed jobs retain FCS logs in workflow artifacts.

For operator errors during installation, inspect the structured error code and
stage. `incompatible_version` requires matching FCS/pack majors; `disk_full`
requires freeing storage/quota; `permission_denied` requires service-account
write access; GitHub access/expiry errors require a readable current URL or
correctly configured server token. Failed updates preserve the active pack.

## Trust profiles

The moving-branch workflow explicitly selects `dev-unsigned`, enables the FCS
startup development allowance, and verifies the unsigned binary inventory using
an independently pinned verifier. It retains runtime authentication, integrity,
semantic checks, and persistence checks. It does not establish publisher trust.

`released-compatibility.yml` separately tests signed releases pinned by archive
and manifest digest, including the declared minimum FCS version on each host.
Configure CI tool pins, release combinations, and public publisher policies as
described in [release trust](RELEASE_TRUST.md). Missing configuration fails
clearly; there is no fallback to branch executables or test keys.
