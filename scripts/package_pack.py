#!/usr/bin/env python3
"""Build the v0.13 Pack ZIP with a complete, deterministic file inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def checksums(root):
    """Inventory all regular payload files; links and device files are forbidden."""
    entries = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Pack links are forbidden: {path}')
        if path.is_file() and path != root / 'checksums.sha256':
            entries.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n')
        elif not path.is_file() and not path.is_dir():
            raise ValueError(f'Non-regular Pack entry: {path}')
    return ''.join(entries)


def package(source, output):
    """Write one portable ZIP without modifying the checked-in payload."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents:
        raise ValueError('Output archive must be outside the Pack')
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['schema_version'] != 'flexserv.fcs-pack.v1alpha2':
        raise ValueError('Only v0.13 v1alpha2 Packs are supported')
    inventory = checksums(source)
    if (source / 'checksums.sha256').read_text() != inventory:
        raise ValueError('Source inventory is stale; refresh it explicitly')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                entry = zipfile.ZipInfo(path.relative_to(source).as_posix(), (1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (0o100644 << 16)
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, path.read_bytes())
    output.with_name(output.name + '.sha256').write_text(
        f'{hashlib.sha256(output.read_bytes()).hexdigest()}  {output.name}\n')
    return output


def main():
    """Refresh source checksums explicitly or package an already reviewed inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', nargs='?', type=Path)
    parser.add_argument('--refresh-checksums', action='store_true')
    args = parser.parse_args()
    if args.refresh_checksums:
        (args.source / 'checksums.sha256').write_text(checksums(args.source))
    elif args.output:
        print(package(args.source, args.output))
    else:
        parser.error('output is required unless --refresh-checksums is given')


if __name__ == '__main__':
    main()
