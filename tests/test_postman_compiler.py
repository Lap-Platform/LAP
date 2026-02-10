#!/usr/bin/env python3
"""
Tests for Postman Collection v2.1 → LAP compiler.
"""

import os
import sys
import json
import subprocess


import pytest
from pathlib import Path

from core.compilers.postman import (
    compile_postman,
    _resolve_variables,
    _extract_base_url,
    _flatten_items,
    _get_url_string,
    _extract_path,
    _extract_query_params,
    _extract_body_params,
    _extract_auth_scheme,
    _infer_type,
    _is_likely_optional,
    _collect_variables,
    _fields_from_dict,
)

SPECS_DIR = Path(__file__).parent.parent / 'examples' / 'verbose' / 'postman'
PROJECT_DIR = Path(__file__).parent.parent
CLI = str(PROJECT_DIR / 'cli/main.py')


# ═══════════════════════════════════════════════════════════════════
# Helper unit tests
# ═══════════════════════════════════════════════════════════════════

class TestResolveVariables:
    def test_basic(self):
        assert _resolve_variables('{{baseUrl}}/tasks', {'baseUrl': 'https://api.example.com'}) == 'https://api.example.com/tasks'

    def test_multiple(self):
        result = _resolve_variables('{{host}}/{{version}}', {'host': 'api.io', 'version': 'v2'})
        assert result == 'api.io/v2'

    def test_missing_var(self):
        assert _resolve_variables('{{unknown}}/path', {}) == '{{unknown}}/path'

    def test_empty(self):
        assert _resolve_variables('', {}) == ''


class TestInferType:
    def test_string(self):
        assert _infer_type('hello') == 'str'

    def test_int(self):
        assert _infer_type(42) == 'int'

    def test_float(self):
        assert _infer_type(3.14) == 'num'

    def test_bool(self):
        assert _infer_type(True) == 'bool'

    def test_list(self):
        assert _infer_type([1, 2, 3]) == '[int]'

    def test_empty_list(self):
        assert _infer_type([]) == '[any]'

    def test_dict(self):
        assert _infer_type({'a': 1}) == 'map'

    def test_none(self):
        assert _infer_type(None) == 'any'


class TestGetUrlString:
    def test_string_url(self):
        assert _get_url_string('https://api.io/v1') == 'https://api.io/v1'

    def test_dict_with_raw(self):
        assert _get_url_string({'raw': 'https://api.io/v1/tasks'}) == 'https://api.io/v1/tasks'

    def test_dict_from_parts(self):
        url = {'protocol': 'https', 'host': ['api', 'io'], 'path': ['v1', 'tasks']}
        assert _get_url_string(url) == 'https://api.io/v1/tasks'


class TestExtractPath:
    def test_strips_base(self):
        url = {'raw': 'https://api.io/v1/tasks'}
        path = _extract_path(url, {}, 'https://api.io/v1')
        assert path == '/tasks'

    def test_colon_params(self):
        url = {'raw': 'https://api.io/v1/tasks/:taskId'}
        path = _extract_path(url, {}, 'https://api.io/v1')
        assert path == '/tasks/{taskId}'

    def test_with_variables(self):
        url = {'raw': '{{baseUrl}}/users'}
        path = _extract_path(url, {'baseUrl': 'https://api.io'}, 'https://api.io')
        assert path == '/users'

    def test_strips_query(self):
        url = {'raw': 'https://api.io/v1/items?page=1'}
        path = _extract_path(url, {}, 'https://api.io/v1')
        assert path == '/items'


class TestExtractQueryParams:
    def test_basic(self):
        url = {'query': [{'key': 'page', 'value': '1', 'description': 'Page number'}]}
        params = _extract_query_params(url)
        assert len(params) == 1
        assert params[0].name == 'page'
        assert params[0].description == 'Page number'

    def test_disabled(self):
        url = {'query': [{'key': 'debug', 'value': 'true', 'disabled': True}]}
        params = _extract_query_params(url)
        assert len(params) == 1
        assert not params[0].required

    def test_string_url(self):
        assert _extract_query_params('https://api.io') == []


class TestExtractBodyParams:
    def test_json_body(self):
        request = {'body': {'mode': 'raw', 'raw': '{"name": "test", "count": 5}'}}
        params = _extract_body_params(request)
        assert len(params) == 2
        names = {p.name for p in params}
        assert 'name' in names
        assert 'count' in names

    def test_formdata(self):
        request = {'body': {'mode': 'formdata', 'formdata': [
            {'key': 'file', 'type': 'file'},
            {'key': 'name', 'value': 'doc', 'type': 'text'}
        ]}}
        params = _extract_body_params(request)
        assert len(params) == 2
        file_param = [p for p in params if p.name == 'file'][0]
        assert file_param.type == 'file'

    def test_urlencoded(self):
        request = {'body': {'mode': 'urlencoded', 'urlencoded': [
            {'key': 'grant_type', 'value': 'client_credentials'},
            {'key': 'scope', 'value': 'read write'}
        ]}}
        params = _extract_body_params(request)
        assert len(params) == 2

    def test_no_body(self):
        assert _extract_body_params({}) == []

    def test_invalid_json(self):
        request = {'body': {'mode': 'raw', 'raw': 'not json'}}
        assert _extract_body_params(request) == []


class TestExtractAuthScheme:
    def test_bearer(self):
        assert _extract_auth_scheme({'type': 'bearer'}) == 'Bearer token'

    def test_basic(self):
        assert _extract_auth_scheme({'type': 'basic'}) == 'Basic username:password'

    def test_apikey(self):
        auth = {'type': 'apikey', 'apikey': [
            {'key': 'key', 'value': 'X-API-Key'},
            {'key': 'in', 'value': 'header'}
        ]}
        assert _extract_auth_scheme(auth) == 'ApiKey X-API-Key in header'

    def test_oauth2(self):
        assert _extract_auth_scheme({'type': 'oauth2'}) == 'OAuth2'

    def test_noauth(self):
        assert _extract_auth_scheme({'type': 'noauth'}) == ''

    def test_empty(self):
        assert _extract_auth_scheme({}) == ''


class TestCollectVariables:
    def test_basic(self):
        coll = {'variable': [
            {'key': 'baseUrl', 'value': 'https://api.io'},
            {'key': 'token', 'value': 'abc'}
        ]}
        v = _collect_variables(coll)
        assert v == {'baseUrl': 'https://api.io', 'token': 'abc'}

    def test_empty(self):
        assert _collect_variables({}) == {}


class TestFlattenItems:
    def test_nested(self):
        items = [
            {'name': 'Folder', 'item': [
                {'name': 'Request 1', 'request': {'method': 'GET'}},
                {'name': 'Subfolder', 'item': [
                    {'name': 'Request 2', 'request': {'method': 'POST'}}
                ]}
            ]}
        ]
        flat = _flatten_items(items)
        assert len(flat) == 2
        assert flat[0]['name'] == 'Request 1'
        assert flat[1]['name'] == 'Request 2'


class TestFieldsFromDict:
    def test_basic(self):
        fields = _fields_from_dict({'id': 1, 'name': 'test', 'active': True})
        assert len(fields) == 3
        names = {f.name for f in fields}
        assert names == {'id', 'name', 'active'}

    def test_nested(self):
        fields = _fields_from_dict({'user': {'id': 1, 'name': 'test'}})
        assert len(fields) == 1
        assert fields[0].name == 'user'
        assert len(fields[0].children) == 2


# ═══════════════════════════════════════════════════════════════════
# Full compilation tests — one per spec
# ═══════════════════════════════════════════════════════════════════

def _all_postman_specs():
    return sorted(SPECS_DIR.glob('*.json'))


@pytest.fixture(params=_all_postman_specs(), ids=lambda f: f.stem)
def postman_spec(request):
    return str(request.param)


class TestCompileAllSpecs:
    def test_compiles_without_error(self, postman_spec):
        ds = compile_postman(postman_spec)
        assert ds.api_name
        assert len(ds.endpoints) > 0

    def test_all_endpoints_have_method_and_path(self, postman_spec):
        ds = compile_postman(postman_spec)
        for ep in ds.endpoints:
            assert ep.method in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')
            assert ep.path.startswith('/')

    def test_lap_output_not_empty(self, postman_spec):
        ds = compile_postman(postman_spec)
        output = ds.to_lap()
        assert '@lap' in output
        assert '@endpoint' in output

    def test_lean_output_shorter(self, postman_spec):
        ds = compile_postman(postman_spec)
        normal = ds.to_lap(lean=False)
        lean = ds.to_lap(lean=True)
        assert len(lean) <= len(normal)


class TestCrudApi:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.ds = compile_postman(str(SPECS_DIR / 'crud-api.json'))

    def test_name(self):
        assert self.ds.api_name == 'Task Manager API'

    def test_base_url(self):
        assert self.ds.base_url == 'https://api.taskmanager.io/v1'

    def test_auth(self):
        assert 'Bearer' in self.ds.auth_scheme

    def test_endpoint_count(self):
        assert len(self.ds.endpoints) == 5

    def test_crud_methods(self):
        methods = [ep.method for ep in self.ds.endpoints]
        assert 'get' in methods
        assert 'post' in methods
        assert 'put' in methods
        assert 'delete' in methods

    def test_path_params_converted(self):
        get_task = [ep for ep in self.ds.endpoints if ep.path == '/tasks/{taskId}' and ep.method == 'get'][0]
        param_names = [p.name for p in get_task.required_params]
        assert 'taskId' in param_names

    def test_query_params(self):
        list_tasks = [ep for ep in self.ds.endpoints if ep.path == '/tasks' and ep.method == 'get'][0]
        param_names = [p.name for p in list_tasks.required_params]
        assert 'status' in param_names

    def test_response_schemas(self):
        create = [ep for ep in self.ds.endpoints if ep.method == 'post'][0]
        assert len(create.response_schemas) > 0
        assert create.response_schemas[0].status_code == '201'

    def test_error_schemas(self):
        create = [ep for ep in self.ds.endpoints if ep.method == 'post'][0]
        assert len(create.error_schemas) > 0
        codes = [e.code for e in create.error_schemas]
        assert '422' in codes


class TestAuthHeavy:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.ds = compile_postman(str(SPECS_DIR / 'auth-heavy.json'))

    def test_collection_auth(self):
        assert 'Bearer' in self.ds.auth_scheme

    def test_per_request_auth_override(self):
        login = [ep for ep in self.ds.endpoints if 'token' in ep.path][0]
        assert 'Basic' in login.auth

    def test_apikey_auth(self):
        api_keys = [ep for ep in self.ds.endpoints if 'api-keys' in ep.path][0]
        assert 'ApiKey' in api_keys.auth

    def test_urlencoded_body(self):
        login = [ep for ep in self.ds.endpoints if 'token' in ep.path][0]
        param_names = [p.name for p in login.request_body]
        assert 'grant_type' in param_names

    def test_header_params(self):
        create_payment = [ep for ep in self.ds.endpoints if ep.path == '/payments' and ep.method == 'post'][0]
        opt_names = [p.name for p in create_payment.optional_params]
        assert 'Idempotency-Key' in opt_names

    def test_endpoint_count(self):
        assert len(self.ds.endpoints) == 6


class TestMultiEnv:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.ds = compile_postman(str(SPECS_DIR / 'multi-env.json'))

    def test_apikey_auth(self):
        assert 'ApiKey' in self.ds.auth_scheme

    def test_variables_resolved_in_base(self):
        assert 'configservice' in self.ds.base_url

    def test_nested_path_params(self):
        set_secret = [ep for ep in self.ds.endpoints if 'secrets' in ep.path and ep.method == 'put'][0]
        param_names = [p.name for p in set_secret.required_params]
        assert 'envName' in param_names
        assert 'secretName' in param_names

    def test_disabled_query_param(self):
        get_config = [ep for ep in self.ds.endpoints if 'config' in ep.path and ep.method == 'get'][0]
        opt_names = [p.name for p in get_config.optional_params]
        assert 'decrypt' in opt_names


class TestFileUpload:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.ds = compile_postman(str(SPECS_DIR / 'file-upload.json'))

    def test_file_param_type(self):
        upload = [ep for ep in self.ds.endpoints if ep.path == '/files' and ep.method == 'post'][0]
        file_params = [p for p in upload.request_body if p.type == 'file']
        assert len(file_params) >= 1

    def test_formdata_text_params(self):
        upload = [ep for ep in self.ds.endpoints if ep.path == '/files' and ep.method == 'post'][0]
        text_params = [p for p in upload.request_body if p.type == 'str']
        assert len(text_params) >= 2

    def test_error_413(self):
        upload = [ep for ep in self.ds.endpoints if ep.path == '/files' and ep.method == 'post'][0]
        codes = [e.code for e in upload.error_schemas]
        assert '413' in codes


class TestPaginated:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.ds = compile_postman(str(SPECS_DIR / 'paginated.json'))

    def test_pagination_params(self):
        list_events = [ep for ep in self.ds.endpoints if ep.path == '/events' and ep.method == 'get'][0]
        param_names = [p.name for p in list_events.required_params]
        assert 'page' in param_names
        assert 'per_page' in param_names

    def test_pagination_response_fields(self):
        list_events = [ep for ep in self.ds.endpoints if ep.path == '/events' and ep.method == 'get'][0]
        assert len(list_events.response_schemas) > 0
        field_names = [f.name for f in list_events.response_schemas[0].fields]
        assert 'pagination' in field_names

    def test_nested_response_fields(self):
        get_event = [ep for ep in self.ds.endpoints if '{eventId}' in ep.path][0]
        assert len(get_event.response_schemas) > 0
        field_names = [f.name for f in get_event.response_schemas[0].fields]
        assert 'metadata' in field_names
        metadata = [f for f in get_event.response_schemas[0].fields if f.name == 'metadata'][0]
        assert len(metadata.children) > 0


# ═══════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_wrapped_collection_format(self, tmp_path):
        """Test the {"collection": {...}} wrapper format."""
        coll = {
            "collection": {
                "info": {"name": "Wrapped API", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
                "item": [
                    {"name": "Test", "request": {"method": "GET", "url": "https://api.io/test"}}
                ]
            }
        }
        p = tmp_path / 'wrapped.json'
        p.write_text(json.dumps(coll))
        ds = compile_postman(str(p))
        assert ds.api_name == 'Wrapped API'
        assert len(ds.endpoints) == 1

    def test_empty_collection(self, tmp_path):
        coll = {"info": {"name": "Empty"}, "item": []}
        p = tmp_path / 'empty.json'
        p.write_text(json.dumps(coll))
        ds = compile_postman(str(p))
        assert ds.api_name == 'Empty'
        assert len(ds.endpoints) == 0

    def test_string_request_skipped(self, tmp_path):
        coll = {
            "info": {"name": "StringReq"},
            "item": [{"name": "Simple", "request": "https://api.io/test"}]
        }
        p = tmp_path / 'string_req.json'
        p.write_text(json.dumps(coll))
        ds = compile_postman(str(p))
        assert len(ds.endpoints) == 0  # string requests are skipped

    def test_deeply_nested_folders(self, tmp_path):
        coll = {
            "info": {"name": "Deep"},
            "item": [{"name": "L1", "item": [{"name": "L2", "item": [{"name": "L3", "item": [
                {"name": "Deep Request", "request": {"method": "GET", "url": "https://api.io/deep"}}
            ]}]}]}]
        }
        p = tmp_path / 'deep.json'
        p.write_text(json.dumps(coll))
        ds = compile_postman(str(p))
        assert len(ds.endpoints) == 1
        assert ds.endpoints[0].summary == 'Deep Request'


# ═══════════════════════════════════════════════════════════════════
# Token benchmark
# ═══════════════════════════════════════════════════════════════════

class TestTokenBenchmark:
    """Verify LAP compression provides meaningful reduction vs raw JSON."""

    def test_compression_ratio(self):
        """LAP should be significantly smaller than raw Postman JSON."""
        ratios = []
        for spec_file in _all_postman_specs():
            raw_size = len(spec_file.read_text())
            ds = compile_postman(str(spec_file))
            lap_size = len(ds.to_lap(lean=False))
            lean_size = len(ds.to_lap(lean=True))
            ratio = raw_size / lap_size if lap_size else float('inf')
            lean_ratio = raw_size / lean_size if lean_size else float('inf')
            ratios.append((spec_file.stem, ratio, lean_ratio))

        # Every spec should achieve at least 2x compression
        for name, ratio, lean_ratio in ratios:
            assert ratio > 1.5, f"{name}: only {ratio:.1f}x compression (expected >1.5x)"

    def test_lean_smaller_than_standard(self):
        for spec_file in _all_postman_specs():
            ds = compile_postman(str(spec_file))
            normal = ds.to_lap(lean=False)
            lean = ds.to_lap(lean=True)
            assert len(lean) <= len(normal), f"{spec_file.stem}: lean not smaller"


# ═══════════════════════════════════════════════════════════════════
# CLI integration
# ═══════════════════════════════════════════════════════════════════

class TestIsLikelyOptional:
    """Tests for raw JSON body required/optional heuristics."""

    def test_none_is_optional(self):
        assert _is_likely_optional('field', None) is True

    def test_empty_string_is_optional(self):
        assert _is_likely_optional('field', '') is True
        assert _is_likely_optional('field', '  ') is True

    def test_empty_list_is_optional(self):
        assert _is_likely_optional('field', []) is True

    def test_postman_variable_is_required(self):
        assert _is_likely_optional('token', '{{auth_token}}') is False

    def test_non_empty_string_is_required(self):
        assert _is_likely_optional('name', 'hello') is False

    def test_number_is_required(self):
        assert _is_likely_optional('count', 42) is False

    def test_populated_list_is_required(self):
        assert _is_likely_optional('ids', [1, 2]) is False

    def test_raw_body_optional_fields(self):
        """Empty strings and null in raw JSON body should produce optional params."""
        request = {
            'body': {
                'mode': 'raw',
                'raw': json.dumps({
                    'channel': '{{channel_id}}',
                    'thread_ts': '',
                    'metadata': None,
                    'tags': [],
                    'limit': 100,
                }),
            }
        }
        params = _extract_body_params(request)
        by_name = {p.name: p for p in params}
        assert by_name['channel'].required is True
        assert by_name['thread_ts'].required is False
        assert by_name['metadata'].required is False
        assert by_name['tags'].required is False
        assert by_name['limit'].required is True


class TestCLI:
    def test_postman_subcommand(self):
        result = subprocess.run(
            [sys.executable, CLI, 'compile', str(SPECS_DIR / 'crud-api.json')],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert '@lap' in result.stdout
        assert '@endpoint' in result.stdout
        assert 'Task Manager' in result.stdout

    def test_postman_lean(self):
        result = subprocess.run(
            [sys.executable, CLI, 'compile', '--lean', str(SPECS_DIR / 'crud-api.json')],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert '@desc' not in result.stdout

    def test_postman_output_file(self, tmp_path):
        out = tmp_path / 'out.lap'
        result = subprocess.run(
            [sys.executable, CLI, 'compile', str(SPECS_DIR / 'crud-api.json'), '-o', str(out)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert out.exists()
        content = out.read_text()
        assert '@lap' in content
