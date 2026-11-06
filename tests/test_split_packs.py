"""Check standalone Pack assets and their conflict-free combined catalog."""
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import zipfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('split', ROOT / 'scripts/split_packs.py')
split = importlib.util.module_from_spec(spec)
spec.loader.exec_module(split)


class SplitPacks(unittest.TestCase):
    def test_standalone_archives_cover_original_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = split.build(ROOT / 'pack', Path(directory), 'a' * 40)
            self.assertEqual({archive.name for archive in outputs}, {
                'tapis-workflow-pack.zip', 'vllm-pack.zip', 'hf-collective-pack.zip'})
            payloads = []
            toolsets = []
            tool_names = []
            for archive in outputs:
                with zipfile.ZipFile(archive) as packed:
                    data = {name: packed.read(name) for name in packed.namelist()}
                payloads.append(data)
                inventory = data['checksums.sha256'].decode().splitlines()
                self.assertEqual(len(inventory), len(data) - 1)
                for line in inventory:
                    digest, filename = line.split('  ', 1)
                    self.assertEqual(hashlib.sha256(data[filename]).hexdigest(), digest)
                manifest = json.loads(data['manifest.json'])
                self.assertEqual(manifest['name'], archive.stem)
                self.assertEqual(manifest['version'], '1.1.0')
                namespaces = {item['name'] for item in manifest['toolsets']}
                toolsets.append(namespaces)
                self.assertEqual('io.tapis.workflows' in namespaces, archive.stem == 'tapis-workflow-pack')
                self.assertEqual('io.flexserv.deployments' in namespaces, archive.stem == 'vllm-pack')
                self.assertEqual('io.flexserv.models' in namespaces, archive.stem == 'hf-collective-pack')
                self.assertNotIn('io.flexserv.content', namespaces)
                self.assertEqual('io.tapis.access.credentials' in namespaces, archive.stem == 'tapis-workflow-pack')
                self.assertEqual('fcs_tools/io/tapis/access/credentials/scan_to_secret/tool.yaml' in data,
                                 archive.stem == 'tapis-workflow-pack')
                names = []
                for path, content in data.items():
                    if path.endswith('/tool.yaml'):
                        match = re.search(r'^  name: ([a-z0-9_.-]+)$', content.decode(), re.M)
                        self.assertIsNotNone(match, path)
                        names.append(match.group(1))
                self.assertEqual(len(names), len(set(names)), archive.stem)
                tool_names.append(set(names))
            for index, first in enumerate(outputs):
                for other in range(index + 1, len(outputs)):
                    self.assertFalse(toolsets[index] & toolsets[other],
                                     f'{first.name} and {outputs[other].name} share toolsets')
                    self.assertFalse(tool_names[index] & tool_names[other],
                                     f'{first.name} and {outputs[other].name} share tools')
            scanner = payloads[0]['fcs_tools/io/tapis/access/credentials/scan_to_secret/tool.yaml'].decode()
            self.assertIn('name: io.tapis.access.credentials.scan_to_secret', scanner)
            self.assertEqual(yaml.safe_load(scanner)['spec']['steps'][0]['tool'],
                             {'name': 'content.scan_to_secret', 'version': '1.0.0'})
            capture = payloads[0]['fcs_tools/io/tapis/jobs/outputs/capture_once/tool.yaml'].decode()
            self.assertIn('name: io.tapis.access.credentials.scan_to_secret', capture)
            self.assertNotIn('io.flexserv.content.scan_to_secret', capture)
            hf = payloads[next(i for i, archive in enumerate(outputs) if archive.stem == 'hf-collective-pack')]
            download = hf['fcs_tools/io/flexserv/models/download/tool.yaml'].decode()
            self.assertIn('name: io.flexserv.models.download', download)
            self.assertIn('visibility: true', download)
            self.assertIn('mode: collective', download)
            self.assertIn('mode: background', download)
            for name in ('local.hf.runtime.inspect', 'local.model.resolve',
                         'local.hf.collective.preflight', 'local.hf.collective.transfer',
                         'local.hf.collective.finalize'):
                self.assertIn('name: ' + name, download)
            for role in ('cancel', 'result', 'status'):
                self.assertIn(f'fcs_tools/io/flexserv/models/{role}/tool.yaml', hf)
            for schema in ('input', 'output'):
                self.assertIn(f'fcs_tools/io/flexserv/models/download/schemas/{schema}.json', hf)
            merged = {}
            for data in payloads:
                for name, content in data.items():
                    if name in ('manifest.json', 'checksums.sha256'):
                        continue
                    self.assertEqual(merged.get(name, content), content)
                    merged[name] = content
            original = {p.relative_to(ROOT / 'pack').as_posix(): p.read_bytes()
                        for p in (ROOT / 'pack').rglob('*') if p.is_file()
                        and p.name not in ('manifest.json', 'checksums.sha256')}
            self.assertEqual(merged, original)
            source = json.loads((Path(directory) / 'pack-source.json').read_text())
            self.assertEqual(source['commit'], 'a' * 40)
            self.assertEqual(set(source['packs']), {archive.stem for archive in outputs})

    def test_stale_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'pack'
            root.mkdir()
            (root / 'manifest.json').write_text('{"schema_version":"flexserv.fcs-pack.v1alpha3"}')
            (root / 'checksums.sha256').write_text('')
            with self.assertRaisesRegex(ValueError, 'stale'):
                split.build(root, Path(directory) / 'out', 'a' * 40)
