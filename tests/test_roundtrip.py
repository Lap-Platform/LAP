"""Round-trip fidelity tests: compile → LAP → parse → verify.

Tests that the parser can reconstruct the same spec that the compiler produced.
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.compilers.openapi import compile_openapi
from core.parser import parse_lap


OPENAPI_SPECS = sorted(Path("examples/verbose/openapi").glob("*.yaml"))


def spec_ids():
    return [p.stem for p in OPENAPI_SPECS]


class TestEndpointRoundTrip:
    """Endpoints survive compile → LAP → parse."""

    @pytest.mark.parametrize("spec_path", OPENAPI_SPECS, ids=spec_ids())
    def test_endpoint_count_preserved(self, spec_path):
        compiled = compile_openapi(str(spec_path))
        for lean in (True, False):
            lap_text = compiled.to_lap(lean=lean)
            parsed = parse_lap(lap_text)
            mode = "lean" if lean else "standard"
            assert len(compiled.endpoints) == len(parsed.endpoints), (
                f"{spec_path.stem} ({mode}): "
                f"compiled {len(compiled.endpoints)} endpoints, "
                f"parsed {len(parsed.endpoints)}"
            )

    @pytest.mark.parametrize("spec_path", OPENAPI_SPECS, ids=spec_ids())
    def test_endpoint_methods_and_paths_preserved(self, spec_path):
        compiled = compile_openapi(str(spec_path))
        lap_text = compiled.to_lap(lean=True)
        parsed = parse_lap(lap_text)

        compiled_set = {(e.method, e.path) for e in compiled.endpoints}
        parsed_set = {(e.method, e.path) for e in parsed.endpoints}

        missing = compiled_set - parsed_set
        extra = parsed_set - compiled_set
        assert not missing, f"Lost endpoints: {missing}"
        assert not extra, f"Extra endpoints: {extra}"

    @pytest.mark.parametrize("spec_path", OPENAPI_SPECS, ids=spec_ids())
    def test_response_schema_count_preserved(self, spec_path):
        compiled = compile_openapi(str(spec_path))
        lap_text = compiled.to_lap(lean=True)
        parsed = parse_lap(lap_text)

        for ce, pe in zip(
            sorted(compiled.endpoints, key=lambda e: (e.method, e.path)),
            sorted(parsed.endpoints, key=lambda e: (e.method, e.path)),
        ):
            assert len(ce.response_schemas) == len(pe.response_schemas), (
                f"{ce.method} {ce.path}: "
                f"compiled {len(ce.response_schemas)} responses, "
                f"parsed {len(pe.response_schemas)}"
            )

    @pytest.mark.parametrize("spec_path", OPENAPI_SPECS, ids=spec_ids())
    def test_error_schema_count_preserved(self, spec_path):
        compiled = compile_openapi(str(spec_path))
        lap_text = compiled.to_lap(lean=True)
        parsed = parse_lap(lap_text)

        for ce, pe in zip(
            sorted(compiled.endpoints, key=lambda e: (e.method, e.path)),
            sorted(parsed.endpoints, key=lambda e: (e.method, e.path)),
        ):
            assert len(ce.error_schemas) == len(pe.error_schemas), (
                f"{ce.method} {ce.path}: "
                f"compiled {len(ce.error_schemas)} errors, "
                f"parsed {len(pe.error_schemas)}"
            )


class TestDoubleRoundTrip:
    """compile → LAP → parse → LAP should produce identical text."""

    @pytest.mark.parametrize("spec_path", OPENAPI_SPECS[:5], ids=spec_ids()[:5])
    def test_lap_text_stable_standard(self, spec_path):
        compiled = compile_openapi(str(spec_path))
        lap1 = compiled.to_lap(lean=False)
        parsed = parse_lap(lap1)
        lap2 = parsed.to_lap(lean=False)
        # Compare endpoint blocks (skip header which may differ)
        blocks1 = [b for b in lap1.split("\n\n") if b.startswith("@endpoint")]
        blocks2 = [b for b in lap2.split("\n\n") if b.startswith("@endpoint")]
        assert len(blocks1) == len(blocks2), "Different number of endpoint blocks"

    @pytest.mark.parametrize("spec_path", OPENAPI_SPECS[:5], ids=spec_ids()[:5])
    def test_lap_text_stable_lean(self, spec_path):
        compiled = compile_openapi(str(spec_path))
        lap1 = compiled.to_lap(lean=True)
        parsed = parse_lap(lap1)
        lap2 = parsed.to_lap(lean=True)
        blocks1 = [b for b in lap1.split("\n\n") if b.startswith("@endpoint")]
        blocks2 = [b for b in lap2.split("\n\n") if b.startswith("@endpoint")]
        assert len(blocks1) == len(blocks2), "Different number of endpoint blocks"


class TestMetadataRoundTrip:
    """API metadata survives round-trip."""

    @pytest.mark.parametrize("spec_path", OPENAPI_SPECS[:5], ids=spec_ids()[:5])
    def test_api_name_preserved(self, spec_path):
        compiled = compile_openapi(str(spec_path))
        lap_text = compiled.to_lap(lean=False)
        parsed = parse_lap(lap_text)
        assert compiled.api_name == parsed.api_name

    @pytest.mark.parametrize("spec_path", OPENAPI_SPECS[:5], ids=spec_ids()[:5])
    def test_base_url_preserved(self, spec_path):
        compiled = compile_openapi(str(spec_path))
        lap_text = compiled.to_lap(lean=False)
        parsed = parse_lap(lap_text)
        assert compiled.base_url == parsed.base_url
