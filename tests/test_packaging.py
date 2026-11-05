"""Exercise the public archive, complete checksum, and rejection contracts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_pack', ROOT / 'scripts/package_pack.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class Packaging(unittest.TestCase):
    def test_only_reviewed_native_envelopes_enable_process_groups(self):
        root = ROOT / 'pack/fcs_tools/io/flexserv/vllm'
        for alias in ('advanced/inspect', 'execute', 'deploy'):
            path = root / alias
            tool = yaml.safe_load((path / 'tool.yaml').read_text())
            envelope = tool['spec']['steps'][0]['input']
            self.assertEqual(envelope['input'], '{{params}}')
            if alias == 'deploy':
                self.assertNotIn('process_group_version', envelope)
            else:
                self.assertEqual(envelope['process_group_version'], 1)
            public = json.loads((path / 'schemas/input.json').read_text())
            self.assertNotIn('process_group_version', public['properties'])
            self.assertFalse(public['additionalProperties'])

    def test_portable_deterministic_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / 'a.zip', Path(directory) / 'b.zip'
            packager.package(ROOT / 'pack', a)
            packager.package(ROOT / 'pack', b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with zipfile.ZipFile(a) as archive:
                names = archive.namelist()
                self.assertIn('manifest.json', names)
                self.assertIn('checksums.sha256', names)
                manifest = json.loads(archive.read('manifest.json'))
                namespaces = {t['name'] for t in manifest['toolsets']}
                self.assertIn('io.flexserv.deployments', namespaces)
                self.assertIn('io.flexserv.models', namespaces)
                self.assertIn('io.tapis.workflows', namespaces)
                self.assertEqual(len(names) - 1, len(archive.read('checksums.sha256').splitlines()))

    def test_changed_asset_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'pack'
            root.mkdir()
            (root / 'manifest.json').write_text('{"schema_version":"flexserv.fcs-pack.v1alpha2"}')
            (root / 'checksums.sha256').write_text(packager.checksums(root))
            (root / 'script.sh').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'stale'):
                packager.package(root, Path(directory) / 'out.zip')

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'link').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'links'):
                packager.checksums(root)


if __name__ == '__main__':
    unittest.main()
