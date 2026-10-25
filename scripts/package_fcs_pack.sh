#!/usr/bin/env bash
# Package the single v0.13 catalog using only Python's standard library.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python3 "$repo/scripts/package_pack.py" "$repo/pack" "${1:-$repo/dist/flexserv-capability-pack.zip}"
