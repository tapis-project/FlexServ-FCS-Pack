#!/usr/bin/env python3
"""Build metadata, portable archives, and branch/version GitHub releases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import quote


def channel(branch):
    if branch == 'main':
        return 'main'
    slug = re.sub(r'[^a-z0-9-]+', '-', branch.lower()).strip('-')[:40] or 'branch'
    return f'{slug}-{hashlib.sha256(branch.encode()).hexdigest()[:10]}'


def metadata(manifest):
    if manifest.suffix == '.json':
        version = json.loads(manifest.read_text())['version']
    else:
        version = re.search(r'^version\s*=\s*"([^"]+)"', manifest.read_text(), re.M)[1]
    ref = os.environ.get('GITHUB_REF_NAME', subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip())
    kind = os.environ.get('GITHUB_REF_TYPE', 'branch')
    if kind == 'tag' and ref != 'v' + version:
        raise ValueError(f'Release tag {ref} does not match manifest version {version}')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?', version):
        raise ValueError('Expected a semantic product version')
    data = dict(version=version, branch=ref, channel=ref if kind == 'tag' else channel(ref),
                source_sha=os.environ.get('GITHUB_SHA') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                run_id=os.environ.get('GITHUB_RUN_ID', 'local'), ref_type=kind,
                repository=os.environ.get('GITHUB_REPOSITORY', 'local/'+Path.cwd().name),
                distribution_class='release_candidate' if kind == 'tag' else 'development_untrusted')
    return data


def digest(path):
    with path.open('rb') as content:
        result = hashlib.sha256()
        for chunk in iter(lambda: content.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def sidecars(archive, data):
    archive.with_name(archive.name + '.sha256').write_text(f'{digest(archive)}  {archive.name}\n')
    archive.with_name(archive.name + '.json').write_text(json.dumps(data, indent=2) + '\n')


def binary_archive(binary, directory, data, platform, arch, target):
    directory.mkdir(parents=True, exist_ok=True)
    data = dict(data, platform=platform, arch=arch, target=target)
    archive = directory / f'flexserv-fcs-{data["channel"]}-{platform}-{arch}.tar.gz'
    with tempfile.TemporaryDirectory(prefix='fcs-binary-') as temp:
        root = Path(temp)
        shutil.copy2(binary, root / 'flexserv-fcs')
        (root / 'flexserv-fcs').chmod(0o755)
        (root / 'BUILD.json').write_text(json.dumps(data, indent=2) + '\n')
        (root / 'checksums.sha256').write_text(''.join(f'{digest(root / name)}  {name}\n' for name in ['flexserv-fcs', 'BUILD.json']))
        with tarfile.open(archive, 'w:gz') as tar:
            for path in sorted(root.iterdir()):
                tar.add(path, arcname=path.name)
    sidecars(archive, data)
    return archive


def gh(*arguments, allow_missing=False):
    result = subprocess.run(['gh', *arguments], text=True, capture_output=True)
    if result.returncode:
        if allow_missing and '404' in result.stderr:
            return None
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else None


def publish(directory, data):
    repo = os.environ['GITHUB_REPOSITORY']
    tag, sha = data['channel'], data['source_sha']
    rolling = data['ref_type'] == 'branch'
    if rolling:
        head = gh('api', f'repos/{repo}/git/ref/heads/{quote(data["branch"], safe="")}')['object']['sha']
        if head != sha:
            print('A newer branch commit exists; retaining its distribution channel.')
            return
    release = gh('api', f'repos/{repo}/releases/tags/{quote(tag, safe="")}', allow_missing=True)
    if rolling and release:
        prior = re.search(r'fcs-build-run:(\d+)', release.get('body') or '')
        if prior and int(prior[1]) > int(data['run_id']):
            print('A newer workflow run already published this channel.')
            return
    assets = sorted(directory.glob('*'))
    if not assets or not any(p.name.endswith('.tar.gz') for p in assets):
        raise ValueError('No distribution archives found')
    if not rolling and release and not release.get('draft'):
        expected = {p.name for p in assets}
        present = {a['name'] for a in release['assets']}
        if expected <= present:
            print('Version release is already published; its assets remain immutable.')
            return
        raise ValueError('Version release has partial assets; repair it explicitly before retrying')
    label = 'UNSIGNED DEVELOPMENT ARTIFACTS — explicit development opt-in required' if rolling else 'Signed release — verify publisher policy and manifest before use'
    notes = label + '\n\n' + f'Version {data["version"]}\nSource commit: {sha}\nBranch/ref: {data["branch"]}\n<!-- fcs-build-run:{data["run_id"]} -->'
    if not release:
        args = ['release', 'create', tag, '--repo', repo, '--target', sha, '--title', tag, '--notes', notes]
        if not rolling:
            args += ['--draft']
        if rolling or '-' in data['version']:
            args += ['--prerelease', '--latest=false']
        subprocess.run(['gh', *args], check=True)
    elif rolling:
        gh('api', f'repos/{repo}/git/refs/tags/{quote(tag, safe="")}', '--method', 'PATCH', '-f', f'sha={sha}', '-F', 'force=true')
        subprocess.run(['gh', 'release', 'edit', tag, '--repo', repo, '--notes', notes, '--prerelease', '--latest=false'], check=True)
    args = ['gh', 'release', 'upload', tag, '--repo', repo, *map(str, assets)]
    if rolling or (release and release.get('draft')):
        args.append('--clobber')
    subprocess.run(args, check=True)
    if not rolling:
        published = gh('api', f'repos/{repo}/releases/tags/{quote(tag, safe="")}')
        present = {a['name']:a for a in published['assets']}
        if set(present) != {p.name for p in assets} or any(
            present.get(p.name, {}).get('size') != p.stat().st_size or
            (present[p.name].get('digest') and present[p.name]['digest'] != 'sha256:' + digest(p))
            for p in assets):
            raise ValueError('Draft release asset set is incomplete; leaving it unpublished')
        subprocess.run(['gh','release','edit',tag,'--repo',repo,'--draft=false'],check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    meta = commands.add_parser('metadata')
    meta.add_argument('--manifest', type=Path, required=True)
    meta.add_argument('--output', type=Path, required=True)
    binary = commands.add_parser('binary')
    binary.add_argument('--binary', type=Path, required=True)
    binary.add_argument('--directory', type=Path, required=True)
    binary.add_argument('--metadata', type=Path, required=True)
    binary.add_argument('--platform', required=True)
    binary.add_argument('--arch', required=True)
    binary.add_argument('--target', required=True)
    release = commands.add_parser('publish')
    release.add_argument('--directory', type=Path, required=True)
    release.add_argument('--metadata', type=Path, required=True)
    checksum = commands.add_parser('sidecars')
    checksum.add_argument('--archive', type=Path, required=True)
    checksum.add_argument('--metadata', type=Path, required=True)
    branch = commands.add_parser('channel')
    branch.add_argument('branch')
    args = parser.parse_args()
    if args.command == 'metadata':
        data = metadata(args.manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2) + '\n')
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write(f'channel={data["channel"]}\nversion={data["version"]}\nsha={data["source_sha"]}\n')
        print(json.dumps(data))
    elif args.command == 'binary':
        print(binary_archive(args.binary, args.directory, json.loads(args.metadata.read_text()), args.platform, args.arch, args.target))
    elif args.command == 'publish':
        publish(args.directory, json.loads(args.metadata.read_text()))
    elif args.command == 'sidecars':
        sidecars(args.archive, json.loads(args.metadata.read_text()))
    else:
        print(channel(args.branch))


if __name__ == '__main__':
    main()
