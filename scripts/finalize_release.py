#!/usr/bin/env python3
"""Sign final staged payloads and verify the published archive with fcs-release."""
import argparse, json, os, subprocess, tarfile, tempfile
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--directory',type=Path,required=True)
p.add_argument('--verifier',type=Path,required=True)
p.add_argument('--signer',type=Path,required=True)
p.add_argument('--policy',type=Path,required=True)
p.add_argument('--key-id',required=True)
p.add_argument('--kind',choices=['fcs','fcs-pack','flexserv'],required=True)
p.add_argument('--fcs-validator',type=Path)
p.add_argument('--expected-archives',type=int,required=True)
a=p.parse_args()
private_key=os.environ.pop('RELEASE_SIGNING_PRIVATE_KEY', '')
if not private_key.strip() or not a.key_id.strip() or not a.policy.is_file() or not a.policy.read_text().strip():
    raise SystemExit('Configure the protected release environment: private signing key, key ID, and public signing policy are required')
repository='https://github.com/'+os.environ['GITHUB_REPOSITORY']
commit=os.environ['GITHUB_SHA'];tag=os.environ['GITHUB_REF_NAME']
if os.environ.get('GITHUB_REF_TYPE')!='tag' or not tag.startswith('v'):
    raise SystemExit('Official signing is restricted to version tags')
archives=sorted(a.directory.glob('*.tar.gz'))
if len(archives) != a.expected_archives or not archives:
    raise SystemExit(f'Incomplete release candidate set: expected {a.expected_archives}, found {len(archives)}')
for archive in archives:
    with tempfile.TemporaryDirectory(prefix='release-sign-') as temp:
        root=Path(temp)/'verified'
        sidecar=archive.with_name(archive.name+'.json')
        metadata=json.loads(sidecar.read_text()) if sidecar.exists() else {}
        target=metadata.get('target')
        context=['--target',target] if target else []
        if a.kind=='fcs-pack':
            if not a.fcs_validator: raise SystemExit('Pack signing requires a pinned FCS semantic validator')
            context += sum((['--feature',f] for f in ['hierarchical-tools','skills','rest','command']), [])
            context += ['--fcs-version',subprocess.check_output([str(a.fcs_validator),'--version'],text=True).strip().split()[-1]]
        subprocess.run([str(a.verifier),'verify','--artifact',str(archive),'--validation','dev-unsigned','--allow-dev-artifacts','--extract-to',str(root),*context],check=True)
        manifest=json.loads((root/'release.manifest.json').read_text())
        if (manifest['artifact_kind'],manifest['source']['repository'],manifest['source']['commit'],manifest['source']['tag'])!=(a.kind,repository,commit,tag) or tag!='v'+manifest['version']:
            raise SystemExit('Candidate identity does not match the checked-out release ref')
        if a.kind=='fcs-pack':
            if not a.fcs_validator: raise SystemExit('Pack signing requires a pinned FCS semantic validator')
            subprocess.run([str(a.fcs_validator),'pack','validate',str(root),'--validation','dev-unsigned','--allow-dev-artifacts','--json'],check=True)
        subprocess.run([str(a.signer),'--manifest',str(root/'release.manifest.json'),'--key-id',a.key_id,'--out',str(root/'release.signature.json')],check=True,env=dict(os.environ,RELEASE_SIGNING_PRIVATE_KEY=private_key))
        candidate=Path(temp)/archive.name
        with tarfile.open(candidate,'w:gz',format=tarfile.USTAR_FORMAT) as tar:
            for file in sorted(root.rglob('*')):
                tar.add(file,arcname=file.relative_to(root).as_posix(),recursive=False)
        subprocess.run([str(a.verifier),'verify','--artifact',str(candidate),'--policy',str(a.policy),*context],check=True)
        # These filenames include the archive name to avoid matrix asset collisions.
        for name in ['release.manifest.json','release.signature.json']:
            archive.with_name(archive.name+'.'+name).write_bytes((root/name).read_bytes())
        archive.write_bytes(candidate.read_bytes())
        import hashlib
        archive.with_name(archive.name+'.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
