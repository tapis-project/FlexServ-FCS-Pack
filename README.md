# FlexServ FCS Pack

The production FCS capability collection, version **0.1.0**. It contains 10
toolsets, 42 tools, and 13 skill documents for Tapis operations, node inspection,
and vLLM deployment workflows. Individual tools retain their own versions.

## Install into a running FCS

FCS must trust the pack publisher through embedded anchors or operator policy.
See [release trust and authoring](docs/RELEASE_TRUST.md). Use the administrator secret configured on your FCS, then supply its artifact URL:

```bash
export FLEXSERV_ADMIN_SECRET='your-configured-administrator-secret'
flexserv-fcs pack install \
  https://github.com/OWNER/FlexServ-FCS-Pack/releases/download/v0.1.0/flexserv-fcs-pack-v0.1.0.tar.gz
flexserv-fcs pack status
```

For a remote FCS, add `--server https://fcs.example.org:8090`. Alternatively,
open its `/fcs/tools` page and use **Install an FCS Pack** with the same URL.
FCS downloads, validates, and activates the pack. The FCS and pack major
versions must match; FCS 0.x accepts pack 0.x. Installing does not execute tools
or grant callers additional scopes.

Actions artifact URLs also work when the FCS server has a GitHub token with
Actions read permission. Public release assets require no token. Fixed releases
use tags and assets such as `v0.1.0/flexserv-fcs-pack-v0.1.0.tar.gz`.

## Build or inspect a downloaded pack

```bash
export FCS_RELEASE_BIN=/trusted/path/to/fcs-release
python3 scripts/package_pack.py pack dist/flexserv-fcs-pack.tar.gz
flexserv-fcs pack validate dist/flexserv-fcs-pack.tar.gz --json \
  --allow-dev-artifacts --validation dev-unsigned
python3 -m unittest discover -s tests -v
```

Packaging uses Python and the pinned FCS-owned manifest generator, normalizes archive metadata, and
regenerates checksums in a staging copy without changing `pack/`. The archive
contains `release.manifest.json` and `payload/`; the existing pack files
(`manifest.json`, `checksums.sha256`, `fcs_tools/`) are inside `payload/`.
Official releases also contain `release.signature.json`.
For manual download, fetch a release asset and its `.sha256` sidecar, verify
with `sha256sum -c` (macOS: `shasum -a 256 -c`), then validate with the command
above. The normal CLI/web installation path handles downloads automatically.

## Authoring and prerequisites

Edit the collection under `pack/`; keep docs, tests, and workflows outside it.
Update manifest/toolset entries when adding tools, and keep namespace and path
identities aligned. Refresh source checksums explicitly with
`python3 scripts/package_pack.py pack --refresh-checksums` before packaging source edits. Raw source directories must be repackaged as
release envelopes before FCS can load them. Distribution packaging always refreshes its own
copy. See [format documentation](docs/FORMAT.md).

The distribution is architecture independent. Tapis tools require configured
vault values and permissions. vLLM deployment tools require their documented
Linux/HPC runtime, model, and scheduler prerequisites; loading the collection
on macOS does not imply those tools can execute there.

## Releases and compatibility

Every branch push produces an Actions artifact and rolling release. `main` is
the primary **unsigned development** distribution. Installing branch content
requires server startup `--allow-dev-artifacts` and explicit
`pack install URL --validation dev-unsigned`. Other branches use sanitized names with a hash suffix;
`python3 scripts/distribution.py channel BRANCH` prints the channel name.
Push a tag matching `pack/manifest.json`, such as `v0.1.0`, for protected signing and a fixed release after operator key/tool-pin setup.

[Compatibility checks](docs/COMPATIBILITY.md) run daily at 06:17 UTC and on manual
dispatch against selected FCS and pack branches. [Extraction provenance](EXTRACTION.md)
records the source history. Publishing these local repositories and enabling
Actions is required before GitHub download URLs and schedules become available.
