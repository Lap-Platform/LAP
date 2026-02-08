# Security Fixes Summary

**Date:** 2026-02-08
**All 320 tests passing after changes.**

## HIGH-2: Circular $ref and unbounded processing

### `src/compiler.py`
- **`resolve_ref()`**: Added `_visited` set parameter for cycle detection. Raises `ValueError` on circular `$ref` references. Also follows transitive `$ref` chains with the same visited set.
- **`extract_response_fields()`**: Added `max_properties=500` limit. Stops processing properties after 500 fields to prevent unbounded iteration on large schemas.

### `src/parser.py`
- **Brace-joining loop**: Added 100KB max line length check. Raises `ValueError` if a joined line exceeds the limit, preventing memory exhaustion from malicious input with deeply nested unclosed braces.

## MEDIUM-1: `__import__()` usage

### `src/converter.py`
- Replaced two instances of `__import__('re').match(...)` with proper `import re` at module top level and direct `re.match(...)` calls. Eliminates dynamic import pattern flagged as a security concern.

## MEDIUM-2: YAML type validation

### `src/compiler.py`
- After `yaml.safe_load()` / `json.loads()` in `compile_openapi()`, added: `if not isinstance(spec, dict): raise ValueError("Invalid OpenAPI spec: expected a YAML mapping")`

### `benchmarks/validate.py`
- Same type check added after loading the spec in `validate_schema_completeness()`.

### `benchmarks/benchmark.py`
- No direct YAML loading — uses `compile_openapi()` which now includes the check.

## MEDIUM-3: API key leakage

### `benchmarks/agent_test.py`
- Removed `--api-key` CLI argument entirely.
- Now reads API key exclusively from `OPENAI_API_KEY` environment variable.
- Updated dry-run detection and all call sites to use the env var.

## LOW-2: Input size limits

### `src/compiler.py`
- Added 50MB file size check before reading OpenAPI specs. Raises `ValueError` if exceeded.

### `src/converter.py`
- Added 10MB file size check before reading DocLean files. Raises `ValueError` if exceeded.
