"""Verify release publication boundaries without changing GitHub resources."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40


class ComponentRelease(unittest.TestCase):
    """Exercise complete inventories, safe reruns and failure-before-publication."""

    def test_publication_boundaries(self):
        for case in ("new", "published", "bad_digest", "extra_asset", "wrong_commit"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "bin").mkdir()
                dist = root / "dist"
                dist.mkdir()
                (dist / "component-amd64.bin").write_bytes(b"amd64-fixture")
                (dist / "component-arm64.bin").write_bytes(b"arm64-fixture")
                inventory = "".join(
                    hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                    for p in sorted(dist.iterdir())
                )
                (dist / "release-assets.sha256").write_text(inventory)
                assets = [dict(name=p.name, size=p.stat().st_size,
                               digest="sha256:" + hashlib.sha256(p.read_bytes()).hexdigest())
                          for p in sorted(dist.iterdir())]
                if case == "bad_digest":
                    assets[0]["digest"] = "sha256:" + "0" * 64
                if case == "extra_asset":
                    assets.append(dict(name="unexpected.txt", size=0, digest="sha256:" + "0" * 64))
                release = dict(id=17, tag_name="fcs-fixture", draft=case != "published", assets=assets)
                for name, data in (("initial", [] if case == "new" else [release]),
                                   ("created", [release]), ("final", dict(release, draft=False))):
                    (root / (name + ".json")).write_text(json.dumps([data] if name != "final" else data))
                gh = root / "bin/gh"
                gh.write_text(r'''#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$FIXTURE/trace"
if [[ "$1" == release && "$2" == create ]]; then touch "$FIXTURE/created-marker"; exit; fi
if [[ "$1" == api && "$2" == --method ]]; then
  touch "$FIXTURE/published-marker"; cat "$FIXTURE/final.json"; exit
fi
case "$2" in
  */commits/*) printf '%s\n' "$FIXTURE_COMMIT" ;;
  *releases\?*)
    if [[ -e "$FIXTURE/created-marker" ]]; then cat "$FIXTURE/created.json"
    else cat "$FIXTURE/initial.json"; fi ;;
  *) exit 2 ;;
esac
''')
                gh.chmod(0o700)
                result = subprocess.run(
                    ["bash", str(ROOT / "scripts/publish_component_release.sh"), "fcs-fixture", str(dist)],
                    env=dict(os.environ, PATH=str(root / "bin") + ":" + os.environ["PATH"],
                             FIXTURE=str(root), FIXTURE_COMMIT="b" * 40 if case == "wrong_commit" else COMMIT,
                             GITHUB_SHA=COMMIT, GITHUB_REPOSITORY="fixture/FCS"),
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode == 0, case in ("new", "published"), result.stderr)
                self.assertEqual((root / "published-marker").exists(), case == "new")
                if case == "new":
                    self.assertIn("--verify-tag --draft", (root / "trace").read_text())
                    self.assertIn("PATCH repos/fixture/FCS/releases/17", (root / "trace").read_text())


if __name__ == "__main__":
    unittest.main()
