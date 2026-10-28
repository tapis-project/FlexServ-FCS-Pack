#!/usr/bin/env python3
"""Derive two portable release Packs from the single reviewed source catalog."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from package_pack import checksums, package


def build(source, output, commit):
    """Preserve tool identity and shared helpers while rebuilding each inventory."""
    source, output = Path(source), Path(output)
    if (source / 'checksums.sha256').read_text() != checksums(source):
        raise ValueError('Source inventory is stale; refresh it explicitly')
    manifest = json.loads((source / 'manifest.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    archives, versions = [], {}
    for name in ('tapis-workflow-pack', 'vllm-pack'):
        if name == 'tapis-workflow-pack':
            toolsets = [item for item in manifest['toolsets'] if
                        item['name'].startswith(('io.tapis.', 'io.flexserv.ssh.'))
                        or item['name'] == 'io.flexserv.paths']
        else:
            toolsets = [item for item in manifest['toolsets'] if item['name'] ==
                        'io.flexserv.deployments']
        with tempfile.TemporaryDirectory(prefix='split-pack-') as temporary:
            root = Path(temporary)
            for item in toolsets:
                relative = Path(item['path'])
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('Invalid source toolset path')
                shutil.copytree(source / relative, root / relative, dirs_exist_ok=True)
            (root / 'manifest.json').write_text(json.dumps(
                dict(manifest, name=name, toolsets=toolsets), indent=2) + '\n')
            (root / 'checksums.sha256').write_text(checksums(root))
            archives.append(package(root, output / (name + '.zip')))
            versions[name] = manifest['version']
    (output / 'pack-source.json').write_text(json.dumps(dict(
        repository='tapis-project/FlexServ-FCS-Pack', commit=commit,
        schema_version=1, packs=versions), indent=2) + '\n')
    return archives


def main():
    """Package without modifying canonical definitions or refreshing source checksums."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('pack'))
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    build(args.source, args.output, commit)
    inventory = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                        for p in sorted(args.output.iterdir()) if p.is_file()
                        and p.name != 'release-assets.sha256')
    (args.output / 'release-assets.sha256').write_text(inventory)


if __name__ == '__main__':
    main()
