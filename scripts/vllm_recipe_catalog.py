#!/usr/bin/env python3
"""Build a pinned offline vLLM recipe catalog and resolve model recipe identities.

The schema must be generated from the matching pinned recipes renderer and its
source lock. Catalog generation does not execute recipes or installation commands.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

import jsonschema
import yaml

MODEL_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$')
REVISION = re.compile(r'^[0-9a-f]{40}$')
MAX_SOURCE_BYTES = 1024 * 1024
MAX_FILES = 10000
MAX_CATALOG_BYTES = 128 * 1024 * 1024


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys rather than silently changing recipe meaning."""


def construct_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def checked_revision(repo, revision):
    if not REVISION.fullmatch(revision):
        raise ValueError('source revisions must be full 40-character lowercase commit hashes')
    resolved = git(repo, 'rev-parse', '--verify', f'{revision}^{{commit}}').decode().strip()
    if resolved != revision:
        raise ValueError('revision did not resolve to the supplied commit')
    return resolved


def json_value(value, depth=0, budget=None):
    if budget is None:
        budget = [100000]
    budget[0] -= 1
    if budget[0] < 0 or depth > 64:
        raise ValueError('YAML nesting or expanded size exceeds limit')
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [json_value(item, depth + 1, budget) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError('recipe mappings must have string keys')
        return {key: json_value(item, depth + 1, budget) for key, item in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('non-finite number in YAML')
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError('unsupported YAML value')


def canonical_id(value):
    if not isinstance(value, str):
        raise ValueError('model identifier must be a string')
    if value.startswith('HF:'):
        value = value[3:]
    if len(value) > 512 or not MODEL_ID.fullmatch(value):
        raise ValueError(f'invalid Hugging Face model identifier: {value!r}')
    return value


def source_files(repo, revision, *paths):
    """Enumerate regular committed blobs with bounded sizes, including their Git IDs."""
    output = git(repo, 'ls-tree', '-r', '-l', '-z', revision, '--', *paths)
    entries = output.split(b'\0')
    if len(entries) - 1 > MAX_FILES:
        raise ValueError('too many catalog source files')
    files = {}
    total_size = 0
    for entry in entries:
        if not entry:
            continue
        metadata, path = entry.split(b'\t', 1)
        mode, kind, object_id, size = metadata.split()
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise ValueError('catalog source must be a regular committed file')
        blob_size = int(size)
        if blob_size > MAX_SOURCE_BYTES:
            raise ValueError('catalog source file exceeds size limit')
        total_size += blob_size
        if total_size > MAX_CATALOG_BYTES:
            raise ValueError('catalog source files exceed total size limit')
        files[path.decode('utf-8')] = object_id.decode('ascii')
    return files


def source_blob(repo, object_id):
    """Read the exact object enumerated from the pinned Git tree."""
    raw = git(repo, 'cat-file', 'blob', object_id)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError('catalog source file exceeds size limit')
    return raw


def build_catalog(model_repo, model_revision, renderer_repo, renderer_revision, schema_path,
                  schema_sha256):
    """Read committed source bytes and validate each YAML using a supplied schema."""
    model_revision = checked_revision(model_repo, model_revision)
    renderer_revision = checked_revision(renderer_repo, renderer_revision)
    with Path(schema_path).open('rb') as handle:
        schema_bytes = handle.read(MAX_SOURCE_BYTES + 1)
    if len(schema_bytes) > MAX_SOURCE_BYTES:
        raise ValueError('schema exceeds size limit')
    if not re.fullmatch(r'[0-9a-f]{64}', schema_sha256) or hashlib.sha256(schema_bytes).hexdigest() != schema_sha256:
        raise ValueError('generated schema does not match its pinned SHA-256')
    schema = json.loads(schema_bytes)
    if schema.get('$schema', 'http://json-schema.org/draft-07/schema#') != 'http://json-schema.org/draft-07/schema#':
        raise ValueError('schema must use JSON Schema draft-07')

    def require_local_references(value, depth=0):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == '$ref' and (not isinstance(item, str) or not item.startswith('#')):
                    raise ValueError('external JSON Schema references are not allowed')
                if key == '$id' and depth > 0:
                    raise ValueError('nested JSON Schema IDs are not allowed')
                require_local_references(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                require_local_references(item, depth + 1)
    require_local_references(schema)
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    paths = source_files(model_repo, model_revision, 'recipes/models')
    recipes = {}
    normalized_bytes = 0
    for path in sorted(paths):
        if not path.endswith('.yaml'):
            continue
        parts = Path(path).parts
        if len(parts) != 4:
            raise ValueError(f'unexpected recipe path: {path}')
        expected_id = canonical_id(f'{parts[2]}/{Path(parts[3]).stem}')
        raw = source_blob(model_repo, paths[path])
        recipe = json_value(yaml.load(raw, Loader=UniqueLoader))
        normalized_bytes += len(json.dumps(recipe, ensure_ascii=False, allow_nan=False).encode('utf-8'))
        if normalized_bytes > MAX_CATALOG_BYTES:
            raise ValueError('expanded recipe catalog exceeds size limit')
        validator.validate(recipe)
        if not isinstance(recipe, dict) or not isinstance(recipe.get('model'), dict):
            raise ValueError(f'invalid model definition in {path}')
        if not isinstance(recipe.get('variants'), dict) or 'default' not in recipe['variants']:
            raise ValueError(f'missing default variant in {path}')
        canonical_id(recipe['model']['model_id'])
        for variant in recipe['variants'].values():
            if not isinstance(variant, dict):
                raise ValueError(f'invalid variant in {path}')
            if 'model_id' in variant:
                canonical_id(variant['model_id'])
        key = expected_id.lower()
        if key in recipes:
            raise ValueError(f'duplicate case-insensitive recipe ID: {expected_id}')
        recipes[key] = {'model_id': expected_id, 'path': path,
                        'sha256': hashlib.sha256(raw).hexdigest(), 'recipe': recipe}
    if not recipes:
        raise ValueError('no model recipes found at pinned revision')
    renderer_paths = source_files(renderer_repo, renderer_revision, 'taxonomy.yaml', 'strategies')
    renderer = {}
    for path in sorted(renderer_paths):
        if path == 'taxonomy.yaml' or (path.startswith('strategies/') and path.endswith('.yaml')):
            raw = source_blob(renderer_repo, renderer_paths[path])
            data = json_value(yaml.load(raw, Loader=UniqueLoader))
            normalized_bytes += len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8'))
            if normalized_bytes > MAX_CATALOG_BYTES:
                raise ValueError('expanded recipe catalog exceeds size limit')
            renderer[path] = {'sha256': hashlib.sha256(raw).hexdigest(), 'data': data}
    if 'taxonomy.yaml' not in renderer or not any(path.startswith('strategies/') for path in renderer):
        raise ValueError('pinned renderer lacks taxonomy or strategies')
    return {'schema_version': 'flexserv.vllm-recipes.v1',
            'sources': {'model_revision': model_revision, 'renderer_revision': renderer_revision,
                        'json_schema_sha256': hashlib.sha256(schema_bytes).hexdigest()},
            'renderer': renderer, 'recipes': recipes}


def resolve(catalog, model_id, preferred_recipe_model_id=None):
    """Resolve the recipe without changing the requested target checkpoint."""
    target = canonical_id(model_id)
    recipes = catalog['recipes']

    def find(identifier):
        key = identifier.lower()
        if key in recipes:
            entry = recipes[key]
            return {'kind': 'exact', 'recipe_model_id': entry['model_id'],
                    'variant': 'default', 'recipe_sha256': entry['sha256']}
        matches = []
        for entry in recipes.values():
            model = entry['recipe'].get('model', {}).get('model_id')
            if model and model.lower() == key:
                matches.append((entry, 'default'))
            for variant, data in entry['recipe']['variants'].items():
                candidate = data.get('model_id')
                if candidate and candidate.lower() == key and (entry, variant) not in matches:
                    matches.append((entry, variant))
        if len(matches) > 1:
            raise ValueError(f'ambiguous variant model ID: {identifier}')
        if matches:
            entry, variant = matches[0]
            return {'kind': 'variant', 'recipe_model_id': entry['model_id'],
                    'variant': variant, 'recipe_sha256': entry['sha256']}
        return None

    match = find(target)
    if match:
        return {'target_model_id': target, 'match': match}
    preferred = canonical_id(preferred_recipe_model_id) if preferred_recipe_model_id else None
    match = find(preferred) if preferred else None
    if match:
        return {'target_model_id': target, 'preferred_recipe_model_id': preferred,
                'match': {**match, 'kind': 'preferred'}, 'requires_expert_review': True}
    return {'target_model_id': target, 'preferred_recipe_model_id': preferred,
            'match': None, 'error': 'recipe_not_found'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    build = subparsers.add_parser('build')
    for arg in ('model-repo', 'model-revision', 'renderer-repo', 'renderer-revision',
                'schema', 'schema-sha256', 'output'):
        build.add_argument('--' + arg, required=True)
    lookup = subparsers.add_parser('lookup')
    lookup.add_argument('--catalog', required=True)
    lookup.add_argument('--model', required=True)
    lookup.add_argument('--preferred')
    args = parser.parse_args()
    if args.command == 'build':
        catalog = build_catalog(args.model_repo, args.model_revision, args.renderer_repo,
                                args.renderer_revision, args.schema, args.schema_sha256)
        output = Path(args.output)
        content = json.dumps(catalog, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False) + '\n'
        if len(content.encode('utf-8')) > MAX_CATALOG_BYTES:
            raise ValueError('generated catalog exceeds size limit')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                             prefix=f'.{output.name}.', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    else:
        result = resolve(json.loads(Path(args.catalog).read_text()), args.model, args.preferred)
        print(json.dumps(result, sort_keys=True))
        if result.get('error') == 'recipe_not_found':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
