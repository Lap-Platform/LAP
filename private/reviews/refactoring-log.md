# LAP Refactoring Log

**Date:** 2026-02-08  
**Scope:** Top 5 structural issues from code-review.md  
**Result:** All 320 tests passing ✅

---

## 1. Eliminated Duplicate Parser in SDK

**Before:** `sdk/python/lap/client.py` had its own `_parse_lap()`, `_parse_params()`, `_parse_returns()`, and `_parse_errors()` — a naive reimplementation that broke on blank lines within endpoints and couldn't handle multi-line braced content.

**After:** Removed all duplicate parsing functions from the SDK client. `client.py` now imports `parse_lap` from `src/parser.py` directly. The SDK test (`test_sdk.py`) was updated to import `parse_lap` from the canonical source.

**Files changed:** `sdk/python/lap/client.py`, `sdk/python/tests/test_sdk.py`

---

## 2. Extracted Shared Utilities → `src/utils.py`

**Before:** `count_tokens()` was duplicated 5 times (benchmark.py, benchmark_all.py, report.py, agent_test.py, a2a_lean.py) with slight variations. `MODEL_COSTS` was duplicated 3 times with inconsistent entries.

**After:** Created `src/utils.py` with:
- `count_tokens(text, model)` — cached tiktoken encoding, graceful fallback
- `MODEL_COSTS` — single authoritative dict with all 5 models
- `read_file_safe(path, max_size)` — safe file reading with size limits
- `get_tiktoken_encoding(model)` — cached singleton pattern (fixes the "encoding created per call" perf issue)

Updated all consumers: `benchmarks/benchmark.py`, `benchmarks/benchmark_all.py`, `benchmarks/report.py`, `benchmarks/agent_test.py`, `demo.py`, `sdk/python/lap/client.py`

**Files changed:** New `src/utils.py`; 6 files updated to import from it

---

## 3. Added Error Handling to Parser

**Before:** Parser silently produced garbage on malformed input. No line numbers, no warnings, no validation. `_looks_like_field_start` redundantly imported `re` inside the function.

**After:**
- Added `ParseError` exception class with `line_number` and `context` attributes
- Parser raises `ParseError` for structural issues (line length exceeded during brace joining)
- Issues `warnings.warn()` for recoverable problems (malformed fields/params → defaults to type 'any')
- Unmatched braces in `_extract_braced` now emit a warning instead of silently returning partial content
- Pre-compiled regex pattern `_FIELD_START_RE` (was recompiled every call in hot path)
- Removed redundant `import re` inside `_looks_like_field_start`
- Generic exception handler wraps each directive's parsing with context

**Files changed:** `src/parser.py`

---

## 4. Fixed Package Structure (sys.path)

**Before:** No `__init__.py` in `src/`, no package structure. Every file had its own `sys.path.insert(0, ...)`.

**After:** Added `src/__init__.py` to make `src/` a proper Python package. The `sys.path.insert` calls in consumer files remain for now (they're needed since there's no `pyproject.toml` editable install yet), but having `__init__.py` makes the imports cleaner and enables future packaging.

**Note:** Full `pyproject.toml` + editable install was deemed out of scope for this refactoring pass since it would require restructuring directories (e.g., `src/` → `lap_core/`) and updating all imports project-wide. The `__init__.py` is the minimal viable step.

**Files changed:** New `src/__init__.py`

---

## 5. Deduplicated CLI Convert Logic

**Before:** `cli.py`'s `cmd_convert()` had ~80 lines of hand-rolled OpenAPI generation (using version "3.0.3") that duplicated `converter.py`'s `lap_to_openapi()` (version "3.0.0"). Different logic, different OpenAPI versions, different behavior.

**After:** `cmd_convert()` is now a 10-line thin wrapper that calls `converter.convert_file()`. Also removed the standalone `_lap_type_to_openapi()` helper that was only used by the old duplicate code. CLI `cmd_benchmark_all` also updated to use `utils.count_tokens` instead of inline tiktoken.

**Files changed:** `cli.py`

---

## Test Results

```
320 passed in 5.45s
```

All existing tests pass with zero modifications to test assertions. The only test file change was `sdk/python/tests/test_sdk.py` where `_parse_lap` import was redirected to the canonical parser.
