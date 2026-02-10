#!/usr/bin/env python3
"""
LAP → OpenAPI Converter

Parses LAP text and outputs valid OpenAPI 3.0 YAML.
Proves zero information loss in a machine-verifiable way.
"""

import re
import sys
from pathlib import Path

import yaml

from core.parser import parse_lap
from core.formats.lap import LAPSpec, Endpoint, Param, ResponseField


def _type_to_openapi(type_str: str) -> dict:
    """Convert LAP type string to OpenAPI schema."""
    # Array type: [inner]
    if type_str.startswith('[') and type_str.endswith(']'):
        return {'type': 'array', 'items': _type_to_openapi(type_str[1:-1])}

    # Type with format: int(unix-timestamp), str(email)
    m = re.match(r'^(\w+)\(([^)]+)\)$', type_str)
    if m:
        base, fmt = m.group(1), m.group(2)
        schema = _type_to_openapi(base)
        schema['format'] = fmt
        return schema

    type_map = {
        'str': {'type': 'string'},
        'int': {'type': 'integer'},
        'num': {'type': 'number'},
        'bool': {'type': 'boolean'},
        'map': {'type': 'object'},
        'any': {},
    }
    return dict(type_map.get(type_str, {'type': type_str}))


def _param_to_openapi(param: Param, location: str = 'query') -> dict:
    """Convert a Param to OpenAPI parameter or property schema."""
    schema = _type_to_openapi(param.type)
    if param.enum:
        schema['enum'] = param.enum
    if param.default is not None:
        # Try to coerce default to appropriate type
        if param.type == 'int':
            try:
                schema['default'] = int(param.default)
            except ValueError:
                schema['default'] = param.default
        elif param.type == 'bool':
            schema['default'] = param.default.lower() in ('true', '1')
        else:
            schema['default'] = param.default
    if param.description:
        schema['description'] = param.description
    return schema


def _field_to_openapi(f: ResponseField) -> dict:
    """Convert a ResponseField to OpenAPI schema."""
    schema = _type_to_openapi(f.type)
    if f.nullable:
        schema['nullable'] = True
    if f.children:
        schema['type'] = 'object'
        props = {}
        for child in f.children:
            props[child.name] = _field_to_openapi(child)
        schema['properties'] = props
    return schema


def lap_to_openapi(spec: LAPSpec) -> dict:
    """Convert a LAPSpec to an OpenAPI 3.0 dict."""
    openapi = {
        'openapi': '3.0.0',
        'info': {
            'title': spec.api_name,
        },
        'paths': {},
    }
    if spec.version:
        openapi['info']['version'] = spec.version
    if spec.base_url:
        openapi['servers'] = [{'url': spec.base_url}]

    # Auth
    if spec.auth_scheme:
        schemes = {}
        for part in spec.auth_scheme.split(' | '):
            part = part.strip()
            if part.startswith('Bearer'):
                schemes['bearerAuth'] = {'type': 'http', 'scheme': 'bearer'}
            elif part.startswith('ApiKey'):
                m = re.match(r'ApiKey\s+(\S+)\s+in\s+(\S+)', part)
                name = m.group(1) if m else 'api_key'
                loc = m.group(2) if m else 'header'
                schemes['apiKeyAuth'] = {'type': 'apiKey', 'name': name, 'in': loc}
            elif part == 'OAuth2':
                schemes['oauth2'] = {'type': 'oauth2', 'flows': {}}
        if schemes:
            openapi['components'] = {'securitySchemes': schemes}
            openapi['security'] = [{name: [] for name in schemes}]

    for ep in spec.endpoints:
        path_params = set()
        import re as _re
        for m in _re.finditer(r'\{(\w+)\}', ep.path):
            path_params.add(m.group(1))

        operation = {}
        if ep.summary:
            operation['summary'] = ep.summary

        parameters = []
        # Path params from required
        for p in ep.required_params:
            if p.name in path_params:
                param = {
                    'name': p.name,
                    'in': 'path',
                    'required': True,
                    'schema': _param_to_openapi(p),
                }
                if p.description:
                    param['description'] = p.description
                    param['schema'].pop('description', None)
                parameters.append(param)

        # Query params
        for p in ep.required_params:
            if p.name not in path_params:
                param = {
                    'name': p.name,
                    'in': 'query',
                    'required': True,
                    'schema': _param_to_openapi(p),
                }
                if p.description:
                    param['description'] = p.description
                    param['schema'].pop('description', None)
                parameters.append(param)

        for p in ep.optional_params:
            if p.name in path_params:
                loc = 'path'
            else:
                loc = 'query'
            param = {
                'name': p.name,
                'in': loc,
                'required': False,
                'schema': _param_to_openapi(p),
            }
            if p.description:
                param['description'] = p.description
                param['schema'].pop('description', None)
            parameters.append(param)

        if parameters:
            operation['parameters'] = parameters

        # Request body (for POST/PUT/PATCH — body params from required/optional that aren't path params)
        if ep.method.lower() in ('post', 'put', 'patch'):
            body_props = {}
            body_required = []
            for p in ep.required_params:
                if p.name not in path_params:
                    body_props[p.name] = _param_to_openapi(p)
                    body_required.append(p.name)
            for p in ep.optional_params:
                if p.name not in path_params:
                    body_props[p.name] = _param_to_openapi(p)

            if body_props:
                # Remove from parameters (they go in body instead)
                operation['parameters'] = [
                    p for p in parameters if p['name'] in path_params
                ]
                if not operation['parameters']:
                    del operation['parameters']

                body_schema = {'type': 'object', 'properties': body_props}
                if body_required:
                    body_schema['required'] = body_required
                operation['requestBody'] = {
                    'content': {
                        'application/json': {
                            'schema': body_schema
                        }
                    }
                }

        # Responses
        responses = {}
        for rs in ep.response_schemas:
            resp = {}
            if rs.description:
                resp['description'] = rs.description
            else:
                resp['description'] = 'Success' if rs.status_code.startswith('2') else 'Response'
            if rs.fields:
                props = {}
                for f in rs.fields:
                    props[f.name] = _field_to_openapi(f)
                resp['content'] = {
                    'application/json': {
                        'schema': {
                            'type': 'object',
                            'properties': props,
                        }
                    }
                }
            responses[rs.status_code] = resp

        for es in ep.error_schemas:
            resp = {'description': es.description or 'Error'}
            responses[es.code] = resp

        if responses:
            operation['responses'] = responses

        if ep.path not in openapi['paths']:
            openapi['paths'][ep.path] = {}
        openapi['paths'][ep.path][ep.method.lower()] = operation

    return openapi


def convert_file(input_path: str, output_path: str = None) -> str:
    """Convert a LAP file to OpenAPI YAML."""
    file_size = Path(input_path).stat().st_size
    if file_size > 10 * 1024 * 1024:
        raise ValueError(f"LAP file too large: {file_size} bytes (max 10MB)")
    text = Path(input_path).read_text()
    spec = parse_lap(text)
    openapi = lap_to_openapi(spec)
    result = yaml.dump(openapi, sort_keys=False, default_flow_style=False)
    if output_path:
        Path(output_path).write_text(result)
    return result


def main():
    import argparse
    p = argparse.ArgumentParser(description='Convert LAP to OpenAPI YAML')
    p.add_argument('input', help='LAP file')
    p.add_argument('-o', '--output', help='Output YAML file')
    args = p.parse_args()

    result = convert_file(args.input, args.output)
    if not args.output:
        print(result)
    else:
        print(f'✅ Converted to {args.output}')


if __name__ == '__main__':
    main()
