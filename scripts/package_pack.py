#!/usr/bin/env python3
"""Package a checksummed pack without modifying its source directory (stdlib only)."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import os
import subprocess


def checksums(root):
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Pack links are forbidden: {path}')
        if path.is_file() and path.name != '.DS_Store' and path != root / 'checksums.sha256':
            files.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n')
        elif not path.is_file() and not path.is_dir():
            raise ValueError(f'Non-regular pack entry: {path}')
    return ''.join(files)


def package(source, output, verifier=None, descriptor=None):
    source = source.resolve()
    output = output.resolve()
    if source == output or source in output.parents:
        raise ValueError('Output archive must be outside the source pack')
    manifest = json.loads((source / 'manifest.json').read_text())
    if not (source / 'fcs_tools').is_dir():
        raise ValueError('Missing fcs_tools/')
    checksums(source)
    with tempfile.TemporaryDirectory(prefix='fcs-pack-') as temporary:
        root = Path(temporary) / 'release'
        payload = root / 'payload'
        shutil.copytree(source, payload, ignore=shutil.ignore_patterns('.DS_Store'))
        (payload / 'checksums.sha256').write_text(checksums(payload))
        for path in payload.rglob('*'):
            path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
        release = json.loads((descriptor or Path(__file__).resolve().parents[1] / 'release-descriptor.json').read_text())
        if release['version'] != manifest['version']:
            raise ValueError('Release descriptor version must match pack manifest')
        release['source']['commit'] = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        release['released_at'] = subprocess.check_output(['git','-C',str(source),'show','-s','--format=%cI','HEAD'],text=True).strip()
        if os.environ.get('GITHUB_REPOSITORY'):
            release['source']['repository'] = 'https://github.com/' + os.environ['GITHUB_REPOSITORY']
        release['source']['tag'] = os.environ.get('GITHUB_REF_NAME') if os.environ.get('GITHUB_REF_TYPE') == 'tag' else None
        config = Path(temporary) / 'descriptor.json'
        config.write_text(json.dumps(release))
        subprocess.run([str(verifier or os.environ.get('FCS_RELEASE_BIN','fcs-release')), 'manifest', '--payload',str(payload),'--descriptor',str(config),'--out',str(root/'release.manifest.json')],check=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                for path in sorted(root.rglob('*')):
                    info = archive.gettarinfo(str(path), arcname=str(path.relative_to(root)))
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ''
                    info.mode = 0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644
                    if path.is_file():
                        with path.open('rb') as content:
                            archive.addfile(info, content)
                    else:
                        archive.addfile(info)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path, nargs='?')
    parser.add_argument('--refresh-checksums', action='store_true', help='Explicitly refresh the source checksum manifest')
    parser.add_argument('--verifier', type=Path)
    parser.add_argument('--descriptor', type=Path)
    args = parser.parse_args()
    if args.refresh_checksums:
        (args.source / 'checksums.sha256').write_text(checksums(args.source))
    elif args.output:
        package(args.source, args.output, args.verifier, args.descriptor)
        print(args.output)
    else:
        parser.error('output is required unless --refresh-checksums is given')


if __name__ == '__main__':
    main()
