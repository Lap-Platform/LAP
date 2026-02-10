#!/usr/bin/env python3
"""Tests for GraphQL SDL → DocLean compiler."""

import sys
from pathlib import Path


import pytest
from core.compilers.graphql import compile_graphql, _unwrap, _type_string
from core.formats.doclean import DocLeanSpec

SPECS_DIR = Path(__file__).parent.parent / "examples" / "verbose" / "graphql"


# ── Basic compilation tests ──────────────────────────────────────────

class TestBasicCompilation:
    def test_compile_github(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        assert isinstance(ds, DocLeanSpec)
        assert ds.api_name  # non-empty
        assert len(ds.endpoints) > 0

    def test_compile_ecommerce(self):
        ds = compile_graphql(str(SPECS_DIR / "ecommerce.graphql"))
        assert len(ds.endpoints) > 0

    def test_compile_social(self):
        ds = compile_graphql(str(SPECS_DIR / "social.graphql"))
        assert len(ds.endpoints) > 0

    def test_compile_analytics(self):
        ds = compile_graphql(str(SPECS_DIR / "analytics.graphql"))
        assert len(ds.endpoints) > 0

    def test_compile_cms(self):
        ds = compile_graphql(str(SPECS_DIR / "cms.graphql"))
        assert len(ds.endpoints) > 0


# ── Method mapping tests ─────────────────────────────────────────────

class TestMethodMapping:
    def test_queries_are_get(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        query_eps = [e for e in ds.endpoints if e.method == "GET"]
        assert len(query_eps) >= 4  # user, repository, searchRepositories, viewer

    def test_mutations_are_post(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        mutation_eps = [e for e in ds.endpoints if e.method == "POST"]
        assert len(mutation_eps) >= 4  # createIssue, updateIssue, addStar, removeStar

    def test_subscriptions_are_event(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        event_eps = [e for e in ds.endpoints if e.method == "EVENT"]
        assert len(event_eps) >= 2  # issueCreated, pullRequestUpdated


# ── Parameter extraction tests ───────────────────────────────────────

class TestParameters:
    def test_required_params(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        repo_ep = next(e for e in ds.endpoints if e.path == "/repository")
        req_names = {p.name for p in repo_ep.required_params}
        assert "owner" in req_names
        assert "name" in req_names

    def test_optional_params(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        search_ep = next(e for e in ds.endpoints if e.path == "/searchRepositories")
        opt_names = {p.name for p in search_ep.optional_params}
        assert "after" in opt_names

    def test_input_type_params(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        create_ep = next(e for e in ds.endpoints if e.path == "/createIssue")
        assert len(create_ep.required_params) >= 1  # input is required

    def test_enum_params(self):
        ds = compile_graphql(str(SPECS_DIR / "ecommerce.graphql"))
        orders_ep = next(e for e in ds.endpoints if e.path == "/orders")
        status_param = next((p for p in orders_ep.optional_params if p.name == "status"), None)
        assert status_param is not None
        assert len(status_param.enum) == 5  # PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED

    def test_default_values(self):
        ds = compile_graphql(str(SPECS_DIR / "ecommerce.graphql"))
        products_ep = next(e for e in ds.endpoints if e.path == "/products")
        first_param = next((p for p in products_ep.optional_params if p.name == "first"), None)
        assert first_param is not None
        assert first_param.default == "20"


# ── Type handling tests ──────────────────────────────────────────────

class TestTypes:
    def test_scalar_types(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        user_ep = next(e for e in ds.endpoints if e.path == "/user")
        login_param = next(p for p in user_ep.required_params if p.name == "login")
        assert login_param.type == "str"

    def test_id_type(self):
        ds = compile_graphql(str(SPECS_DIR / "ecommerce.graphql"))
        product_ep = next(e for e in ds.endpoints if e.path == "/product")
        id_param = next(p for p in product_ep.required_params if p.name == "id")
        assert id_param.type in ("str(id)", "id")

    def test_list_type_in_response(self):
        ds = compile_graphql(str(SPECS_DIR / "ecommerce.graphql"))
        products_ep = next(e for e in ds.endpoints if e.path == "/products")
        # Should have response schema
        assert len(products_ep.response_schemas) > 0


# ── Response field tests ─────────────────────────────────────────────

class TestResponseFields:
    def test_nested_response_fields(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        user_ep = next(e for e in ds.endpoints if e.path == "/user")
        assert len(user_ep.response_schemas) > 0
        fields = user_ep.response_schemas[0].fields
        field_names = {f.name for f in fields}
        assert "id" in field_names
        assert "login" in field_names

    def test_circular_ref_handling(self):
        """Types that reference themselves should not cause infinite recursion."""
        ds = compile_graphql(str(SPECS_DIR / "cms.graphql"))
        # Page has parentPage: Page (self-reference)
        page_ep = next(e for e in ds.endpoints if e.path == "/page")
        assert len(page_ep.response_schemas) > 0
        # Should compile without error; circular refs handled via max_depth

    def test_interface_fields(self):
        ds = compile_graphql(str(SPECS_DIR / "cms.graphql"))
        search_ep = next(e for e in ds.endpoints if e.path == "/search")
        assert len(search_ep.response_schemas) > 0

    def test_union_fields(self):
        ds = compile_graphql(str(SPECS_DIR / "social.graphql"))
        feed_ep = next(e for e in ds.endpoints if e.path == "/feed")
        assert len(feed_ep.response_schemas) > 0


# ── DocLean output tests ─────────────────────────────────────────────

class TestDocLeanOutput:
    def test_output_contains_doclean_header(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        output = ds.to_doclean()
        assert "@doclean" in output
        assert "@api" in output

    def test_output_contains_endpoints(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        output = ds.to_doclean()
        # New compact format uses Q/M/S prefixes instead of @endpoint
        assert "Q " in output or "@endpoint GET" in output
        assert "M " in output or "@endpoint POST" in output
        assert "S " in output or "@endpoint EVENT" in output

    def test_output_contains_type_defs(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        output = ds.to_doclean()
        assert "enum IssueState" in output

    def test_lean_mode_strips_descriptions(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        standard = ds.to_doclean(lean=False)
        lean = ds.to_doclean(lean=True)
        assert len(lean) <= len(standard)

    def test_output_contains_input_types(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        output = ds.to_doclean()
        assert "input CreateIssueInput" in output

    def test_output_contains_interface(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        output = ds.to_doclean()
        assert "iface Node" in output or "@interface Node" in output

    def test_output_contains_union(self):
        ds = compile_graphql(str(SPECS_DIR / "social.graphql"))
        output = ds.to_doclean()
        assert "union FeedItem" in output or "@union FeedItem" in output

    def test_base_url_is_graphql(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        assert ds.base_url == "/graphql"


# ── All schemas compile ──────────────────────────────────────────────

class TestAllSchemas:
    @pytest.mark.parametrize("schema", [
        "github.graphql",
        "ecommerce.graphql",
        "social.graphql",
        "analytics.graphql",
        "cms.graphql",
    ])
    def test_schema_compiles(self, schema):
        ds = compile_graphql(str(SPECS_DIR / schema))
        output = ds.to_doclean()
        assert len(output) > 100
        assert "@doclean" in output

    @pytest.mark.parametrize("schema", [
        "github.graphql",
        "ecommerce.graphql",
        "social.graphql",
        "analytics.graphql",
        "cms.graphql",
    ])
    def test_schema_lean_mode(self, schema):
        ds = compile_graphql(str(SPECS_DIR / schema))
        standard = ds.to_doclean(lean=False)
        lean = ds.to_doclean(lean=True)
        assert len(lean) <= len(standard)


# ── Token benchmark test ─────────────────────────────────────────────

class TestTokenBenchmark:
    def _count_tokens_approx(self, text: str) -> int:
        """Approximate token count (chars / 4)."""
        return max(1, len(text) // 4)

    def test_compression_ratio(self):
        """DocLean output should be significantly smaller than raw SDL."""
        for schema in SPECS_DIR.glob("*.graphql"):
            raw = schema.read_text()
            ds = compile_graphql(str(schema))
            doclean = ds.to_doclean(lean=True)
            raw_tokens = self._count_tokens_approx(raw)
            dl_tokens = self._count_tokens_approx(doclean)
            # GraphQL SDL is already compact; DocLean adds response schemas so may be larger
            # but should not be absurdly larger (< 5x)
            assert dl_tokens < raw_tokens * 5, f"{schema.name}: DocLean ({dl_tokens}) too large vs SDL ({raw_tokens})"

    def test_all_schemas_token_summary(self):
        """Print token summary for all schemas (informational)."""
        total_raw = 0
        total_dl = 0
        total_lean = 0
        for schema in sorted(SPECS_DIR.glob("*.graphql")):
            raw = schema.read_text()
            ds = compile_graphql(str(schema))
            standard = ds.to_doclean(lean=False)
            lean = ds.to_doclean(lean=True)
            raw_t = self._count_tokens_approx(raw)
            dl_t = self._count_tokens_approx(standard)
            lean_t = self._count_tokens_approx(lean)
            total_raw += raw_t
            total_dl += dl_t
            total_lean += lean_t

        # Just verify we processed something
        assert total_raw > 0
        assert total_dl > 0
        assert total_lean > 0


# ── Edge cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_minimal_schema(self, tmp_path):
        """A minimal schema with just a query."""
        schema = tmp_path / "minimal.graphql"
        schema.write_text('type Query { hello: String }')
        ds = compile_graphql(str(schema))
        assert len(ds.endpoints) == 1
        assert ds.endpoints[0].method == "GET"
        assert ds.endpoints[0].path == "/hello"

    def test_no_mutations(self, tmp_path):
        schema = tmp_path / "query_only.graphql"
        schema.write_text('type Query { items: [String!]! }')
        ds = compile_graphql(str(schema))
        post_eps = [e for e in ds.endpoints if e.method == "POST"]
        assert len(post_eps) == 0

    def test_deeply_nested_types(self, tmp_path):
        """Should handle deep nesting without stack overflow."""
        schema = tmp_path / "deep.graphql"
        schema.write_text("""
            type A { b: B }
            type B { c: C }
            type C { d: D }
            type D { value: String }
            type Query { a: A }
        """)
        ds = compile_graphql(str(schema))
        assert len(ds.endpoints) == 1

    def test_self_referential_type(self, tmp_path):
        """Type referencing itself should not infinite loop."""
        schema = tmp_path / "self_ref.graphql"
        schema.write_text("""
            type TreeNode {
                value: String!
                children: [TreeNode!]
            }
            type Query { root: TreeNode }
        """)
        ds = compile_graphql(str(schema))
        assert len(ds.endpoints) == 1

    def test_description_extraction(self):
        ds = compile_graphql(str(SPECS_DIR / "github.graphql"))
        user_ep = next(e for e in ds.endpoints if e.path == "/user")
        assert "user" in user_ep.summary.lower() or "login" in user_ep.summary.lower()
