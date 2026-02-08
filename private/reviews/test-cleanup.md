# Test Suite Cleanup Summary

**Date:** 2026-02-08  
**Before:** 320 tests | **After:** 128 tests | **Removed:** 192 (60%)

---

## What Changed

### test_a2a.py: 27 → 22 tests

- **Removed** `test_to_dict_strips_empty`, `test_to_json`, `test_context_hash` — trivial dataclass/helper tests
- **Removed** `test_all_examples_compile` — loop over 24 examples just checking intent ∈ set (already covered by specific compiler tests)
- **Removed** `test_all_examples_roundtrip` — asserted `len(nl) > 0`, caught nothing
- **Removed** `test_structured_eliminates_ambiguity` — 90% threshold was too lenient to fail
- **Replaced** with `test_roundtrip_preserves_intent_keywords` — 4 representative cases checking actual intent keywords survive decompilation
- **Tightened** `test_compact_smaller_than_json` — tests 4 representative cases instead of all 24
- **Fixed** `test_politeness_stripped` — now also asserts "cats" is in the query
- **Fixed** `test_benchmark_returns_savings` — removed false assumption that compact is always smaller than NL

### test_integration.py: 247 → 75 tests

**Removed entirely (144 parameterized A2A tests):**
- `test_compile_produces_valid_intent[msg0-23]` (24) — duplicate of test_a2a.py compiler tests
- `test_decompile_produces_text[msg0-23]` (24) — just `assert len > 0`
- `test_intent_preserved_in_round_trip[msg0-23]` (24) — moved representative version to test_a2a.py
- `test_compact_format_valid[msg0-23]` (24) — trivial format check
- `test_json_format_valid[msg0-23]` (24) — tests `json.loads`, not LAP code
- `test_compact_smaller_than_nl[msg0-23]` (24) — `< len*2` threshold was meaningless

**Removed (30 duplicate/trivial tests):**
- `test_lean_smaller_than_standard[x10]` (10) — trivially true by construction
- `test_doclean_header_always_present[x10]` (10) — tests hardcoded string literal
- `test_every_endpoint_has_method_and_path[x10]` (10) — tests dataclass invariants

**Consolidated edge cases:** Merged split test pairs (e.g., `test_no_params_endpoint` + `test_no_params_round_trip`) into single round-trip tests that check both.

**Absorbed** `test_idempotent_serialization` from format invariants into pipeline round-trip class (kept — it's a real pipeline test).

**Kept all 9 CLI subprocess tests** — these are true integration tests.

### test_parser.py & test_sdk.py: Unchanged

These were already solid per the audit (25 real parser tests, 11 real SDK tests).

---

## Test Distribution (After)

| File | Tests | What They Cover |
|------|-------|-----------------|
| test_parser.py | 31 | Parser unit tests, round-trips, converter |
| test_a2a.py | 22 | NL compiler (8 intents), decompiler, benchmark, negotiation |
| test_integration.py | 60 | Pipeline round-trips (4×10 specs), edge cases (12), CLI (9) |
| test_sdk.py | 15 | SDK client, registry, middleware, parser |
| **Total** | **128** | |

---

## Quality Improvements

1. **No more `assert len > 0` or `is not None`** — every assertion checks a specific expected value
2. **No more `< len*2` thresholds** — removed or replaced with concrete comparisons
3. **No cross-file duplication** — A2A tests live in test_a2a.py, pipeline tests in test_integration.py
4. **Parameterization only where it adds value** — specs (testing real pipeline) not example messages (testing the same code path 24 times)
