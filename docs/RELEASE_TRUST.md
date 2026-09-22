# Signed releases, authoring, and development

Only matching version-tag releases signed by an authorized pack publisher are
production releases. Every-branch artifacts, including `main`, are unsigned
development content. Both the old inner checksums and the new complete signed
inventory are validated; neither a valid signature nor installation grants
runtime scopes, credentials, or execution permissions.

## Install

Configure FCS with a public publisher policy (`serve --trust-policy FILE`) or
use a distribution with the appropriate embedded pack anchors. Start it with
the usual service/admin authentication and writable `FLEXSERV_FCS_DATA_DIR`.
Then use the authenticated CLI or `/fcs/tools` panel:

```bash
flexserv-fcs pack install https://github.com/ORG/FlexServ-FCS-Pack/releases/download/v0.1.0/flexserv-fcs-pack-v0.1.0.tar.gz
flexserv-fcs pack status --json
```

No manual unpacking is needed. Actions links require a server-configured GitHub
token with Actions read permission; private releases need Contents read access.
Never place tokens in submitted URLs. For offline checks:

```bash
flexserv-fcs pack validate signed-pack.tar.gz --trust-policy /etc/fcs/trust.json --json
```

For offline startup, set `FLEXSERV_FCS_TOOL_DIR` to the downloaded signed envelope
directory/archive and pass `--trust-policy` to FCS. It verifies and copies the
input into a private snapshot. This initial fallback is superseded by any
managed active pack. Installed content and current policy are rechecked on
restart. FCS/pack majors must match; the signed range, pack API, features,
platforms, and operator restrictions may further limit compatibility.

## Author and package

Edit production tools only under `pack/`. Update both `pack/manifest.json` and
`release-descriptor.json` when changing the product version. The descriptor
declares `flexserv/fcs-pack`, required FCS versions, API, features, supported
platforms, and entrypoints. The packaging script fills the exact Git revision
and CI repository/tag, copies into staging, regenerates inner checksums,
normalizes modes, and invokes the shared Rust generator for the outer inventory.
It leaves the source checkout unchanged.

```bash
export FCS_RELEASE_BIN=/independently/trusted/fcs-release
python3 scripts/package_pack.py pack dist/development-pack.tar.gz
flexserv-fcs pack validate dist/development-pack.tar.gz --allow-dev-artifacts \
  --validation dev-unsigned --json
```

The envelope contains `release.manifest.json`, optional development/required
production `release.signature.json`, and `payload/` containing the original pack.
Only regular 0644/0755 files are allowed. The signed inventory lists every file,
size, mode, and SHA-256. It rejects extra/missing files, links, special/sparse
entries, duplicate paths/JSON keys, traversal, non-NFC Unicode, and case-fold
collisions. Archives use USTAR; do not generate PAX or GNU extension records.
Keep tool runtime state and operator configuration outside the snapshot.

To install a branch artifact, start FCS with `--allow-dev-artifacts`, then use
`pack install URL --validation dev-unsigned`. Offline validation requires both
flags. The web page offers development selection only after reading the
server's allowance. Reports explicitly say `development_untrusted`; integrity,
semantic checks, and runtime authentication remain enabled. Strict failures
never silently retry in development mode.

## Public policies and key rotation

FCS policy keys are Base64-encoded raw 32-byte Ed25519 public keys, scoped to an
exact role, artifact ID, and source repository. For example, the `keys` entry
below belongs in a `{"schema_version":1,"keys":[...]}` policy:

```json
{
  "key_id": "pack-publisher-2026",
  "public_key": "BASE64_PUBLIC_KEY",
  "artifact_kind": "fcs-pack",
  "artifact_id": "flexserv/fcs-pack",
  "repository": "https://github.com/YOUR_ORG/FlexServ-FCS-Pack"
}
```

No usable production key is committed. Use different private keys for FCS,
Pack, and Gateway roles. Add a new public key ID to operators/FCS builds before
switching signers. Revoke old IDs with `revoked_key_ids`; operator revocations
override embedded trust. Changing a key's public bytes or scope under its old
ID fails. Operators may also restrict manifest digests and minimum versions.
Pins are deployment choices and need not change on every component version.

## Configure CI before publication

`ci-tools.lock.json` deliberately starts empty. Fill `platforms` for
`linux-amd64`, `linux-arm64`, `macos-amd64`, and `macos-arm64`. Each platform
needs a `fcs-release` entry. Linux amd64 signing also needs `fcs-release-sign`
and `flexserv-fcs` entries, for example:

```json
{
  "schema_version": 1,
  "platforms": {
    "linux-amd64": {
      "fcs-release": {
        "url": "https://github.com/ORG/FlexServ-FCS/releases/download/v0.1.0/flexserv-fcs-v0.1.0-linux-amd64.tar.gz",
        "sha256": "INDEPENDENTLY_REVIEWED_ARCHIVE_SHA256",
        "member": "payload/fcs-release"
      }
    }
  }
}
```

The signer comes from FCS's separately published `fcs-release-ci-tools-...`
archive (`payload/fcs-release-sign`), never the runtime binary archive.
`fetch_ci_tools.py` verifies the configured archive digest before extracting or
executing a tool. Obtain these digests through independent review; a checksum
fetched beside an arbitrary executable is not a trust anchor. Do not replace
missing pins with a moving branch download.

Create a protected `release` environment restricted to matching version tags.
Set secret `RELEASE_SIGNING_PRIVATE_KEY` to the repository's Ed25519 PKCS#8 PEM,
and variables `RELEASE_SIGNING_KEY_ID` and `RELEASE_SIGNING_PUBLIC_POLICY` (full
public policy JSON for this pack publisher). Build/package jobs have no signing
secret. The separate protected job verifies inventory and semantics with pinned
tools, signs the final manifest bytes, verifies the resulting archive, uploads
all assets to a draft, checks completeness, then publishes. Source and built
payloads contain no production private keys. Missing keys/pins fail clearly.

The daily/manual moving-branch check enables development explicitly and still
tests real URL installation, REST/MCP discovery, runtime authentication, and
restart on all four hosts. A separate strict released-compatibility workflow
reads `compatibility-releases.lock.json`. Add a combination for the declared
minimum FCS version on every host and any additional supported FCS versions.
Each release entry contains `platform`, `fcs_version`, and `fcs`/`pack` objects
with `url`, `archive_sha256`, and `manifest_sha256`. Configure repository variable
`RELEASE_COMPATIBILITY_POLICY` with both publishers' public policies. Empty pins
fail; the workflow never substitutes unsigned content.

## Migration and troubleshooting

Legacy unsigned hashes cannot establish authenticity. Back up old FCS data,
repackage the collection into an envelope, and either obtain a signed replacement
or deliberately enable development. Strict startup rejects an old/untrusted
active pack without deleting it. With FCS stopped, an operator may move old
`active.json` to the backup to start built-in-only and install a replacement.

Inspect installation `code`, `stage`, and `verification` results. Unknown or
revoked publishers need an operator-reviewed policy or replacement release,
not disabled verification. Hash/mode/path errors require a clean artifact.
`INCOMPATIBLE` requires a matching major/range/API/platform. `invalid_pack`
indicates semantic or inner-checksum failure. For `disk_full`, free staging
space/quota; for `permission_denied`, fix service-account access; for networking
or expired Actions artifacts, correct connectivity/token access or choose a
current asset. Failed updates preserve the active registry.

The host and same-user runtime remain trusted. This phase establishes release
provenance and snapshot integrity; it adds neither privilege separation nor
durable distributed deployment coordination. Real signing, publication, and
hosted platform checks require operator configuration after local review.
