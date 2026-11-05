"""Exercise recipe identity selection without a model download or an LLM."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recipe_catalog', ROOT / 'scripts/vllm_recipe_catalog.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class RecipeLookup(unittest.TestCase):
    def setUp(self):
        self.data = {'recipes': {
            'org/base': {'model_id': 'Org/Base', 'sha256': 'abc', 'recipe': {'variants': {
                'default': {}, 'quant': {'model_id': 'Vendor/Quant'}}}},
            'org/other': {'model_id': 'Org/Other', 'sha256': 'def', 'recipe': {'variants': {
                'default': {}}}},
        }}

    def test_exact_and_variant_preserve_target_identity(self):
        exact = catalog.resolve(self.data, 'HF:org/base')
        self.assertEqual(exact['target_model_id'], 'org/base')
        self.assertEqual(exact['match']['kind'], 'exact')
        variant = catalog.resolve(self.data, 'Vendor/Quant')
        self.assertEqual(variant['match']['kind'], 'variant')
        self.assertEqual(variant['match']['variant'], 'quant')
        self.assertEqual(variant['target_model_id'], 'Vendor/Quant')

    def test_preferred_never_changes_target_and_requires_review(self):
        result = catalog.resolve(self.data, 'User/Custom', 'Org/Base')
        self.assertEqual(result['target_model_id'], 'User/Custom')
        self.assertEqual(result['match']['recipe_model_id'], 'Org/Base')
        self.assertEqual(result['match']['kind'], 'preferred')
        self.assertTrue(result['requires_expert_review'])

    def test_missing_and_invalid_models(self):
        result = catalog.resolve(self.data, 'User/Custom', 'Org/Missing')
        self.assertEqual(result['error'], 'recipe_not_found')
        self.assertEqual(result['preferred_recipe_model_id'], 'Org/Missing')
        with self.assertRaises(ValueError):
            catalog.resolve(self.data, '../../etc/passwd')

    def test_ambiguous_variant_is_rejected(self):
        self.data['recipes']['org/other']['recipe']['variants']['quant'] = {'model_id': 'Vendor/Quant'}
        with self.assertRaisesRegex(ValueError, 'ambiguous variant'):
            catalog.resolve(self.data, 'Vendor/Quant')

    def test_default_model_id_can_differ_from_recipe_path(self):
        self.data['recipes']['org/base']['recipe']['model'] = {'model_id': 'Vendor/Default'}
        result = catalog.resolve(self.data, 'Vendor/Default')
        self.assertEqual(result['match']['recipe_model_id'], 'Org/Base')
        self.assertEqual(result['match']['variant'], 'default')

    def test_duplicate_yaml_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate YAML key'):
            yaml.load('model: one\nmodel: two\n', Loader=catalog.UniqueLoader)

    def test_recursive_yaml_alias_rejected(self):
        parsed = yaml.load('items: &loop [*loop]', Loader=catalog.UniqueLoader)
        with self.assertRaisesRegex(ValueError, 'nesting or expanded size'):
            catalog.json_value(parsed)


class CatalogBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.model_repo = self.root / 'model'
        self.renderer_repo = self.root / 'renderer'
        for repo in (self.model_repo, self.renderer_repo):
            repo.mkdir()
            self.git(repo, 'init', '-q')
            self.git(repo, 'config', 'user.name', 'Catalog Test')
            self.git(repo, 'config', 'user.email', 'catalog@example.test')
        recipe = self.model_repo / 'recipes/models/Org/Model.yaml'
        recipe.parent.mkdir(parents=True)
        recipe.write_text('model:\n  model_id: Org/Model\nvariants:\n  default:\n    precision: bf16\n')
        (self.renderer_repo / 'taxonomy.yaml').write_text('hardware_profiles: {}\n')
        (self.renderer_repo / 'strategies').mkdir()
        (self.renderer_repo / 'strategies/tp.yaml').write_text('name: single_node_tp\n')
        for repo in (self.model_repo, self.renderer_repo):
            self.git(repo, 'add', '.')
            self.git(repo, 'commit', '-qm', 'fixture')
        self.model_revision = self.git(self.model_repo, 'rev-parse', 'HEAD').strip()
        self.renderer_revision = self.git(self.renderer_repo, 'rev-parse', 'HEAD').strip()
        self.schema = self.root / 'schema.json'
        self.write_schema({'type': 'object', 'required': ['model', 'variants']})

    @staticmethod
    def git(repo, *args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True)

    def write_schema(self, schema):
        self.schema.write_text(json.dumps(schema))
        self.digest = hashlib.sha256(self.schema.read_bytes()).hexdigest()

    def build(self):
        return catalog.build_catalog(self.model_repo, self.model_revision, self.renderer_repo,
                                     self.renderer_revision, self.schema, self.digest)

    def test_build_uses_committed_objects_not_working_tree(self):
        (self.model_repo / 'recipes/models/Org/Model.yaml').write_text('invalid: changed\n')
        result = self.build()
        self.assertEqual(result['recipes']['org/model']['recipe']['model']['model_id'], 'Org/Model')
        self.assertEqual(result['sources']['renderer_revision'], self.renderer_revision)

    def test_external_schema_refs_and_nested_ids_rejected(self):
        for schema in ({'$ref': 'https://example.org/schema.json'},
                       {'properties': {'x': {'$id': 'https://example.org/'}}}):
            self.write_schema(schema)
            with self.assertRaisesRegex(ValueError, 'external|nested'):
                self.build()

    def test_wrong_schema_digest_rejected(self):
        self.digest = '0' * 64
        with self.assertRaisesRegex(ValueError, 'pinned SHA-256'):
            self.build()

    def test_committed_symlink_is_rejected(self):
        link = self.model_repo / 'recipes/models/Org/Link.yaml'
        link.symlink_to('Model.yaml')
        self.git(self.model_repo, 'add', '.')
        self.git(self.model_repo, 'commit', '-qm', 'add link')
        self.model_revision = self.git(self.model_repo, 'rev-parse', 'HEAD').strip()
        with self.assertRaisesRegex(ValueError, 'regular committed file'):
            self.build()


if __name__ == '__main__':
    unittest.main()
