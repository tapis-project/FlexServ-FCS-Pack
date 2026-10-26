"""Check independent Pack assets and their shared, conflict-free runtime catalog."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('split', ROOT / 'scripts/split_packs.py')
split = importlib.util.module_from_spec(spec)
spec.loader.exec_module(split)


class SplitPacks(unittest.TestCase):
    def test_standalone_archives_cover_original_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = split.build(ROOT / 'pack', Path(directory), 'a' * 40)
            payloads = []
            for archive in outputs:
                with zipfile.ZipFile(archive) as packed:
                    data = {name: packed.read(name) for name in packed.namelist()}
                payloads.append(data)
                inventory = data['checksums.sha256'].decode().splitlines()
                self.assertEqual(len(inventory), len(data) - 1)
                manifest = json.loads(data['manifest.json'])
                self.assertEqual(manifest['name'], archive.stem)
                namespaces = {item['name'] for item in manifest['toolsets']}
                self.assertEqual('io.tapis.workflows' in namespaces, archive.stem == 'tapis-workflow-pack')
                self.assertEqual('io.flexserv.deployments' in namespaces, archive.stem == 'vllm-pack')
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

    def test_stale_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'pack'
            root.mkdir()
            (root / 'manifest.json').write_text('{"schema_version":"flexserv.fcs-pack.v1alpha2"}')
            (root / 'checksums.sha256').write_text('')
            with self.assertRaisesRegex(ValueError, 'stale'):
                split.build(root, Path(directory) / 'out', 'a' * 40)
