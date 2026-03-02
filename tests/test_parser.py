#!/usr/bin/env python3
"""Tests for LAP parser and converter."""

import sys
import os

import pytest
import yaml
from pathlib import Path

from lap.core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema
from lap.core.parser import parse_lap, _parse_param, _parse_field, _parse_returns, _parse_errors, _split_top_level
from lap.core.compilers.openapi import compile_openapi
from lap.core.converter import lap_to_openapi


# ── Helper ──

SPECS_DIR = Path(__file__).parent.parent / 'examples'
OUTPUT_DIR = Path(__file__).parent.parent / 'output'


# ── Unit tests for parsing primitives ──

class TestSplitTopLevel:
    def test_simple(self):
        # _split_top_level only splits at field boundaries (word: type pattern)
        # Plain values like 'a, b, c' are not field definitions
        assert _split_top_level('a, b, c') == ['a, b, c']

    def test_simple_fields(self):
        assert _split_top_level('a: str, b: int, c: bool') == ['a: str', 'b: int', 'c: bool']

    def test_nested_braces(self):
        result = _split_top_level('a: map{x: str, y: int}, b: str')
        assert len(result) == 2
        assert 'x: str, y: int' in result[0]

    def test_nested_parens(self):
        result = _split_top_level('a: str(email/url), b: int')
        assert len(result) == 2


class TestParseParam:
    def test_simple(self):
        p = _parse_param('name: str')
        assert p.name == 'name'
        assert p.type == 'str'

    def test_with_description(self):
        p = _parse_param('name: str # A user name')
        assert p.name == 'name'
        assert p.type == 'str'
        assert p.description == 'A user name'

    def test_with_default(self):
        p = _parse_param('limit: int=10')
        assert p.name == 'limit'
        assert p.type == 'int'
        assert p.default == '10'

    def test_with_enum(self):
        p = _parse_param('status: str(active/inactive/pending)')
        assert p.name == 'status'
        assert p.type == 'str'
        assert p.enum == ['active', 'inactive', 'pending']

    def test_with_format(self):
        p = _parse_param('created: int(unix-timestamp)')
        assert p.name == 'created'
        assert p.type == 'int(unix-timestamp)'  # format, not enum

    def test_default_and_description(self):
        p = _parse_param('limit: int=10 # Max results')
        assert p.default == '10'
        assert p.description == 'Max results'


class TestParseField:
    def test_simple(self):
        f = _parse_field('id: str')
        assert f.name == 'id'
        assert f.type == 'str'
        assert not f.nullable

    def test_nullable(self):
        f = _parse_field('email: str?')
        assert f.name == 'email'
        assert f.type == 'str'
        assert f.nullable

    def test_nested_map(self):
        f = _parse_field('billing: map{name: str?, email: str?}')
        assert f.name == 'billing'
        assert f.type == 'map'
        assert len(f.children) == 2
        assert f.children[0].name == 'name'
        assert f.children[0].nullable

    def test_deep_nested(self):
        f = _parse_field('outer: map{inner: map{deep: str}}')
        assert f.children[0].name == 'inner'
        assert f.children[0].children[0].name == 'deep'


class TestParseReturns:
    def test_code_only(self):
        rs = _parse_returns('@returns(200)')
        assert rs.status_code == '200'
        assert rs.fields == []

    def test_with_description(self):
        rs = _parse_returns('@returns(200) Returns the charge object.')
        assert rs.status_code == '200'
        assert rs.description == 'Returns the charge object.'

    def test_with_fields(self):
        rs = _parse_returns('@returns(200) {id: str, name: str?}')
        assert len(rs.fields) == 2
        assert rs.fields[0].name == 'id'
        assert rs.fields[1].nullable

    def test_with_fields_and_comment(self):
        rs = _parse_returns('@returns(200) {id: str} # Success')
        assert len(rs.fields) == 1
        assert rs.description == 'Success'


class TestParseErrors:
    def test_with_descriptions(self):
        errors = _parse_errors('@errors {400: Bad request, 401: Unauthorized}')
        assert len(errors) == 2
        assert errors[0].code == '400'
        assert errors[0].description == 'Bad request'

    def test_codes_only(self):
        errors = _parse_errors('@errors {400, 401, 404}')
        assert len(errors) == 3
        assert errors[1].code == '401'
        assert errors[1].description == ''

    def test_description_with_commas(self):
        """Commas inside error descriptions should not split into new errors."""
        errors = _parse_errors('@errors {404: Not found, check the ID, 500: Server error}')
        assert len(errors) == 2
        assert errors[0].code == '404'
        assert 'check the ID' in errors[0].description
        assert errors[1].code == '500'


# ── v0.3 format tests ──

class TestExpandedMapType:
    def test_param_with_inline_map(self):
        p = _parse_param('user: map{legal_name!: str, email: str}')
        assert p.name == 'user'
        assert p.type == 'map{legal_name!: str, email: str}'

    def test_param_with_inline_map_and_desc(self):
        p = _parse_param('user: map{name!: str, email: str} # User info')
        assert p.name == 'user'
        assert p.type == 'map{name!: str, email: str}'
        assert p.description == 'User info'


class TestV03Directives:
    def test_common_fields(self):
        doc = """@lap v0.3
@api Test
@auth OAuth2
@common_fields {client_id: str # Your client ID, secret: str # Your secret}
@endpoints 1

@endpoint POST /items
@required {name: str}
@returns(200)
"""
        spec = parse_lap(doc)
        assert len(spec.common_fields) == 2
        assert spec.common_fields[0].name == 'client_id'
        assert spec.common_fields[1].name == 'secret'

    def test_hint_skipped(self):
        doc = """@lap v0.3
@api Test
@endpoints 0
@hint download_for_search
"""
        spec = parse_lap(doc)
        assert spec.api_name == 'Test'

    def test_group_markers_skipped(self):
        doc = """@lap v0.3
@api Test

@group users
@endpoint GET /users
@returns(200)
@endgroup

@group items
@endpoint GET /items
@returns(200)
@endgroup
"""
        spec = parse_lap(doc)
        assert len(spec.endpoints) == 2
        assert spec.endpoints[0].path == '/users'
        assert spec.endpoints[1].path == '/items'

    def test_example_request_skipped(self):
        doc = """@lap v0.3
@api Test

@endpoint POST /items
@required {name: str}
@example_request {"name":"test"}
@returns(201)
"""
        spec = parse_lap(doc)
        assert len(spec.endpoints) == 1
        assert spec.endpoints[0].path == '/items'

    def test_grouped_toc(self):
        """Grouped TOC format: name(count), ..."""
        from lap.core.formats.lap import LAPSpec, Endpoint
        spec = LAPSpec(
            api_name='Test',
            endpoints=[
                Endpoint(method='get', path='/v1/users', summary='List'),
                Endpoint(method='post', path='/v1/users', summary='Create'),
                Endpoint(method='get', path='/v1/items', summary='List items'),
            ],
        )
        text = spec.to_lap()
        assert '@toc users(2), items(1)' in text

    def test_group_markers_emitted(self):
        """Multiple path prefixes emit @group markers."""
        from lap.core.formats.lap import LAPSpec, Endpoint
        spec = LAPSpec(
            api_name='Test',
            endpoints=[
                Endpoint(method='get', path='/users'),
                Endpoint(method='get', path='/items'),
            ],
        )
        text = spec.to_lap()
        assert '@group users' in text
        assert '@group items' in text
        assert '@endgroup' in text

    def test_download_hint(self):
        """Specs with >20 endpoints emit @hint."""
        from lap.core.formats.lap import LAPSpec, Endpoint
        endpoints = [Endpoint(method='get', path=f'/ep{i}') for i in range(25)]
        spec = LAPSpec(api_name='Test', endpoints=endpoints)
        text = spec.to_lap()
        assert '@hint download_for_search' in text


# ── Full document parsing ──

class TestParseFull:
    def test_minimal(self):
        doc = """@lap v0.1
@api Test API
@base https://api.test.com
@version 1.0
@auth Bearer token

@endpoint GET /users
@desc List users
@optional {limit: int=10}
@returns(200) {id: str, name: str}
@errors {401: Unauthorized}
"""
        spec = parse_lap(doc)
        assert spec.api_name == 'Test API'
        assert spec.base_url == 'https://api.test.com'
        assert spec.version == '1.0'
        assert spec.auth_scheme == 'Bearer token'
        assert len(spec.endpoints) == 1

        ep = spec.endpoints[0]
        assert ep.method == 'get'
        assert ep.path == '/users'
        assert ep.summary == 'List users'
        assert len(ep.optional_params) == 1
        assert ep.optional_params[0].default == '10'
        assert len(ep.response_schemas) == 1
        assert len(ep.response_schemas[0].fields) == 2
        assert len(ep.error_schemas) == 1

    def test_multiple_endpoints(self):
        doc = """@lap v0.1
@api Test

@endpoint GET /a
@returns(200)

@endpoint POST /b
@required {x: str}
@returns(201)
"""
        spec = parse_lap(doc)
        assert len(spec.endpoints) == 2
        assert spec.endpoints[0].path == '/a'
        assert spec.endpoints[1].path == '/b'


# ── Round-trip tests ──

class TestRoundTrip:
    def _round_trip(self, spec_file: str, lean: bool = False):
        """Compile OpenAPI → LAP → parse back and verify."""
        spec_path = SPECS_DIR / spec_file
        if not spec_path.exists():
            pytest.skip(f'{spec_file} not found')

        # Forward: OpenAPI → LAPSpec → LAP text
        original = compile_openapi(str(spec_path))
        text = original.to_lap(lean=lean)

        # Reverse: LAP text → LAPSpec
        parsed = parse_lap(text)

        # Verify header
        assert parsed.api_name == original.api_name
        assert parsed.base_url == original.base_url
        assert parsed.version == original.version

        # Verify endpoints count
        assert len(parsed.endpoints) == len(original.endpoints), \
            f'Endpoint count mismatch: {len(parsed.endpoints)} vs {len(original.endpoints)}'

        # Verify each endpoint
        for orig_ep, parsed_ep in zip(original.endpoints, parsed.endpoints):
            assert parsed_ep.method == orig_ep.method
            assert parsed_ep.path == orig_ep.path
            if not lean:
                assert parsed_ep.summary == orig_ep.summary

            # Verify param counts
            orig_req = orig_ep.required_params + [p for p in orig_ep.request_body if p.required]
            orig_opt = orig_ep.optional_params + [p for p in orig_ep.request_body if not p.required]
            assert len(parsed_ep.required_params) == len(orig_req), \
                f'{orig_ep.method} {orig_ep.path}: required params {len(parsed_ep.required_params)} vs {len(orig_req)}'
            assert len(parsed_ep.optional_params) == len(orig_opt), \
                f'{orig_ep.method} {orig_ep.path}: optional params {len(parsed_ep.optional_params)} vs {len(orig_opt)}'

            # Verify param names and types
            for orig_p, parsed_p in zip(orig_req, parsed_ep.required_params):
                assert parsed_p.name == orig_p.name
                assert parsed_p.type == orig_p.type

            for orig_p, parsed_p in zip(orig_opt, parsed_ep.optional_params):
                assert parsed_p.name == orig_p.name
                assert parsed_p.type == orig_p.type

            # Verify response schema count
            assert len(parsed_ep.response_schemas) == len(orig_ep.response_schemas), \
                f'{orig_ep.method} {orig_ep.path}: response schemas mismatch'

    def test_stripe_standard(self):
        self._round_trip('stripe-charges.yaml', lean=False)

    def test_stripe_lean(self):
        self._round_trip('stripe-charges.yaml', lean=True)

    def test_github(self):
        self._round_trip('github-core.yaml', lean=False)

    def test_openai(self):
        self._round_trip('openai-core.yaml', lean=False)

    def test_slack(self):
        self._round_trip('slack.yaml', lean=False)


# ── Parse from file tests ──

class TestParseFromFile:
    def test_parse_stripe_lap(self):
        path = OUTPUT_DIR / 'stripe-charges.lap'
        if not path.exists():
            pytest.skip('stripe-charges.lap not found')
        spec = parse_lap(path.read_text(encoding='utf-8'))
        assert spec.api_name == 'Stripe Charges API'
        assert len(spec.endpoints) == 5
        assert spec.endpoints[0].method == 'post'
        assert spec.endpoints[0].path == '/v1/charges'

    def test_parse_stripe_lean(self):
        path = OUTPUT_DIR / 'stripe-charges.lean.lap'
        if not path.exists():
            pytest.skip('stripe-charges.lean.lap not found')
        spec = parse_lap(path.read_text(encoding='utf-8'))
        assert spec.api_name == 'Stripe Charges API'
        assert len(spec.endpoints) == 5


# ── Converter tests ──

class TestConverter:
    def test_roundtrip_openapi(self):
        """OpenAPI → LAP → parse → OpenAPI: verify structural equivalence."""
        spec_path = SPECS_DIR / 'stripe-charges.yaml'
        if not spec_path.exists():
            pytest.skip('stripe-charges.yaml not found')

        original_openapi = yaml.safe_load(spec_path.read_text(encoding='utf-8'))
        lap_spec = compile_openapi(str(spec_path))
        text = lap_spec.to_lap(lean=False)
        parsed = parse_lap(text)
        regenerated = lap_to_openapi(parsed)

        # Verify same paths exist
        orig_paths = set(original_openapi.get('paths', {}).keys())
        regen_paths = set(regenerated.get('paths', {}).keys())
        assert orig_paths == regen_paths, f'Path mismatch: {orig_paths - regen_paths}'

        # Verify same methods per path
        for path in orig_paths:
            orig_methods = set(k for k in original_openapi['paths'][path] if k in ('get', 'post', 'put', 'patch', 'delete'))
            regen_methods = set(k for k in regenerated['paths'][path] if k in ('get', 'post', 'put', 'patch', 'delete'))
            assert orig_methods == regen_methods, f'{path}: methods {orig_methods} vs {regen_methods}'

    def test_converter_produces_valid_yaml(self):
        doc = """@lap v0.1
@api Test API
@base https://api.test.com
@version 1.0

@endpoint GET /items
@optional {limit: int=25}
@returns(200) {items: [map], total: int}
"""
        spec = parse_lap(doc)
        openapi = lap_to_openapi(spec)
        assert openapi['openapi'] == '3.0.0'
        assert openapi['info']['title'] == 'Test API'
        assert '/items' in openapi['paths']
        result = yaml.dump(openapi)
        reparsed = yaml.safe_load(result)
        assert reparsed == openapi


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
