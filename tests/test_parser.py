#!/usr/bin/env python3
"""Tests for DocLean parser and converter."""

import sys
import os

import pytest
import yaml
from pathlib import Path

from core.formats.doclean import DocLeanSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema
from core.parser import parse_doclean, _parse_param, _parse_field, _parse_returns, _parse_errors, _split_top_level
from core.compilers.openapi import compile_openapi
from core.converter import doclean_to_openapi


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


# ── Full document parsing ──

class TestParseFull:
    def test_minimal(self):
        doc = """@doclean v0.1
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
        spec = parse_doclean(doc)
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
        doc = """@doclean v0.1
@api Test

@endpoint GET /a
@returns(200)

@endpoint POST /b
@required {x: str}
@returns(201)
"""
        spec = parse_doclean(doc)
        assert len(spec.endpoints) == 2
        assert spec.endpoints[0].path == '/a'
        assert spec.endpoints[1].path == '/b'


# ── Round-trip tests ──

class TestRoundTrip:
    def _round_trip(self, spec_file: str, lean: bool = False):
        """Compile OpenAPI → DocLean → parse back and verify."""
        spec_path = SPECS_DIR / spec_file
        if not spec_path.exists():
            pytest.skip(f'{spec_file} not found')

        # Forward: OpenAPI → DocLeanSpec → DocLean text
        original = compile_openapi(str(spec_path))
        text = original.to_doclean(lean=lean)

        # Reverse: DocLean text → DocLeanSpec
        parsed = parse_doclean(text)

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
    def test_parse_stripe_doclean(self):
        path = OUTPUT_DIR / 'stripe-charges.doclean'
        if not path.exists():
            pytest.skip('stripe-charges.doclean not found')
        spec = parse_doclean(path.read_text())
        assert spec.api_name == 'Stripe Charges API'
        assert len(spec.endpoints) == 5
        assert spec.endpoints[0].method == 'post'
        assert spec.endpoints[0].path == '/v1/charges'

    def test_parse_stripe_lean(self):
        path = OUTPUT_DIR / 'stripe-charges.lean.doclean'
        if not path.exists():
            pytest.skip('stripe-charges.lean.doclean not found')
        spec = parse_doclean(path.read_text())
        assert spec.api_name == 'Stripe Charges API'
        assert len(spec.endpoints) == 5


# ── Converter tests ──

class TestConverter:
    def test_roundtrip_openapi(self):
        """OpenAPI → DocLean → parse → OpenAPI: verify structural equivalence."""
        spec_path = SPECS_DIR / 'stripe-charges.yaml'
        if not spec_path.exists():
            pytest.skip('stripe-charges.yaml not found')

        original_openapi = yaml.safe_load(spec_path.read_text())
        doclean_spec = compile_openapi(str(spec_path))
        text = doclean_spec.to_doclean(lean=False)
        parsed = parse_doclean(text)
        regenerated = doclean_to_openapi(parsed)

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
        doc = """@doclean v0.1
@api Test API
@base https://api.test.com
@version 1.0

@endpoint GET /items
@optional {limit: int=25}
@returns(200) {items: [map], total: int}
"""
        spec = parse_doclean(doc)
        openapi = doclean_to_openapi(spec)
        assert openapi['openapi'] == '3.0.0'
        assert openapi['info']['title'] == 'Test API'
        assert '/items' in openapi['paths']
        result = yaml.dump(openapi)
        reparsed = yaml.safe_load(result)
        assert reparsed == openapi


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
