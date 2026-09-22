#!/usr/bin/env python3
"""Check signed, pinned release combinations, including the supported minimum."""
import argparse,json,os,subprocess,tempfile,hashlib,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--platform',required=True)
p.add_argument('--lock',type=Path,default=Path('compatibility-releases.lock.json'))
p.add_argument('--policy',type=Path,required=True)
a=p.parse_args();lock=json.loads(a.lock.read_text())
releases=[r for r in lock.get('releases',[]) if r['platform']==a.platform]
if not releases or lock['minimum_fcs_version'] not in [r['fcs_version'] for r in releases]:
    raise SystemExit('Configure pinned release combinations including minimum_fcs_version for this platform')
with tempfile.TemporaryDirectory(prefix='released-compat-') as temp:
 for index,release in enumerate(releases):
    directory=Path(temp)/str(index);directory.mkdir()
    for kind in ['fcs','pack']:
        asset=release[kind];url=asset['url']
        if not url.startswith('https://'):raise SystemExit('Pinned URLs must use HTTPS')
        archive=directory/(kind+'.tar.gz');size=0;digest=hashlib.sha256()
        with urllib.request.urlopen(url,timeout=60) as response,archive.open('wb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>1024**3:raise SystemExit('Archive limit exceeded')
                output.write(chunk);digest.update(chunk)
        if digest.hexdigest()!=asset['archive_sha256']:raise SystemExit('Pinned archive checksum mismatch')
        features=[]
        if kind=='pack':
            verified_fcs=json.loads((directory/'fcs/release.manifest.json').read_text())
            for feature in verified_fcs['compatibility']['features']: features += ['--feature',feature]
        subprocess.run([os.environ['FCS_RELEASE_BIN'],'verify','--artifact',str(archive),'--policy',str(a.policy),'--fcs-version',release['fcs_version'],'--expected-digest',asset['manifest_sha256'],'--extract-to',str(directory/kind),*features],check=True)
        verified_manifest=json.loads((directory/kind/'release.manifest.json').read_text())
        if verified_manifest['artifact_kind'] != ('fcs' if kind=='fcs' else 'fcs-pack'):
            raise SystemExit('Pinned release has the wrong artifact role')
    binary=directory/'fcs/payload/flexserv-fcs'
    version=subprocess.check_output([str(binary),'--version'],text=True).strip().split()[-1]
    if version!=release['fcs_version']:raise SystemExit('FCS version does not match compatibility pin')
    subprocess.run([str(binary),'pack','validate',str(directory/'pack'),'--trust-policy',str(a.policy),'--expected-pack-digest',release['pack']['manifest_sha256'],'--json'],check=True)
    print(json.dumps({'platform':a.platform,'fcs_version':version,'fcs_manifest':release['fcs']['manifest_sha256'],'pack_manifest':release['pack']['manifest_sha256'],'strict':True}))
