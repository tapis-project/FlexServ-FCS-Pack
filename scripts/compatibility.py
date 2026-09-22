#!/usr/bin/env python3
"""Resolve an FCS build and test URL installation, discovery, and restart recovery."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tarfile
import tempfile
import time
from urllib.request import Request, urlopen

from distribution import channel, digest, gh


def resolve(repository, branch):
    pages = subprocess.check_output(['gh', 'api', '--paginate', '--slurp', '--method', 'GET',
        f'repos/{repository}/actions/workflows/build.yml/runs', '-f', f'branch={branch}',
        '-f', 'status=success', '-f', 'per_page=100'], text=True)
    runs = [run for page in json.loads(pages) for run in page['workflow_runs']
            if run['head_branch'] == branch and run['event'] in ('push', 'workflow_dispatch')]
    if not runs:
        raise RuntimeError(f'No successful FCS build exists for {repository}:{branch}')
    run = runs[0]
    data = dict(repository=repository, branch=branch, channel=channel(branch), run_id=str(run['id']), source_sha=run['head_sha'])
    for key, value in data.items():
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write(f'{key}={value}\n')
    print(json.dumps(data, indent=2))
    return data


def download_build(repository, run_id, branch, sha, platform, arch, directory):
    directory.mkdir(parents=True, exist_ok=True)
    name = f'flexserv-fcs-{channel(branch)}-{platform}-{arch}'
    # gh exits nonzero for missing/expired artifacts. Never fall back to another run.
    subprocess.run(['gh', 'run', 'download', run_id, '--repo', repository, '--name', name, '--dir', str(directory)], check=True)
    archive = directory / (name + '.tar.gz')
    metadata = json.loads(archive.with_name(archive.name + '.json').read_text())
    if (metadata['source_sha'], str(metadata['run_id']), metadata['platform'], metadata['arch']) != (sha, run_id, platform, arch):
        raise RuntimeError('Downloaded FCS build metadata does not match the selected run/platform')
    expected = archive.with_name(archive.name + '.sha256').read_text().split()[0]
    if digest(archive) != expected:
        raise RuntimeError('FCS binary archive checksum mismatch')
    verified = directory / 'verified'
    subprocess.run([os.environ['FCS_RELEASE_BIN'],'verify','--artifact',str(archive),'--validation','dev-unsigned','--allow-dev-artifacts','--extract-to',str(verified)],check=True)
    manifest=json.loads((verified/'release.manifest.json').read_text())
    if manifest['artifact_kind']!='fcs' or manifest['source']['commit']!=sha:
        raise RuntimeError('Verified FCS release identity differs from selected build')
    import shutil
    shutil.copy2(verified/'payload/flexserv-fcs',directory/'flexserv-fcs')
    (directory / 'flexserv-fcs').chmod(0o755)


def smoke(binary, archive, artifact_url, log_path):
    binary = binary.resolve()
    validated = json.loads(subprocess.check_output([str(binary), 'pack', 'validate', str(archive), '--validation','dev-unsigned','--allow-dev-artifacts','--json'], text=True))
    expected_tools = {tool['name'] for tool in validated['tools'] if not tool['name'].startswith('flexserv.builtin.')}
    expected_skills = {(s['owner_path'], s['skill_path']) for s in validated['skills']}
    scopes = set()
    for declaration in validated['declarations']:
        scopes.update(declaration.get('_meta', {}).get('flexserv.dev/tool-contract', {}).get('required_scopes', []))
    for skill in validated['skills']:
        scopes.update(skill.get('required_scopes', []))
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    service_secret, admin_secret = secrets.token_hex(32), secrets.token_hex(32)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fcs-compat-') as temporary, log_path.open('w') as logs:
        env = dict(os.environ, FLEXSERV_FCS_HOST='127.0.0.1', FLEXSERV_FCS_PORT=str(port),
            FLEXSERV_FCS_BASE_URL=base, FLEXSERV_FCS_URL=base, FLEXSERV_FCS_DATA_DIR=temporary,
            FLEXSERV_FCS_TOOL_DIR='', FLEXSERV_GATEWAY_URL='',
            FLEXSERV_SERVICE_SECRET=service_secret, FLEXSERV_ADMIN_SECRET=admin_secret,
            FLEXSERV_FCS_MCP_SERVICE_PRINCIPALS=json.dumps({'gateway': sorted(scopes)}),
            FLEXSERV_FCS_MCP_ALLOW_UNAUTHENTICATED='false')

        def request(path, body=None, signed=False, headers=None):
            data = None if body is None else json.dumps(body, separators=(',', ':')).encode()
            method = 'GET' if body is None else 'POST'
            auth = {'Content-Type': 'application/json'}
            if signed:
                timestamp, nonce = str(int(time.time() * 1000)), secrets.token_hex(16)
                body_hash = hashlib.sha256(data or b'').hexdigest()
                canonical = '\n'.join(['gateway', method, path, timestamp, nonce, body_hash])
                auth.update({'x-flexserv-agent-id': 'gateway', 'x-flexserv-timestamp': timestamp,
                    'x-flexserv-nonce': nonce, 'x-flexserv-body-sha256': body_hash,
                    'x-flexserv-signature': hmac.new(service_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()})
            else:
                auth['X-Flexserv-Admin-Secret'] = admin_secret
            auth.update(headers or {})
            with urlopen(Request(base + path, data=data, headers=auth, method=method), timeout=15) as response:
                return json.loads(response.read()), response.headers

        def start():
            process = subprocess.Popen([str(binary), 'serve','--allow-dev-artifacts'], env=env, stdout=logs, stderr=subprocess.STDOUT)
            for _ in range(150):
                if process.poll() is not None:
                    raise RuntimeError(f'FCS exited during startup; inspect {log_path}')
                try:
                    request('/healthz')
                    return process
                except OSError:
                    time.sleep(0.2)
            process.terminate()
            process.wait(timeout=15)
            raise RuntimeError('FCS health check timed out')

        def verify():
            current = request('/fcs/v1/packs/current')[0]['pack']
            assert current['version'] == validated['manifest']['version']
            assert current['source_url'] == artifact_url
            tools = request('/fcs/v1/tools', signed=True)[0]['tools']
            actual_tools = {t['name'] for t in tools if not t['name'].startswith('flexserv.builtin.')}
            assert actual_tools == expected_tools, (actual_tools, expected_tools)
            skills = request('/fcs/v1/skills', signed=True)[0]['skills']
            assert {(s['owner_path'], s['skill_path']) for s in skills} == expected_skills
            body = {'jsonrpc':'2.0','id':1,'method':'initialize','params':{
                'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'compatibility','version':'0.1.0'},
                '_meta':{'flexserv/requestedScopes': sorted(scopes)}}}
            result, headers = request('/fcs/v1/mcp', body, True, {'Accept':'application/json, text/event-stream'})
            assert 'result' in result, result
            session = {'Accept':'application/json, text/event-stream','MCP-Session-Id':headers['MCP-Session-Id'],
                       'MCP-Protocol-Version':'2025-11-25'}
            def pages(method, field):
                items, cursor = [], None
                while True:
                    result = request('/fcs/v1/mcp', {'jsonrpc':'2.0','id':2,'method':method,'params':{'cursor':cursor} if cursor else {}}, True, session)[0]
                    assert 'result' in result, result
                    items.extend(result['result'][field])
                    cursor = result['result'].get('nextCursor')
                    if not cursor:
                        return items
            assert {t['name'] for t in pages('tools/list', 'tools') if not t['name'].startswith('flexserv.builtin.')} == expected_tools
            assert len(pages('resources/list', 'resources')) == len(expected_skills)
            return current['installation_id']

        process = start()
        try:
            installed = json.loads(subprocess.check_output([str(binary), 'pack', 'install', artifact_url, '--validation','dev-unsigned','--json'], env=env, text=True, timeout=900))
            assert installed['status'] == 'succeeded', installed
            installed_id = verify()
            process.terminate()
            process.wait(timeout=15)
            process = start()
            assert verify() == installed_id, 'Restart changed the active installation'
            print(json.dumps({'healthy':True,'version':validated['manifest']['version'],
                'pack_tools':len(expected_tools),'skills':len(expected_skills),'restart_verified':True}))
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    select = commands.add_parser('resolve')
    select.add_argument('--repository', required=True)
    select.add_argument('--branch', required=True)
    fetch = commands.add_parser('download')
    for name in ['repository','run-id','branch','sha','platform','arch']:
        fetch.add_argument('--' + name, required=True)
    fetch.add_argument('--directory', required=True, type=Path)
    test = commands.add_parser('smoke')
    test.add_argument('--binary', required=True, type=Path)
    test.add_argument('--archive', required=True, type=Path)
    test.add_argument('--artifact-url', required=True)
    test.add_argument('--log', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'resolve':
        resolve(args.repository, args.branch)
    elif args.command == 'download':
        download_build(args.repository, args.run_id, args.branch, args.sha, args.platform, args.arch, args.directory)
    else:
        smoke(args.binary, args.archive, args.artifact_url, args.log)


if __name__ == '__main__':
    main()
