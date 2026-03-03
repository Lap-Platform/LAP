"""Regression tests for compiler quality bug fixes (v0.3.1)."""

import pytest
from pathlib import Path

import yaml

from lap.core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema
from lap.core.compilers.openapi import compile_openapi, _infer_auth_from_description
from lap.core.compilers.skill import generate_skill, SkillOptions
from lap.core.yaml_compat import _SafeLoaderCompat

EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "verbose" / "openapi"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =====================================================================
# Bug #1: Swagger 2.0 securityDefinitions should be recognized
# =====================================================================

class TestSwagger2Auth:
    """Bug #1: Swagger 2.0 securityDefinitions should be recognized."""

    def test_netlify_has_auth(self):
        spec = compile_openapi(str(EXAMPLES_DIR / "netlify.yaml"))
        assert spec.auth_scheme, "Netlify (Swagger 2.0) should have auth detected"

    def test_swagger2_base_url(self):
        spec = compile_openapi(str(EXAMPLES_DIR / "netlify.yaml"))
        assert spec.base_url, "Swagger 2.0 base_url should be extracted from host/basePath"
        assert spec.base_url.startswith("http"), f"base_url should be a URL, got: {spec.base_url}"


# =====================================================================
# Bug #2: Auth mentioned only in info.description should be detected
# =====================================================================

class TestDescriptionAuth:
    """Bug #2: Auth mentioned only in info.description should be detected."""

    def test_notion_has_auth(self):
        spec = compile_openapi(str(EXAMPLES_DIR / "notion.yaml"))
        assert spec.auth_scheme, "Notion (auth in description only) should have auth detected"

    def test_infer_bearer_keyword(self):
        result = _infer_auth_from_description(
            {"info": {"description": "Use a Bearer token for auth."}}
        )
        assert "Bearer" in result

    def test_infer_api_key_keyword(self):
        result = _infer_auth_from_description(
            {"info": {"description": "Supply your API key in the header."}}
        )
        assert "ApiKey" in result

    def test_infer_oauth2_keyword(self):
        result = _infer_auth_from_description(
            {"info": {"description": "This API uses OAuth2 for authorization."}}
        )
        assert "OAuth2" in result

    def test_no_false_positive_weather(self):
        result = _infer_auth_from_description(
            {"info": {"description": "A public API for weather data."}}
        )
        assert result == ""

    def test_no_false_positive_empty_desc(self):
        assert _infer_auth_from_description({"info": {}}) == ""

    def test_no_false_positive_no_info(self):
        assert _infer_auth_from_description({}) == ""


# =====================================================================
# Bug #3: Jira YAML with bare = should parse without error
# =====================================================================

class TestYamlParsing:
    """Bug #3: Jira YAML with bare = should parse without error."""

    @pytest.mark.timeout(120)
    def test_jira_compiles(self):
        jira_path = EXAMPLES_DIR / "jira.yaml"
        if not jira_path.exists():
            pytest.skip("jira.yaml not available")
        spec = compile_openapi(str(jira_path))
        assert len(spec.endpoints) > 0, "Jira should have endpoints"


# =====================================================================
# Bug #4: Skill description should not contain 'API API'
# =====================================================================

class TestApiApiDoubling:
    """Bug #4: Skill description should not contain 'API API'."""

    def test_no_doubling_in_skill(self):
        spec = LAPSpec(
            api_name="Stripe Charges API",
            base_url="https://api.stripe.com",
            version="1.0.0",
            endpoints=[
                Endpoint(method="get", path="/charges", summary="List charges"),
            ],
        )
        result = generate_skill(spec)
        skill_md = result.file_map["SKILL.md"]
        assert "API API" not in skill_md, f"Should not double API in SKILL.md"

    def test_api_suffix_stripped_in_description(self):
        spec = LAPSpec(
            api_name="Stripe Charges API",
            base_url="https://api.stripe.com",
            version="1.0.0",
            endpoints=[
                Endpoint(method="get", path="/charges", summary="List charges"),
            ],
        )
        result = generate_skill(spec)
        skill_md = result.file_map["SKILL.md"]
        # The description should say "Stripe Charges API skill" not "Stripe Charges API API skill"
        assert "Stripe Charges API skill" in skill_md

    def test_no_doubling_single_word_api(self):
        """Edge case: api_name is literally 'API' -- should not produce 'API API'."""
        spec = LAPSpec(
            api_name="API",
            base_url="https://api.example.com",
            version="1.0.0",
            endpoints=[
                Endpoint(method="get", path="/status", summary="Status"),
            ],
        )
        result = generate_skill(spec)
        skill_md = result.file_map["SKILL.md"]
        assert "API API" not in skill_md, f"Should not double 'API' in: {skill_md[:200]}"


# =====================================================================
# Bug #5: Response schemas deeper than 2 levels should be preserved
# =====================================================================

class TestDeepNesting:
    """Bug #5: Response schemas deeper than 2 levels should preserve properties."""

    def test_deep_nested_level3(self):
        spec = compile_openapi(str(FIXTURES_DIR / "deep_nested.yaml"))
        assert len(spec.endpoints) > 0
        ep = spec.endpoints[0]
        assert ep.response_schemas, "Should have response schemas"
        rs = ep.response_schemas[0]

        # Navigate: level1 -> level2 -> level3 and check it has children
        level1 = next((f for f in rs.fields if f.name == "level1"), None)
        assert level1 is not None, "level1 field should exist"
        assert level1.children, "level1 should have children"

        level2 = next((f for f in level1.children if f.name == "level2"), None)
        assert level2 is not None, "level2 field should exist"
        assert level2.children, "level2 should have children"

        level3 = next((f for f in level2.children if f.name == "level3"), None)
        assert level3 is not None, "level3 field should exist"
        assert level3.children, "level3 should have children (was previously lost at depth 2)"

    def test_max_depth_default_is_3(self):
        """The extract_response_fields max_depth should be at least 3."""
        from lap.core.compilers.openapi import extract_response_fields
        import inspect
        sig = inspect.signature(extract_response_fields)
        default_max = sig.parameters["max_depth"].default
        assert default_max >= 3, f"max_depth default should be >= 3, got {default_max}"


# =====================================================================
# Bug #6: YAML boolean values in enums should not become True/False
# =====================================================================

class TestBooleanEnumCorruption:
    """Bug #6: YAML boolean values in enums should not become True/False."""

    def test_yaml_loader_preserves_NO(self):
        data = yaml.load("enum: [US, NO, YES, DK, ON, OFF]", Loader=_SafeLoaderCompat)
        values = data["enum"]
        assert "NO" in values, f"NO should be preserved as string, got: {values}"
        assert "YES" in values, f"YES should be preserved as string, got: {values}"

    def test_yaml_loader_no_booleans(self):
        data = yaml.load("enum: [US, NO, YES, DK, ON, OFF]", Loader=_SafeLoaderCompat)
        values = data["enum"]
        assert not any(isinstance(v, bool) for v in values), \
            f"No booleans should be in enum: {values}"

    def test_yaml_loader_preserves_true_false_strings(self):
        """true/false should still resolve as booleans (YAML 1.2 behavior)."""
        data = yaml.load("values: [true, false]", Loader=_SafeLoaderCompat)
        values = data["values"]
        assert values == [True, False], f"true/false should remain booleans: {values}"

    def test_big_enum_fixture_country_codes(self):
        """big_enum.yaml should preserve NO and DK as country codes."""
        spec = compile_openapi(str(FIXTURES_DIR / "big_enum.yaml"))
        ep = spec.endpoints[0]
        country_param = next(
            p for p in ep.required_params + ep.optional_params if p.name == "country"
        )
        assert "NO" in country_param.enum, f"NO should be string, got: {country_param.enum}"
        assert "DK" in country_param.enum, f"DK should be string, got: {country_param.enum}"
        assert not any(isinstance(v, bool) for v in country_param.enum), \
            f"No booleans in enum: {country_param.enum}"

    def test_enum_rendering_no_capitalized_bools(self):
        """Param.to_lap() should render bools as lowercase true/false."""
        param = Param(name="flag", type="str", enum=[True, False, "maybe"])
        lap_text = param.to_lap()
        assert "True" not in lap_text, f"Should not have capitalized True: {lap_text}"
        assert "False" not in lap_text, f"Should not have capitalized False: {lap_text}"
        assert "true/false/maybe" in lap_text


# =====================================================================
# Bug #7: graphql-core should be importable
# =====================================================================

class TestGraphqlDependency:
    """Bug #7: graphql-core should be importable."""

    def test_graphql_importable(self):
        from lap.core.compilers.graphql import compile_graphql
        assert callable(compile_graphql)


# =====================================================================
# Bug #8: HTTP auth scheme "basic" should produce "Basic", not "Bearer basic"
# =====================================================================

class TestHttpAuthSchemeFormatting:
    """Bug #8: HTTP auth schemes should map correctly."""

    def test_basic_auth_produces_basic(self):
        from lap.core.compilers.openapi import extract_auth
        spec = {
            "components": {
                "securitySchemes": {
                    "basicAuth": {"type": "http", "scheme": "basic"},
                }
            }
        }
        result = extract_auth(spec)
        assert result == "Basic"
        assert "Bearer" not in result

    def test_bearer_auth_produces_bearer(self):
        from lap.core.compilers.openapi import extract_auth
        spec = {
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"},
                }
            }
        }
        result = extract_auth(spec)
        assert result == "Bearer"

    def test_mixed_basic_and_bearer(self):
        from lap.core.compilers.openapi import extract_auth
        spec = {
            "components": {
                "securitySchemes": {
                    "basicAuth": {"type": "http", "scheme": "basic"},
                    "bearerAuth": {"type": "http", "scheme": "bearer"},
                }
            }
        }
        result = extract_auth(spec)
        assert "Basic" in result
        assert "Bearer" in result
        assert "Basic | Bearer" == result

    def test_unknown_http_scheme_capitalized(self):
        from lap.core.compilers.openapi import extract_auth
        spec = {
            "components": {
                "securitySchemes": {
                    "digestAuth": {"type": "http", "scheme": "digest"},
                }
            }
        }
        result = extract_auth(spec)
        assert result == "Digest"


# =====================================================================
# Bug #9: HTML tags in descriptions should be stripped
# =====================================================================

class TestHtmlStripping:
    """Bug #9: HTML tags should be stripped from descriptions."""

    def test_strip_html_helper(self):
        from lap.core.compilers.openapi import _strip_html
        assert _strip_html("<p>Hello</p>") == "Hello"
        assert _strip_html('Click <a href="url">here</a>') == "Click here"
        assert _strip_html("<b>bold</b> and <i>italic</i>") == "bold and italic"
        assert _strip_html("no tags here") == "no tags here"

    def test_param_description_no_html(self):
        from lap.core.compilers.openapi import extract_params
        params = [
            {
                "name": "customer",
                "in": "query",
                "schema": {"type": "string"},
                "description": "<p>The customer's <a href='/docs'>ID</a></p>",
            }
        ]
        required, optional = extract_params(params, {})
        param = (required + optional)[0]
        assert "<" not in param.description
        assert ">" not in param.description
        assert "customer" in param.description.lower() or "ID" in param.description

    def test_response_description_no_html(self):
        from lap.core.compilers.openapi import extract_response_schemas
        responses = {
            "200": {
                "description": "<p>Successful response with <b>data</b></p>",
            }
        }
        resp_schemas, _ = extract_response_schemas(responses, {})
        assert resp_schemas
        assert "<" not in resp_schemas[0].description

    def test_endpoint_summary_no_html(self):
        """Endpoint summary should have HTML stripped."""
        import tempfile, json, os
        spec_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/items": {
                    "get": {
                        "summary": "<p>List all items</p>",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(spec_data, f)
            spec = compile_openapi(tmp_path)
            assert "<" not in spec.endpoints[0].summary
            assert "List all items" in spec.endpoints[0].summary
        finally:
            os.unlink(tmp_path)


# =====================================================================
# Bug #10: Env var should be STRIPE_API_KEY, not STRIPE_API_API_KEY
# =====================================================================

class TestEnvVarDoubleApi:
    """Bug #10: Env var should strip trailing _API before appending _API_KEY."""

    def test_stripe_api_env_var(self):
        spec = LAPSpec(
            api_name="Stripe API",
            base_url="https://api.stripe.com",
            auth_scheme="Bearer",
            endpoints=[Endpoint(method="get", path="/charges", summary="List charges")],
        )
        result = generate_skill(spec, SkillOptions(clawhub=True))
        md = result.file_map["SKILL.md"]
        assert "STRIPE_API_KEY" in md
        assert "STRIPE_API_API_KEY" not in md

    def test_plain_name_no_trailing_api(self):
        """Name without trailing API should work normally."""
        spec = LAPSpec(
            api_name="Acme",
            base_url="https://api.acme.com",
            auth_scheme="Bearer",
            endpoints=[Endpoint(method="get", path="/items", summary="List items")],
        )
        result = generate_skill(spec, SkillOptions(clawhub=True))
        md = result.file_map["SKILL.md"]
        assert "ACME_API_KEY" in md

    def test_bare_api_name(self):
        """api_name='API' should produce API_API_KEY (slug is 'api')."""
        spec = LAPSpec(
            api_name="API",
            base_url="https://api.example.com",
            auth_scheme="Bearer",
            endpoints=[Endpoint(method="get", path="/status", summary="Status")],
        )
        result = generate_skill(spec, SkillOptions(clawhub=True))
        md = result.file_map["SKILL.md"]
        assert "API_API_KEY" in md


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
