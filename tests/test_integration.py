#!/usr/bin/env python3
"""
Integration tests for LAP (LeanAgent Protocol).

Covers:
1. Full pipeline round-trip for every spec (compile → parse → convert)
2. Edge cases (empty, no params, deep nesting, huge params, etc.)
3. CLI subprocess integration tests
"""

import os
import sys
import subprocess
import glob


import pytest
import yaml
from pathlib import Path

from core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema
from core.parser import parse_lap
from core.compilers.openapi import compile_openapi
from core.converter import lap_to_openapi

SPECS_DIR = Path(__file__).parent.parent / 'examples' / 'verbose' / 'openapi'
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
PROJECT_DIR = Path(__file__).parent.parent
CLI = str(PROJECT_DIR / 'cli/main.py')
OUTPUT_DIR = PROJECT_DIR / 'output'


# ═══════════════════════════════════════════════════════════════════
# 1. Full Pipeline Round-Trip — every spec in examples/
# ═══════════════════════════════════════════════════════════════════

def _all_spec_files():
    """Get all spec files excluding incompatible ones.
    
    Excluded:
    - stripe-full: too large for fast tests
    - jira: YAML parsing error (bare '=' in enum triggers YAML tag error)
    """
    files = sorted(glob.glob(str(SPECS_DIR / '*.yaml')))
    return [f for f in files if 'stripe-full' not in f and 'jira' not in f]


@pytest.fixture(params=_all_spec_files(), ids=lambda f: Path(f).stem)
def spec_file(request):
    return request.param


class TestFullPipelineRoundTrip:
    """For every spec: compile → parse → convert → verify."""

    def test_standard_round_trip(self, spec_file):
        """OpenAPI → LAP(standard) → parse → verify structure."""
        original = compile_openapi(spec_file)
        text = original.to_lap(lean=False)
        parsed = parse_lap(text)

        assert parsed.api_name == original.api_name
        assert parsed.base_url == original.base_url
        assert parsed.version == original.version
        assert len(parsed.endpoints) == len(original.endpoints)

        for orig_ep, parsed_ep in zip(original.endpoints, parsed.endpoints):
            assert parsed_ep.method == orig_ep.method
            assert parsed_ep.path == orig_ep.path
            assert parsed_ep.summary == orig_ep.summary

            orig_req = orig_ep.required_params + [p for p in orig_ep.request_body if p.required]
            orig_opt = orig_ep.optional_params + [p for p in orig_ep.request_body if not p.required]
            assert len(parsed_ep.required_params) == len(orig_req), \
                f'{orig_ep.method} {orig_ep.path}: required mismatch'
            assert len(parsed_ep.optional_params) == len(orig_opt), \
                f'{orig_ep.method} {orig_ep.path}: optional mismatch'

            for op, pp in zip(orig_req, parsed_ep.required_params):
                assert pp.name == op.name
                assert pp.type == op.type

            for op, pp in zip(orig_opt, parsed_ep.optional_params):
                assert pp.name == op.name
                assert pp.type == op.type

    def test_lean_round_trip(self, spec_file):
        """OpenAPI → LAP(lean) → parse → verify no descriptions."""
        original = compile_openapi(spec_file)
        text = original.to_lap(lean=True)
        parsed = parse_lap(text)

        assert len(parsed.endpoints) == len(original.endpoints)

        for ep in parsed.endpoints:
            assert ep.summary == '', f'{ep.method} {ep.path} has summary in lean mode: {ep.summary!r}'
            for p in ep.required_params + ep.optional_params:
                assert p.description == '', \
                    f'{ep.method} {ep.path} param {p.name} has description in lean mode'

    def test_convert_back_to_openapi(self, spec_file):
        """OpenAPI → LAP → parse → OpenAPI: same paths and methods."""
        original_yaml = yaml.safe_load(Path(spec_file).read_text())
        compiled = compile_openapi(spec_file)
        text = compiled.to_lap(lean=False)
        parsed = parse_lap(text)
        regenerated = lap_to_openapi(parsed)

        orig_paths = set(original_yaml.get('paths', {}).keys())
        regen_paths = set(regenerated.get('paths', {}).keys())
        assert orig_paths == regen_paths

        for path in orig_paths:
            orig_methods = {k for k in original_yaml['paths'][path] if k in ('get', 'post', 'put', 'patch', 'delete')}
            regen_methods = {k for k in regenerated['paths'][path] if k in ('get', 'post', 'put', 'patch', 'delete')}
            assert orig_methods == regen_methods, f'{path}: {orig_methods} vs {regen_methods}'

    def test_idempotent_serialization(self, spec_file):
        """Serialize → parse → serialize should produce identical output."""
        compiled = compile_openapi(spec_file)
        text1 = compiled.to_lap()
        parsed = parse_lap(text1)
        text2 = parsed.to_lap()
        assert text1.strip() == text2.strip()


# ═══════════════════════════════════════════════════════════════════
# 2. Edge Case Tests
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCaseEmpty:
    def test_empty_spec(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'empty_spec.yaml'))
        assert spec.api_name == 'Empty API'
        assert len(spec.endpoints) == 0
        text = spec.to_lap()
        parsed = parse_lap(text)
        assert len(parsed.endpoints) == 0

    def test_empty_spec_to_openapi(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'empty_spec.yaml'))
        text = spec.to_lap()
        parsed = parse_lap(text)
        openapi = lap_to_openapi(parsed)
        assert openapi['paths'] == {}


class TestEdgeCaseNoParams:
    def test_no_params_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'no_params.yaml'))
        assert len(spec.endpoints) == 1
        ep = spec.endpoints[0]
        assert ep.required_params == []
        assert ep.optional_params == []
        assert ep.request_body == []
        text = spec.to_lap()
        parsed = parse_lap(text)
        assert len(parsed.endpoints) == 1
        assert parsed.endpoints[0].required_params == []
        assert parsed.endpoints[0].optional_params == []


class TestEdgeCaseOnlyRequired:
    def test_only_required_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'only_required.yaml'))
        ep = spec.endpoints[0]
        assert len(ep.required_params) == 1
        assert ep.required_params[0].name == 'user_id'
        assert ep.optional_params == []
        text = spec.to_lap()
        parsed = parse_lap(text)
        assert len(parsed.endpoints[0].required_params) == 1
        assert parsed.endpoints[0].required_params[0].name == 'user_id'


class TestEdgeCaseDeepNested:
    def test_deep_nested_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'deep_nested.yaml'))
        ep = spec.endpoints[0]
        assert len(ep.response_schemas) == 1
        text = spec.to_lap()
        parsed = parse_lap(text)
        assert len(parsed.endpoints) == 1
        rs = parsed.endpoints[0].response_schemas[0]
        field_names = {f.name for f in rs.fields}
        assert 'level1' in field_names or 'top_field' in field_names


class TestEdgeCaseManyParams:
    def test_many_params_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'many_params.yaml'))
        ep = spec.endpoints[0]
        total_orig = len(ep.required_params) + len(ep.optional_params)
        assert total_orig >= 20
        text = spec.to_lap()
        parsed = parse_lap(text)
        ep_parsed = parsed.endpoints[0]
        total_parsed = len(ep_parsed.required_params) + len(ep_parsed.optional_params)
        assert total_parsed == total_orig


class TestEdgeCaseNoAuth:
    def test_no_auth_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'no_auth.yaml'))
        assert spec.auth_scheme == ''
        text = spec.to_lap()
        parsed = parse_lap(text)
        assert parsed.auth_scheme == ''
        assert len(parsed.endpoints) == 2


class TestEdgeCaseSpecialChars:
    def test_special_chars_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'special_chars.yaml'))
        ep = spec.endpoints[0]
        param_names = {p.name for p in ep.required_params + ep.optional_params}
        assert 'query' in param_names
        assert 'format' in param_names
        text = spec.to_lap()
        parsed = parse_lap(text)
        parsed_names = {p.name for p in parsed.endpoints[0].required_params + parsed.endpoints[0].optional_params}
        assert 'query' in parsed_names


class TestEdgeCaseBigEnum:
    def test_big_enum_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'big_enum.yaml'))
        ep = spec.endpoints[0]
        country_param = next(p for p in ep.required_params + ep.optional_params if p.name == 'country')
        assert len(country_param.enum) == 20
        text = spec.to_lap()
        parsed = parse_lap(text)
        ep_parsed = parsed.endpoints[0]
        country_parsed = next(p for p in ep_parsed.required_params + ep_parsed.optional_params if p.name == 'country')
        assert len(country_parsed.enum) == 20
        assert 'US' in country_parsed.enum
        assert 'FI' in country_parsed.enum


class TestEdgeCaseArrayNested:
    def test_array_nested_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'array_nested.yaml'))
        ep = spec.endpoints[0]
        rs = ep.response_schemas[0]
        field_names = {f.name for f in rs.fields}
        assert 'orders' in field_names or 'total' in field_names
        text = spec.to_lap()
        parsed = parse_lap(text)
        assert len(parsed.endpoints) == 1


class TestEdgeCaseMultiAuth:
    def test_multi_auth_round_trip(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'multi_auth.yaml'))
        assert 'Bearer' in spec.auth_scheme
        assert 'ApiKey' in spec.auth_scheme
        assert 'OAuth2' in spec.auth_scheme
        text = spec.to_lap()
        parsed = parse_lap(text)
        assert 'Bearer' in parsed.auth_scheme
        assert 'ApiKey' in parsed.auth_scheme
        assert 'OAuth2' in parsed.auth_scheme

    def test_multi_auth_errors_preserved(self):
        spec = compile_openapi(str(FIXTURES_DIR / 'multi_auth.yaml'))
        ep = spec.endpoints[0]
        error_codes = {e.code for e in ep.error_schemas}
        assert '401' in error_codes
        assert '403' in error_codes


# ═══════════════════════════════════════════════════════════════════
# 3. CLI Integration Tests (subprocess)
# ═══════════════════════════════════════════════════════════════════

class TestCLICompile:
    def test_compile_stdout(self):
        result = subprocess.run(
            [sys.executable, CLI, 'compile', str(SPECS_DIR / 'stripe-charges.yaml')],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        assert '@lap' in result.stdout
        assert '@api' in result.stdout
        assert '@endpoint' in result.stdout

    def test_compile_lean(self):
        result = subprocess.run(
            [sys.executable, CLI, 'compile', '--lean', str(SPECS_DIR / 'stripe-charges.yaml')],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        assert '@desc' not in result.stdout

    def test_compile_to_file(self, tmp_path):
        out = tmp_path / 'test.lap'
        result = subprocess.run(
            [sys.executable, CLI, 'compile', str(SPECS_DIR / 'stripe-charges.yaml'), '-o', str(out)],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        assert out.exists()
        content = out.read_text()
        assert '@lap' in content


class TestCLIValidate:
    def test_validate_passes(self):
        result = subprocess.run(
            [sys.executable, CLI, 'validate', str(SPECS_DIR / 'stripe-charges.yaml')],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        output = result.stdout.lower()
        assert 'pass' in output or 'endpoint' in output or '100%' in output


class TestCLIBenchmark:
    def test_benchmark_produces_numbers(self):
        result = subprocess.run(
            [sys.executable, CLI, 'benchmark', str(SPECS_DIR / 'stripe-charges.yaml')],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        import re
        numbers = re.findall(r'\d{2,}', result.stdout)
        assert len(numbers) > 0, 'Benchmark should produce numeric output'


class TestCLIInspect:
    def _ensure_lap(self):
        lap_file = OUTPUT_DIR / 'stripe-charges.lap'
        if not lap_file.exists():
            subprocess.run(
                [sys.executable, CLI, 'compile', str(SPECS_DIR / 'stripe-charges.yaml'),
                 '-o', str(lap_file)],
                capture_output=True, text=True, cwd=str(PROJECT_DIR)
            )
        return lap_file

    def test_inspect_all(self):
        f = self._ensure_lap()
        result = subprocess.run(
            [sys.executable, CLI, 'inspect', str(f)],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        assert 'Stripe' in result.stdout or 'stripe' in result.stdout.lower()

    def test_inspect_with_endpoint_filter(self):
        f = self._ensure_lap()
        result = subprocess.run(
            [sys.executable, CLI, 'inspect', str(f), '--endpoint', 'POST /v1/charges'],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        assert '/v1/charges' in result.stdout


class TestCLIConvert:
    def _ensure_lap(self):
        lap_file = OUTPUT_DIR / 'stripe-charges.lap'
        if not lap_file.exists():
            subprocess.run(
                [sys.executable, CLI, 'compile', str(SPECS_DIR / 'stripe-charges.yaml'),
                 '-o', str(lap_file)],
                capture_output=True, text=True, cwd=str(PROJECT_DIR)
            )
        return lap_file

    def test_convert_stdout(self):
        f = self._ensure_lap()
        result = subprocess.run(
            [sys.executable, CLI, 'convert', str(f)],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        parsed = yaml.safe_load(result.stdout)
        assert 'openapi' in parsed
        assert 'paths' in parsed

    def test_convert_to_file(self, tmp_path):
        f = self._ensure_lap()
        out = tmp_path / 'output.yaml'
        result = subprocess.run(
            [sys.executable, CLI, 'convert', str(f), '-o', str(out)],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        assert result.returncode == 0
        assert out.exists()
        parsed = yaml.safe_load(out.read_text())
        assert 'paths' in parsed


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
