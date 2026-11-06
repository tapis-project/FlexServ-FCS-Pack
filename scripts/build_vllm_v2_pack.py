#!/usr/bin/env python3
"""Publish vLLM v2 wrappers using schemas exported by the actual FCS binary."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import yaml
from package_pack import checksums


def public_input(schema):
    """Unwrap the host-fixed deployment profile without losing local definitions."""
    result = copy.deepcopy(schema['properties']['input'])
    if '$defs' in schema:
        result['$defs'] = copy.deepcopy(schema['$defs'])
    if '$ref' in result:
        definition = result['$ref'].removeprefix('#/$defs/')
        result = dict(result.get('$defs', {}).get(definition, result), **{'$defs': result.get('$defs', {})})
    return result


def build(server, source, catalog=None):
    contracts = json.loads(subprocess.check_output([str(server), '--export-native-contracts']))
    natives = {tool['name']: tool for tool in contracts['tools']}
    root = source / 'fcs_tools/io/flexserv/vllm'
    if catalog is not None:
        data = json.loads(catalog.read_text())
        if data.get('schema_version') != 'flexserv.vllm-recipes.v1':
            raise ValueError('unsupported recipe catalog format')
        for entry in data['recipes'].values():
            for field in ('guide', 'notes', 'troubleshooting', 'hardware_notes'):
                entry['recipe'].pop(field, None)
        data['projection'] = 'serving-fields-v1'
        destination = root / 'catalog/catalog.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(data, sort_keys=True, separators=(',', ':')) + '\n')
    definitions = [
        ('advanced/inspect', 'local.vllm.advanced.inspect', '1.0.0', False),
        ('deploy', 'local.vllm.v2.run', '2.0.0', True),
        ('execute', 'local.vllm.v2.run', '1.0.0', True),
        ('status', 'local.vllm.v2.status', '1.0.0', False),
        ('continue', 'local.vllm.stage.release', '1.0.0', False),
        ('inspect', 'local.vllm.v2.inspect', '1.0.0', False),
        ('stop', 'local.vllm.v2.stop', '1.0.0', False),
    ]
    tools = []
    for alias, native, version, background in definitions:
        contract = natives[native]
        path = root / alias
        (path / 'schemas').mkdir(parents=True, exist_ok=True)
        for key, schema in [('input', public_input(contract['parameters_schema'])), ('output', contract['output_schema'])]:
            (path / 'schemas' / (key + '.json')).write_text(json.dumps(schema, indent=2) + '\n')
        spec = {
            'contract': {'description': contract['description'], 'parameters_schema': 'schemas/input.json', 'output_schema': 'schemas/output.json'},
            'policy': {'derive': 'dependencies', 'resources': ['local_vllm']},
            'steps': [{'id': 'run', 'kind': 'call', 'tool': {'name': native, 'version': contract['version']},
                       'input': {'profile': 'local_vllm', 'input': '{{params}}'}}],
            'result': '{{steps.run}}',
        }
        if alias in ('advanced/inspect', 'execute'):
            spec['steps'][0]['input']['process_group_version'] = 1
        if background:
            spec['execution'] = {'mode': 'background', 'timeout_seconds': 7200, 'max_calls': 512}
            spec['distribution'] = {'mode': 'collective', 'default_selector': {'role': 'worker'}}
        document = {'schema_version': 'flexserv.tool.v1alpha3', 'kind': 'Tool',
                    'metadata': {'name': 'io.flexserv.vllm.' + alias.replace('/', '.'), 'version': version, 'visibility': True}, 'spec': spec}
        (path / 'tool.yaml').write_text(yaml.safe_dump(document, sort_keys=False))
        tools.append({'name': document['metadata']['name'], 'version': version, 'path': alias})
    for alias, original in (('cancel', 'cancel'), ('result', 'result'), ('workflow_status', 'status')):
        document = yaml.safe_load((source / 'fcs_tools/io/flexserv/deployments' / original / 'tool.yaml').read_text())
        document['metadata']['name'] = 'io.flexserv.vllm.' + alias
        old = source / 'fcs_tools/io/flexserv/deployments' / original
        import shutil
        shutil.copytree(old, root / alias, dirs_exist_ok=True)
        (root / alias / 'tool.yaml').write_text(yaml.safe_dump(document, sort_keys=False))
        tools.append({'name': document['metadata']['name'], 'version': '1.0.0', 'path': alias})
    log = natives['process.logs.read']
    path = root / 'logs'
    path.mkdir(parents=True, exist_ok=True)
    document = {'schema_version': 'flexserv.tool.v1alpha3', 'kind': 'Tool',
                'metadata': {'name': 'io.flexserv.vllm.logs', 'version': '1.0.0', 'visibility': True},
                'spec': {'contract': {'from_native': {'name': log['name'], 'version': log['version']}},
                         'policy': {}, 'steps': [{'id': 'read', 'kind': 'call', 'tool': {'name': log['name'], 'version': log['version']}, 'input': '{{params}}'}]}}
    (path / 'tool.yaml').write_text(yaml.safe_dump(document, sort_keys=False))
    tools.append({'name': 'io.flexserv.vllm.logs', 'version': '1.0.0', 'path': 'logs'})
    toolset = {'schema_version': 'flexserv.toolset.v1alpha3', 'kind': 'ToolSet',
               'metadata': {'name': 'io.flexserv.vllm', 'version': '1.0.0', 'visibility': True},
               'spec': {'description': 'Reviewed Auto and Manual vLLM deployment', 'tools': tools}}
    (root / 'toolset.yaml').write_text(yaml.safe_dump(toolset, sort_keys=False))
    for alias in ('inspect', 'stop'):
        path = source / f'fcs_tools/io/flexserv/deployments/{alias}/schemas/output.json'
        if path.exists():
            path.write_text(json.dumps(natives[f'local.deployment.{alias}']['output_schema'], indent=2) + '\n')
    # The original deployment wrappers share this native DTO. Keep their nested
    # output checks aligned when the supervisor adds observation fields.
    deployment_output = natives['local.vllm.start']['output_schema'].get('$defs', {}).get('DeploymentOutput')
    if deployment_output:
        for path in source.glob('fcs_tools/io/flexserv/deployments/**/schemas/output.json'):
            schema = json.loads(path.read_text())
            if 'DeploymentOutput' in schema.get('$defs', {}):
                schema['$defs']['DeploymentOutput'] = copy.deepcopy(deployment_output)
                path.write_text(json.dumps(schema, indent=2) + '\n')
    (source / 'checksums.sha256').write_text(checksums(source))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True, type=Path)
    parser.add_argument('--source', default=Path('pack'), type=Path)
    parser.add_argument('--catalog', type=Path, help='Project a fully validated source catalog into bounded serving fields')
    args = parser.parse_args()
    build(args.server.resolve(), args.source.resolve(), args.catalog)
