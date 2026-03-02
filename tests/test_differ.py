#!/usr/bin/env python3
"""Tests for the DocLean schema diff engine."""

import sys
from pathlib import Path


import pytest
from core.formats.doclean import (
    DocLeanSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema,
)
from core.differ import diff_specs, check_compatibility, generate_changelog, Change


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_spec_v1() -> DocLeanSpec:
    return DocLeanSpec(
        api_name="TestAPI", base_url="https://api.test.com", version="1.0.0",
        endpoints=[
            Endpoint(
                method="post", path="/v1/charges",
                summary="Create a charge",
                required_params=[Param("amount", "int", required=True)],
                optional_params=[Param("currency", "str")],
                request_body=[],
                response_schemas=[
                    ResponseSchema("200", "Success", fields=[
                        ResponseField("id", "str"),
                        ResponseField("status", "str"),
                    ]),
                ],
                error_schemas=[
                    ErrorSchema("400", "invalid_request"),
                    ErrorSchema("402", "card_declined"),
                ],
            ),
            Endpoint(
                method="delete", path="/v1/charges/{id}",
                summary="Delete a charge",
                required_params=[Param("id", "str", required=True)],
                optional_params=[], request_body=[],
                response_schemas=[], error_schemas=[],
            ),
            Endpoint(
                method="get", path="/v1/charges",
                summary="List charges",
                required_params=[], optional_params=[Param("limit", "int")],
                request_body=[], response_schemas=[], error_schemas=[],
            ),
        ],
    )


def _make_spec_v2() -> DocLeanSpec:
    return DocLeanSpec(
        api_name="TestAPI", base_url="https://api.test.com", version="2.0.0",
        endpoints=[
            Endpoint(
                method="post", path="/v1/charges",
                summary="Create a charge (v2)",
                required_params=[
                    Param("amount", "int", required=True),
                    Param("idempotency_key", "str", required=True),  # NEW required → breaking
                ],
                optional_params=[
                    Param("currency", "str"),
                    Param("metadata_v2", "map"),  # NEW optional → non-breaking
                ],
                request_body=[],
                response_schemas=[
                    ResponseSchema("200", "Success", fields=[
                        ResponseField("id", "str"),
                        # "status" removed → breaking
                        ResponseField("created_at", "int"),  # NEW field → non-breaking
                    ]),
                ],
                error_schemas=[
                    ErrorSchema("400", "invalid_request"),
                    # 402 removed → breaking
                    ErrorSchema("429", "rate_limit"),  # NEW → non-breaking
                ],
            ),
            # DELETE /v1/charges/{id} removed → breaking
            Endpoint(
                method="get", path="/v1/charges",
                summary="List charges",
                required_params=[], optional_params=[Param("limit", "str")],  # type changed int→str → breaking
                request_body=[], response_schemas=[], error_schemas=[],
            ),
            # NEW endpoint → non-breaking
            Endpoint(
                method="post", path="/v1/charges/{id}/refund",
                summary="Refund a charge",
                required_params=[], optional_params=[], request_body=[],
                response_schemas=[], error_schemas=[],
            ),
        ],
    )


# ── Tests ────────────────────────────────────────────────────────────

class TestDiffSpecs:
    def test_added_endpoints(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        assert "POST /v1/charges/{id}/refund" in diff.added_endpoints

    def test_removed_endpoints(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        assert "DELETE /v1/charges/{id}" in diff.removed_endpoints

    def test_added_required_param_is_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "param_added" and "idempotency_key" in c.detail]
        assert len(matches) == 1
        assert matches[0].breaking is True

    def test_added_optional_param_not_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "param_added" and "metadata_v2" in c.detail]
        assert len(matches) == 1
        assert matches[0].breaking is False

    def test_param_type_changed_is_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "param_type_changed" and "limit" in c.detail]
        assert len(matches) == 1
        assert matches[0].breaking is True

    def test_response_field_removed_is_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "response_field_removed" and "status" in c.detail]
        assert len(matches) == 1
        assert matches[0].breaking is True

    def test_response_field_added_not_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "response_field_added" and "created_at" in c.detail]
        assert len(matches) == 1
        assert matches[0].breaking is False

    def test_error_removed_is_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "error_removed" and "402" in c.detail]
        assert len(matches) == 1
        assert matches[0].breaking is True

    def test_error_added_not_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "error_added" and "429" in c.detail]
        assert len(matches) == 1
        assert matches[0].breaking is False

    def test_description_changed_not_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "description_changed"]
        assert len(matches) >= 1
        assert all(not c.breaking for c in matches)

    def test_endpoint_removed_is_breaking(self):
        diff = diff_specs(_make_spec_v1(), _make_spec_v2())
        matches = [c for c in diff.changes if c.category == "endpoint_removed"]
        assert len(matches) == 1
        assert matches[0].breaking is True

    def test_no_changes_for_identical_specs(self):
        spec = _make_spec_v1()
        diff = diff_specs(spec, spec)
        assert len(diff.changes) == 0
        assert len(diff.added_endpoints) == 0
        assert len(diff.removed_endpoints) == 0


class TestCompatibility:
    def test_breaking_changes_major(self):
        result = check_compatibility(_make_spec_v1(), _make_spec_v2())
        assert result.compatible is False
        assert result.severity == "MAJOR"
        assert len(result.breaking_changes) > 0

    def test_identical_is_compatible(self):
        spec = _make_spec_v1()
        result = check_compatibility(spec, spec)
        assert result.compatible is True
        assert result.severity == "PATCH"

    def test_minor_change(self):
        """Adding only an optional param → MINOR."""
        old = DocLeanSpec(api_name="T", endpoints=[
            Endpoint(method="get", path="/x", required_params=[], optional_params=[],
                     request_body=[], response_schemas=[], error_schemas=[]),
        ])
        new = DocLeanSpec(api_name="T", endpoints=[
            Endpoint(method="get", path="/x", required_params=[],
                     optional_params=[Param("foo", "str")],
                     request_body=[], response_schemas=[], error_schemas=[]),
        ])
        result = check_compatibility(old, new)
        assert result.compatible is True
        assert result.severity == "MINOR"


class TestChangelog:
    def test_changelog_format(self):
        cl = generate_changelog(_make_spec_v1(), _make_spec_v2(), version="2.0.0")
        assert cl.startswith("## v2.0.0")
        assert "### Breaking Changes" in cl
        assert "### New Features" in cl

    def test_changelog_contains_breaking_details(self):
        cl = generate_changelog(_make_spec_v1(), _make_spec_v2(), version="2.0.0")
        assert "idempotency_key" in cl
        assert "DELETE /v1/charges/{id}" in cl

    def test_changelog_contains_non_breaking(self):
        cl = generate_changelog(_make_spec_v1(), _make_spec_v2(), version="2.0.0")
        assert "metadata_v2" in cl
        assert "refund" in cl.lower()

    def test_no_changes_changelog(self):
        spec = _make_spec_v1()
        cl = generate_changelog(spec, spec, version="1.0.1")
        assert "No changes detected" in cl


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
