import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from package_pack import package, checksums
from distribution import channel


class PackagingTests(unittest.TestCase):
    def test_production_catalog_survived_extraction(self):
        root = ROOT / 'pack'
        manifest = json.loads((root / 'manifest.json').read_text())
        self.assertRegex(manifest['version'], r'^\d+\.\d+\.\d+$')
        self.assertEqual(len(manifest['toolsets']), 10)
        tools = {'.'.join(p.parent.relative_to(root / 'fcs_tools').parts) for p in root.rglob('tool.yaml')}
        expected = set((ROOT / 'tests/catalog-tools.txt').read_text().splitlines())
        self.assertEqual(tools, expected)
        skills = [p for p in root.rglob('*') if p.is_file() and ('skills' in p.parts or '.skills' in p.parts)]
        self.assertEqual(len(skills), 13)

    def test_reproducible_archives_leave_source_unchanged(self):
        before = checksums(ROOT / 'pack')
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / 'a.tar.gz', Path(temporary) / 'b.tar.gz'
            package(ROOT / 'pack', first)
            package(ROOT / 'pack', second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first) as tar:
                data = {p.name.removeprefix('payload/'): tar.extractfile(p).read() for p in tar if p.isfile() and p.name.startswith('payload/')}
            for line in data['checksums.sha256'].decode().splitlines():
                expected, path = line.split('  ', 1)
                self.assertEqual(hashlib.sha256(data[path]).hexdigest(), expected)
        self.assertEqual(checksums(ROOT / 'pack'), before)

    def test_branch_channels_are_safe_and_distinct(self):
        self.assertEqual(channel('main'), 'main')
        self.assertNotEqual(channel('feature/a'), channel('feature-a'))
        self.assertRegex(channel('feature/Some.Change'), r'^[a-z0-9-]+$')


if __name__ == '__main__':
    unittest.main()
