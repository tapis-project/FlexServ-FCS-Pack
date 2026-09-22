#!/usr/bin/env python3
"""Install immutable CI tools using operator-reviewed archive SHA-256 pins."""
import argparse,hashlib,json,os,tarfile,tempfile
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--lock',type=Path,default=Path('ci-tools.lock.json'))
p.add_argument('--platform',required=True)
p.add_argument('--directory',type=Path,default=Path('.ci-tools'))
p.add_argument('--tools',nargs='+',default=['fcs-release'])
a=p.parse_args();lock=json.loads(a.lock.read_text())
if lock.get('schema_version')!=1: raise SystemExit('Unsupported CI tools lock')
configured=lock.get('platforms',{}).get(a.platform,{})
a.directory.mkdir(parents=True,exist_ok=True)
for name in a.tools:
    entry=configured.get(name)
    if not entry: raise SystemExit(f'Configure an independently reviewed {a.platform}/{name} pin in {a.lock}; no moving-branch bootstrap is allowed')
    url=urlparse(entry['url'])
    if url.scheme!='https' or url.username or url.password: raise SystemExit('Tool URLs must use HTTPS without credentials')
    expected=entry['sha256']
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected): raise SystemExit('Invalid tool archive digest')
    with tempfile.TemporaryDirectory(prefix='pinned-tool-') as temp:
        archive=Path(temp)/'download';digest=hashlib.sha256();count=0
        with urlopen(entry['url'],timeout=60) as response,archive.open('wb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                count+=len(chunk)
                if count>1024**3: raise SystemExit('CI tool archive exceeds 1 GiB')
                digest.update(chunk);output.write(chunk)
        if digest.hexdigest()!=expected: raise SystemExit('Pinned CI tool checksum mismatch')
        with tarfile.open(archive,'r:gz') as tar:
            matches=[m for m in tar if m.name==entry['member']]
            if len(matches)!=1 or not matches[0].isfile() or matches[0].size>512*1024**2: raise SystemExit('Invalid pinned tool archive member')
            destination=a.directory/name
            with tar.extractfile(matches[0]) as source,destination.open('wb') as output:
                import shutil
                shutil.copyfileobj(source,output)
            destination.chmod(0o755)
    if os.environ.get('GITHUB_ENV'):
        with open(os.environ['GITHUB_ENV'],'a') as output:
            output.write(name.upper().replace('-','_')+'_BIN='+str((a.directory/name).resolve())+'\n')
