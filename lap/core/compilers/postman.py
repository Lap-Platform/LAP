#!/usr/bin/env python3
"""
Postman Collection v2.1 → LAP compiler.

Reads a Postman Collection JSON and produces a LAP spec.
Handles: folders, auth, variables, request bodies (JSON/form-data/urlencoded),
response examples, path/query/header params.
"""

import json
import re
from pathlib import Path
from typing import Optional

from lap.core.formats.lap import (
    LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema
)
from lap.core.utils import AUTH_PARAM_NAMES, AUTH_DESC_KEYWORDS, strip_html


def _resolve_variables(text: str, variables: dict) -> str:
    """Replace {{var}} with values from the variable dict."""
    if not text:
        return text
    def replacer(m):
        key = m.group(1)
        return variables.get(key, m.group(0))
    return re.sub(r'\{\{(\w+)\}\}', replacer, text)


def _extract_base_url(collection: dict, variables: dict) -> str:
    """Extract base URL from collection variables or first request."""
    if 'baseUrl' in variables:
        return variables['baseUrl']
    # Try to find from first request
    items = collection.get('item', [])
    for item in _flatten_items(items):
        req = item.get('request')
        if req and isinstance(req, dict):
            url = _get_url_string(req.get('url', ''))
            url = _resolve_variables(url, variables)
            # Extract base (scheme + host)
            m = re.match(r'(https?://[^/]+)', url)
            if m:
                return m.group(1)
    return ''


def _flatten_items(items: list) -> list:
    """Flatten nested folder items into a flat list of request items."""
    result = []
    for item in items:
        if 'request' in item:
            result.append(item)
        if 'item' in item:
            result.extend(_flatten_items(item['item']))
    return result


def _get_url_string(url) -> str:
    """Get URL string from Postman URL object or string."""
    if isinstance(url, str):
        return url
    if isinstance(url, dict):
        raw = url.get('raw', '')
        if raw:
            return raw
        # Build from parts
        protocol = url.get('protocol', 'https')
        host = '.'.join(url.get('host', []))
        path_parts = url.get('path', [])
        path = '/'.join(str(p) for p in path_parts)
        return f"{protocol}://{host}/{path}"
    return ''


def _extract_path(url, variables: dict, base_url: str) -> str:
    """Extract the path portion from a Postman URL, stripping the base."""
    url_str = _get_url_string(url)
    url_str = _resolve_variables(url_str, variables)

    # Strip base URL
    if base_url and url_str.startswith(base_url):
        path = url_str[len(base_url):]
    else:
        # Try to extract path from full URL
        m = re.match(r'https?://[^/]+(/.*)$', url_str)
        path = m.group(1) if m else url_str

    # Remove query string
    path = path.split('?')[0]

    # Normalize: convert :param to {param}
    path = re.sub(r':(\w+)', r'{\1}', path)

    if not path.startswith('/'):
        path = '/' + path

    return path


def _extract_query_params(url) -> list:
    """Extract query parameters from a Postman URL object."""
    if isinstance(url, dict):
        query = url.get('query', [])
        if not query:
            return []
        params = []
        for q in query:
            if not isinstance(q, dict):
                continue
            name = q.get('key', '')
            if not name:
                continue
            disabled = q.get('disabled', False)
            params.append(Param(
                name=name,
                type='str',
                required=not disabled,
                description=strip_html(q.get('description', '')).strip() if q.get('description') else '',
            ))
        return params
    return []


def _extract_header_params(request: dict) -> list:
    """Extract non-standard header parameters."""
    headers = request.get('header', [])
    if not headers:
        return []
    
    # Skip common auto-headers
    skip = {'content-type', 'accept', 'authorization', 'user-agent', 'host'}
    params = []
    for h in headers:
        if not isinstance(h, dict):
            continue
        name = h.get('key', '')
        if not name or name.lower() in skip:
            continue
        disabled = h.get('disabled', False)
        params.append(Param(
            name=name,
            type='str',
            required=not disabled,
            description=strip_html(h.get('description', '')).strip() if h.get('description') else '',
        ))
    return params


def _extract_path_params(url) -> list:
    """Extract path variables from Postman URL object."""
    if isinstance(url, dict):
        variables = url.get('variable', [])
        if not variables:
            return []
        params = []
        for v in variables:
            if not isinstance(v, dict):
                continue
            name = v.get('key', '')
            if not name:
                continue
            params.append(Param(
                name=name,
                type='str',
                required=True,
                description=strip_html(v.get('description', '')).strip() if v.get('description') else '',
            ))
        return params
    return []


def _extract_body_params(request: dict) -> list:
    """Extract request body parameters."""
    body = request.get('body')
    if not body:
        return []

    mode = body.get('mode', '')
    params = []

    if mode == 'raw':
        raw = body.get('raw', '')
        # Try to parse as JSON
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                for key, val in data.items():
                    params.append(Param(
                        name=key,
                        type=_infer_type(val),
                        required=not _is_likely_optional(key, val),
                        description='',
                    ))
        except (json.JSONDecodeError, TypeError):
            pass

    elif mode in ('formdata', 'urlencoded'):
        items = body.get(mode, [])
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get('key', '')
            if not name:
                continue
            disabled = item.get('disabled', False)
            item_type = item.get('type', 'text')
            param_type = 'file' if item_type == 'file' else 'str'
            params.append(Param(
                name=name,
                type=param_type,
                required=not disabled,
                description=strip_html(item.get('description', '')).strip() if item.get('description') else '',
            ))

    return params


def _is_likely_optional(key: str, value) -> bool:
    """Heuristic: infer if a raw JSON body field is optional based on its example value."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == '':
        return True
    if isinstance(value, str) and value.startswith('{{') and value.endswith('}}'):
        return False  # Postman variable placeholder → likely required
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _infer_type(value) -> str:
    """Infer LAP type from a JSON value."""
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'num'
    if isinstance(value, str):
        return 'str'
    if isinstance(value, list):
        if value:
            return f'[{_infer_type(value[0])}]'
        return '[any]'
    if isinstance(value, dict):
        return 'map'
    return 'any'


def _extract_response_schemas(item: dict) -> tuple:
    """Extract response schemas from Postman response examples."""
    responses = item.get('response', [])
    if not responses:
        return [], []

    response_schemas = []
    error_schemas = []

    for resp in responses:
        if not isinstance(resp, dict):
            continue
        code = str(resp.get('code', resp.get('status', '200')))
        name = resp.get('name', '')
        body_str = resp.get('body', '')

        fields = []
        if body_str:
            try:
                data = json.loads(body_str)
                if isinstance(data, dict):
                    fields = _fields_from_dict(data)
                elif isinstance(data, list) and data and isinstance(data[0], dict):
                    fields = _fields_from_dict(data[0])
            except (json.JSONDecodeError, TypeError):
                pass

        if code.startswith('2') or code.startswith('1'):
            response_schemas.append(ResponseSchema(
                status_code=code,
                description=name,
                fields=fields,
            ))
        else:
            error_schemas.append(ErrorSchema(
                code=code,
                description=name,
            ))

    return response_schemas, error_schemas


def _fields_from_dict(data: dict, depth: int = 0, max_depth: int = 2) -> list:
    """Create ResponseField list from a sample dict."""
    fields = []
    for key, val in data.items():
        children = []
        if isinstance(val, dict) and depth < max_depth:
            children = _fields_from_dict(val, depth + 1, max_depth)
        fields.append(ResponseField(
            name=key,
            type=_infer_type(val),
            nullable=val is None,
            children=children,
        ))
    return fields


def _extract_auth_scheme(auth: dict) -> str:
    """Convert Postman auth object to LAP auth string."""
    if not auth:
        return ''
    
    auth_type = auth.get('type', '')
    
    if auth_type == 'bearer':
        return 'Bearer token'
    elif auth_type == 'basic':
        return 'Basic username:password'
    elif auth_type == 'apikey':
        apikey_items = auth.get('apikey', [])
        key_name = 'key'
        key_in = 'header'
        for item in apikey_items:
            if isinstance(item, dict):
                if item.get('key') == 'key':
                    key_name = item.get('value', 'key')
                elif item.get('key') == 'in':
                    key_in = item.get('value', 'header')
        return f'ApiKey {key_name} in {key_in}'
    elif auth_type == 'oauth2':
        return 'OAuth2'
    elif auth_type == 'noauth':
        return ''
    
    return auth_type


def _infer_auth_from_postman(collection: dict) -> str:
    """Heuristic: scan query and header params across all requests for auth-like names/descriptions.

    Called when the collection has no explicit auth block. Returns e.g.
    "ApiKey api_key in query" or "" if nothing is found.
    """
    for item in _flatten_items(collection.get('item', [])):
        request = item.get('request', {})
        if not isinstance(request, dict):
            continue

        # Check query params from the URL object
        url = request.get('url', '')
        if isinstance(url, dict):
            for q in url.get('query', []):
                if not isinstance(q, dict):
                    continue
                name = (q.get('key') or '').strip()
                name_lower = name.lower()
                desc = (q.get('description') or '').lower()
                if name_lower in AUTH_PARAM_NAMES:
                    return f"ApiKey {name} in query"
                if any(kw in desc for kw in AUTH_DESC_KEYWORDS):
                    return f"ApiKey {name} in query"

        # Check header params
        for h in request.get('header', []):
            if not isinstance(h, dict):
                continue
            name = (h.get('key') or '').strip()
            name_lower = name.lower()
            desc = (h.get('description') or '').lower()
            if name_lower in AUTH_PARAM_NAMES:
                return f"ApiKey {name} in header"
            if any(kw in desc for kw in AUTH_DESC_KEYWORDS):
                return f"ApiKey {name} in header"

    return ""


def _collect_variables(collection: dict) -> dict:
    """Collect variables from collection-level variable array."""
    variables = {}
    for v in collection.get('variable', []):
        if isinstance(v, dict) and 'key' in v:
            variables[v['key']] = v.get('value', '')
    return variables


def compile_postman(spec_path: str) -> LAPSpec:
    """Compile a Postman Collection v2.1 JSON to LAP format."""
    path = Path(spec_path)
    file_size = path.stat().st_size
    if file_size > 50 * 1024 * 1024:
        raise ValueError(f"Collection too large: {file_size} bytes (max 50MB)")

    raw = path.read_text(encoding='utf-8')
    collection_wrapper = json.loads(raw)
    
    # Handle both wrapped {"collection": {...}} and direct format
    if 'collection' in collection_wrapper:
        collection = collection_wrapper['collection']
    elif 'info' in collection_wrapper:
        collection = collection_wrapper
    else:
        raise ValueError("Invalid Postman Collection: missing 'info' or 'collection' key")

    info = collection.get('info', {})
    variables = _collect_variables(collection)
    base_url = _extract_base_url(collection, variables)

    auth = collection.get('auth', {})
    auth_scheme = _extract_auth_scheme(auth) or _infer_auth_from_postman(collection)

    lap = LAPSpec(
        api_name=info.get('name', path.stem),
        base_url=base_url,
        version=info.get('version', '') if isinstance(info.get('version'), str) else '',
        auth_scheme=auth_scheme,
    )

    items = _flatten_items(collection.get('item', []))

    for item in items:
        request = item.get('request', {})
        if isinstance(request, str):
            # Simple string request (just URL)
            continue

        method = request.get('method', 'GET').lower()
        url = request.get('url', '')

        ep_path = _extract_path(url, variables, base_url)

        # Collect params
        path_params = _extract_path_params(url)
        query_params = _extract_query_params(url)
        header_params = _extract_header_params(request)
        body_params = _extract_body_params(request)

        required_params = path_params + [p for p in query_params if p.required]
        optional_params = [p for p in query_params if not p.required] + header_params

        response_schemas, error_schemas = _extract_response_schemas(item)

        summary = item.get('name', '').strip()

        # Per-request auth override
        req_auth = request.get('auth')
        ep_auth = _extract_auth_scheme(req_auth) if req_auth else ''

        endpoint = Endpoint(
            method=method,
            path=ep_path,
            summary=summary,
            auth=ep_auth,
            required_params=required_params,
            optional_params=optional_params,
            request_body=body_params,
            response_schemas=response_schemas,
            error_schemas=error_schemas,
        )
        lap.endpoints.append(endpoint)

    return lap


