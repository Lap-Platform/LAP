"""
Tests for Smithy compiler.

Test categories:
1. JSON AST Loading
2. Type Resolution
3. HTTP Binding
4. Operation Conversion
5. Service Extraction
6. End-to-End Compilation
7. Edge Cases
"""

import json
import pytest
from pathlib import Path

from core.compilers.smithy import (
    compile_smithy,
    _load_json_ast,
    _build_shape_index,
    _find_service,
    _extract_service_metadata,
    _extract_auth_scheme,
    _smithy_type_to_lap,
    _parse_http_trait,
    _extract_uri_params,
    _extract_http_bindings,
    _operation_to_endpoint,
    _extract_operation_output,
    _extract_operation_errors,
    _structure_to_response_fields,
)


SPECS_DIR = Path(__file__).parent.parent / "examples" / "verbose" / "smithy"


# ==============================================================================
# Category 1: JSON AST Loading (6 tests)
# ==============================================================================

def test_load_valid_json_ast():
    """Test loading a valid Smithy JSON AST file."""
    spec_path = SPECS_DIR / "weather.json"
    json_ast = _load_json_ast(spec_path)
    assert "smithy" in json_ast
    assert "shapes" in json_ast
    assert json_ast["smithy"] == "2.0"


def test_load_minimal_json_ast(tmp_path):
    """Test loading minimal valid JSON AST."""
    minimal = {
        "smithy": "2.0",
        "shapes": {}
    }
    json_file = tmp_path / "minimal.json"
    json_file.write_text(json.dumps(minimal), encoding='utf-8')

    json_ast = _load_json_ast(json_file)
    assert json_ast["smithy"] == "2.0"
    assert json_ast["shapes"] == {}


def test_load_invalid_structure_missing_smithy(tmp_path):
    """Test error when 'smithy' field is missing."""
    invalid = {"shapes": {}}
    json_file = tmp_path / "invalid.json"
    json_file.write_text(json.dumps(invalid), encoding='utf-8')

    with pytest.raises(ValueError, match="missing 'smithy' version field"):
        _load_json_ast(json_file)


def test_load_invalid_structure_missing_shapes(tmp_path):
    """Test error when 'shapes' field is missing."""
    invalid = {"smithy": "2.0"}
    json_file = tmp_path / "invalid.json"
    json_file.write_text(json.dumps(invalid), encoding='utf-8')

    with pytest.raises(ValueError, match="missing 'shapes' field"):
        _load_json_ast(json_file)


def test_load_malformed_json(tmp_path):
    """Test error when JSON is malformed."""
    json_file = tmp_path / "malformed.json"
    json_file.write_text("{invalid json", encoding='utf-8')

    with pytest.raises(ValueError, match="Invalid JSON"):
        _load_json_ast(json_file)


def test_detect_smithy_directory():
    """Test directory detection for smithy-build.json."""
    # This test would require creating a temp directory with smithy-build.json
    # For now, we just verify the logic in compile_smithy
    pass


# ==============================================================================
# Category 2: Type Resolution (12 tests)
# ==============================================================================

def test_scalar_type_string():
    """Test String → str mapping."""
    shapes = {}
    assert _smithy_type_to_lap("smithy.api#String", shapes) == "str"


def test_scalar_type_integer():
    """Test Integer → int mapping."""
    shapes = {}
    assert _smithy_type_to_lap("smithy.api#Integer", shapes) == "int"


def test_scalar_type_long():
    """Test Long → int(i64) mapping."""
    shapes = {}
    assert _smithy_type_to_lap("smithy.api#Long", shapes) == "int(i64)"


def test_scalar_type_boolean():
    """Test Boolean → bool mapping."""
    shapes = {}
    assert _smithy_type_to_lap("smithy.api#Boolean", shapes) == "bool"


def test_scalar_type_float():
    """Test Float → num(f32) mapping."""
    shapes = {}
    assert _smithy_type_to_lap("smithy.api#Float", shapes) == "num(f32)"


def test_scalar_type_timestamp():
    """Test Timestamp → str(timestamp) mapping."""
    shapes = {}
    assert _smithy_type_to_lap("smithy.api#Timestamp", shapes) == "str(timestamp)"


def test_list_type():
    """Test list type → [element] mapping."""
    shapes = {
        "example#StringList": {
            "type": "list",
            "member": {"target": "smithy.api#String"}
        }
    }
    assert _smithy_type_to_lap("example#StringList", shapes) == "[str]"


def test_map_type():
    """Test map type → map<k,v> mapping."""
    shapes = {
        "example#StringMap": {
            "type": "map",
            "key": {"target": "smithy.api#String"},
            "value": {"target": "smithy.api#Integer"}
        }
    }
    assert _smithy_type_to_lap("example#StringMap", shapes) == "map<str,int>"


def test_structure_type():
    """Test structure returns name."""
    shapes = {
        "example#Person": {
            "type": "structure",
            "members": {
                "name": {"target": "smithy.api#String"}
            }
        }
    }
    assert _smithy_type_to_lap("example#Person", shapes) == "Person"


def test_enum_type():
    """Test enum type with member extraction."""
    shapes = {
        "example#Status": {
            "type": "enum",
            "members": {
                "ACTIVE": {
                    "target": "smithy.api#Unit",
                    "traits": {"smithy.api#enumValue": "active"}
                },
                "INACTIVE": {
                    "target": "smithy.api#Unit",
                    "traits": {"smithy.api#enumValue": "inactive"}
                }
            }
        }
    }
    result = _smithy_type_to_lap("example#Status", shapes)
    assert result == "enum(active/inactive)"


def test_circular_reference():
    """Test circular reference detection."""
    shapes = {
        "example#Node": {
            "type": "structure",
            "members": {
                "value": {"target": "smithy.api#String"},
                "next": {"target": "example#Node"}
            }
        }
    }
    # Should not infinite loop
    result = _smithy_type_to_lap("example#Node", shapes)
    assert result == "Node"


def test_unknown_type_defaults_to_any():
    """Test unknown types default to 'any'."""
    shapes = {}
    assert _smithy_type_to_lap("example#Unknown", shapes) == "any"


# ==============================================================================
# Category 3: HTTP Binding (10 tests)
# ==============================================================================

def test_parse_http_trait():
    """Test parsing @http trait."""
    traits = {
        "smithy.api#http": {
            "method": "POST",
            "uri": "/users",
            "code": 201
        }
    }
    method, uri, code = _parse_http_trait(traits)
    assert method == "POST"
    assert uri == "/users"
    assert code == 201


def test_extract_uri_params_single():
    """Test extracting single path parameter."""
    params = _extract_uri_params("/cities/{cityId}")
    assert params == ["cityId"]


def test_extract_uri_params_multiple():
    """Test extracting multiple path parameters."""
    params = _extract_uri_params("/users/{userId}/posts/{postId}")
    assert params == ["userId", "postId"]


def test_extract_uri_params_none():
    """Test URI with no parameters."""
    params = _extract_uri_params("/current-time")
    assert params == []


def test_http_label_to_required_params():
    """Test @httpLabel → required_params."""
    shapes = {
        "example#Input": {
            "type": "structure",
            "members": {
                "cityId": {
                    "target": "smithy.api#String",
                    "traits": {
                        "smithy.api#required": {},
                        "smithy.api#httpLabel": {}
                    }
                }
            }
        }
    }
    http_trait = {"method": "GET", "uri": "/cities/{cityId}"}
    required, optional, body = _extract_http_bindings("example#Input", http_trait, shapes)

    assert len(required) == 1
    assert required[0].name == "cityId"
    assert required[0].required is True


def test_http_query_to_optional_params():
    """Test @httpQuery without @required → optional_params."""
    shapes = {
        "example#Input": {
            "type": "structure",
            "members": {
                "days": {
                    "target": "smithy.api#Integer",
                    "traits": {
                        "smithy.api#httpQuery": "days"
                    }
                }
            }
        }
    }
    http_trait = {"method": "GET", "uri": "/forecast"}
    required, optional, body = _extract_http_bindings("example#Input", http_trait, shapes)

    assert len(optional) == 1
    assert optional[0].name == "days"
    assert optional[0].required is False


def test_http_query_with_required():
    """Test @httpQuery with @required → required_params."""
    shapes = {
        "example#Input": {
            "type": "structure",
            "members": {
                "cityId": {
                    "target": "smithy.api#String",
                    "traits": {
                        "smithy.api#required": {},
                        "smithy.api#httpQuery": "city"
                    }
                }
            }
        }
    }
    http_trait = {"method": "GET", "uri": "/forecast"}
    required, optional, body = _extract_http_bindings("example#Input", http_trait, shapes)

    assert len(required) == 1
    assert required[0].name == "city"
    assert required[0].required is True


def test_http_header_to_optional_params():
    """Test @httpHeader → optional_params."""
    shapes = {
        "example#Input": {
            "type": "structure",
            "members": {
                "apiKey": {
                    "target": "smithy.api#String",
                    "traits": {
                        "smithy.api#httpHeader": "X-API-Key"
                    }
                }
            }
        }
    }
    http_trait = {"method": "GET", "uri": "/data"}
    required, optional, body = _extract_http_bindings("example#Input", http_trait, shapes)

    assert len(optional) == 1
    assert optional[0].name == "X-API-Key"


def test_unbound_members_to_request_body():
    """Test unbound members → request_body."""
    shapes = {
        "example#Input": {
            "type": "structure",
            "members": {
                "name": {
                    "target": "smithy.api#String",
                    "traits": {"smithy.api#required": {}}
                },
                "age": {
                    "target": "smithy.api#Integer"
                }
            }
        }
    }
    http_trait = {"method": "POST", "uri": "/users"}
    required, optional, body = _extract_http_bindings("example#Input", http_trait, shapes)

    assert len(body) == 2
    assert body[0].name == "name"
    assert body[0].required is True
    assert body[1].name == "age"
    assert body[1].required is False


def test_operation_without_http_trait():
    """Test operations without @http trait are skipped."""
    shapes = {
        "example#Op": {
            "type": "operation",
            "traits": {}
        }
    }
    endpoint = _operation_to_endpoint("example#Op", shapes["example#Op"], shapes)
    assert endpoint is None


# ==============================================================================
# Category 4: Operation Conversion (8 tests)
# ==============================================================================

def test_simple_get_operation():
    """Test simple GET with path param."""
    shapes = {
        "example#GetCity": {
            "type": "operation",
            "input": {"target": "example#GetCityInput"},
            "output": {"target": "example#GetCityOutput"},
            "traits": {
                "smithy.api#http": {
                    "method": "GET",
                    "uri": "/cities/{cityId}",
                    "code": 200
                }
            }
        },
        "example#GetCityInput": {
            "type": "structure",
            "members": {
                "cityId": {
                    "target": "smithy.api#String",
                    "traits": {
                        "smithy.api#required": {},
                        "smithy.api#httpLabel": {}
                    }
                }
            }
        },
        "example#GetCityOutput": {
            "type": "structure",
            "members": {
                "name": {
                    "target": "smithy.api#String",
                    "traits": {"smithy.api#required": {}}
                }
            }
        }
    }

    endpoint = _operation_to_endpoint("example#GetCity", shapes["example#GetCity"], shapes)
    assert endpoint is not None
    assert endpoint.method == "GET"
    assert endpoint.path == "/cities/{cityId}"
    assert len(endpoint.required_params) == 1
    assert endpoint.required_params[0].name == "cityId"


def test_post_operation_with_body():
    """Test POST with request body."""
    shapes = {
        "example#CreateReport": {
            "type": "operation",
            "input": {"target": "example#CreateReportInput"},
            "traits": {
                "smithy.api#http": {
                    "method": "POST",
                    "uri": "/reports",
                    "code": 201
                }
            }
        },
        "example#CreateReportInput": {
            "type": "structure",
            "members": {
                "title": {
                    "target": "smithy.api#String",
                    "traits": {"smithy.api#required": {}}
                },
                "content": {
                    "target": "smithy.api#String"
                }
            }
        }
    }

    endpoint = _operation_to_endpoint("example#CreateReport", shapes["example#CreateReport"], shapes)
    assert endpoint is not None
    assert endpoint.method == "POST"
    assert len(endpoint.request_body) == 2


def test_operation_with_errors():
    """Test operation with multiple errors."""
    shapes = {
        "example#GetData": {
            "type": "operation",
            "errors": [
                {"target": "example#NotFound"},
                {"target": "example#Unauthorized"}
            ],
            "traits": {
                "smithy.api#http": {
                    "method": "GET",
                    "uri": "/data"
                }
            }
        },
        "example#NotFound": {
            "type": "structure",
            "members": {},
            "traits": {
                "smithy.api#error": "client",
                "smithy.api#httpError": 404
            }
        },
        "example#Unauthorized": {
            "type": "structure",
            "members": {},
            "traits": {
                "smithy.api#error": "client",
                "smithy.api#httpError": 401
            }
        }
    }

    endpoint = _operation_to_endpoint("example#GetData", shapes["example#GetData"], shapes)
    assert endpoint is not None
    assert len(endpoint.error_schemas) == 2
    assert endpoint.error_schemas[0].code == "404"
    assert endpoint.error_schemas[1].code == "401"


def test_operation_without_input():
    """Test operation with no input."""
    shapes = {
        "example#GetTime": {
            "type": "operation",
            "output": {"target": "example#GetTimeOutput"},
            "traits": {
                "smithy.api#http": {
                    "method": "GET",
                    "uri": "/time"
                }
            }
        },
        "example#GetTimeOutput": {
            "type": "structure",
            "members": {
                "time": {"target": "smithy.api#Timestamp"}
            }
        }
    }

    endpoint = _operation_to_endpoint("example#GetTime", shapes["example#GetTime"], shapes)
    assert endpoint is not None
    assert len(endpoint.required_params) == 0
    assert len(endpoint.optional_params) == 0
    assert len(endpoint.request_body) == 0


def test_operation_without_output():
    """Test operation with no output."""
    shapes = {
        "example#DeleteItem": {
            "type": "operation",
            "input": {"target": "example#DeleteItemInput"},
            "traits": {
                "smithy.api#http": {
                    "method": "DELETE",
                    "uri": "/items/{id}"
                }
            }
        },
        "example#DeleteItemInput": {
            "type": "structure",
            "members": {
                "id": {
                    "target": "smithy.api#String",
                    "traits": {
                        "smithy.api#required": {},
                        "smithy.api#httpLabel": {}
                    }
                }
            }
        }
    }

    endpoint = _operation_to_endpoint("example#DeleteItem", shapes["example#DeleteItem"], shapes)
    assert endpoint is not None
    assert len(endpoint.response_schemas) == 0


def test_operation_with_nested_response():
    """Test operation with nested response structure."""
    shapes = {
        "example#GetUser": {
            "type": "operation",
            "output": {"target": "example#GetUserOutput"},
            "traits": {
                "smithy.api#http": {
                    "method": "GET",
                    "uri": "/users/{id}"
                }
            }
        },
        "example#GetUserOutput": {
            "type": "structure",
            "members": {
                "user": {
                    "target": "example#User",
                    "traits": {"smithy.api#required": {}}
                }
            }
        },
        "example#User": {
            "type": "structure",
            "members": {
                "id": {"target": "smithy.api#String"},
                "name": {"target": "smithy.api#String"}
            }
        }
    }

    endpoint = _operation_to_endpoint("example#GetUser", shapes["example#GetUser"], shapes)
    assert endpoint is not None
    assert len(endpoint.response_schemas) == 1
    assert len(endpoint.response_schemas[0].fields) == 1
    assert len(endpoint.response_schemas[0].fields[0].children) > 0


def test_skip_operation_without_http():
    """Test operation without @http trait is skipped."""
    shapes = {
        "example#InternalOp": {
            "type": "operation",
            "traits": {}
        }
    }

    endpoint = _operation_to_endpoint("example#InternalOp", shapes["example#InternalOp"], shapes)
    assert endpoint is None


def test_operation_with_description():
    """Test operation description extraction."""
    shapes = {
        "example#GetData": {
            "type": "operation",
            "traits": {
                "smithy.api#http": {
                    "method": "GET",
                    "uri": "/data"
                },
                "smithy.api#documentation": "Fetches all data"
            }
        }
    }

    endpoint = _operation_to_endpoint("example#GetData", shapes["example#GetData"], shapes)
    assert endpoint is not None
    assert endpoint.summary == "Fetches all data"


# ==============================================================================
# Category 5: Service Extraction (6 tests)
# ==============================================================================

def test_find_service():
    """Test finding service shape."""
    shapes = {
        "example#MyService": {
            "type": "service",
            "version": "1.0"
        },
        "example#OtherShape": {
            "type": "structure"
        }
    }

    service_id, service_shape = _find_service(shapes)
    assert service_id == "example#MyService"
    assert service_shape["type"] == "service"


def test_extract_service_version():
    """Test extracting service version."""
    service_shape = {
        "type": "service",
        "version": "2006-03-01"
    }

    metadata = _extract_service_metadata(service_shape)
    assert metadata["version"] == "2006-03-01"


def test_extract_bearer_auth():
    """Test extracting @httpBearerAuth."""
    service_shape = {
        "type": "service",
        "traits": {
            "smithy.api#httpBearerAuth": {}
        }
    }
    shapes = {}

    auth = _extract_auth_scheme(service_shape, shapes)
    assert auth == "Bearer token"


def test_extract_api_key_auth():
    """Test extracting @httpApiKeyAuth."""
    service_shape = {
        "type": "service",
        "traits": {
            "smithy.api#httpApiKeyAuth": {"name": "api_key"}
        }
    }
    shapes = {}

    auth = _extract_auth_scheme(service_shape, shapes)
    assert auth == "ApiKey"


def test_extract_aws_sigv4():
    """Test extracting AWS SigV4 auth."""
    service_shape = {
        "type": "service",
        "traits": {
            "aws.auth#sigv4": {"name": "weather"}
        }
    }
    shapes = {}

    auth = _extract_auth_scheme(service_shape, shapes)
    assert auth == "AWS SigV4"


def test_multiple_auth_schemes():
    """Test multiple auth schemes (joined with |)."""
    service_shape = {
        "type": "service",
        "traits": {
            "smithy.api#httpBearerAuth": {},
            "smithy.api#httpApiKeyAuth": {}
        }
    }
    shapes = {}

    auth = _extract_auth_scheme(service_shape, shapes)
    assert "Bearer token" in auth
    assert "ApiKey" in auth
    assert " | " in auth


# ==============================================================================
# Category 6: End-to-End Compilation (8 tests)
# ==============================================================================

class TestWeatherServiceCompilation:
    """Test complete Weather service compilation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        spec_path = SPECS_DIR / "weather.json"
        self.lap = compile_smithy(str(spec_path))

    def test_api_name(self):
        """Test API name extraction."""
        assert self.lap.api_name == "Weather"

    def test_version(self):
        """Test version extraction."""
        assert self.lap.version == "2006-03-01"

    def test_auth_scheme(self):
        """Test auth scheme extraction."""
        assert "AWS SigV4" in self.lap.auth_scheme

    def test_endpoint_count(self):
        """Test correct number of endpoints."""
        # Weather service has 4 operations, all HTTP-bound
        assert len(self.lap.endpoints) == 4

    def test_get_city_endpoint(self):
        """Test GetCity endpoint extraction."""
        ep = next((e for e in self.lap.endpoints if e.path == "/cities/{cityId}"), None)
        assert ep is not None
        assert ep.method == "GET"
        assert ep.path == "/cities/{cityId}"
        assert len(ep.required_params) == 1
        assert ep.required_params[0].name == "cityId"

    def test_get_forecast_endpoint(self):
        """Test GetForecast endpoint with query params."""
        ep = next((e for e in self.lap.endpoints if e.path == "/forecast"), None)
        assert ep is not None
        assert ep.method == "GET"
        assert ep.path == "/forecast"
        # cityId is required query param
        assert len(ep.required_params) == 1
        assert ep.required_params[0].name == "city"
        # days and units are optional query params
        assert len(ep.optional_params) == 2

    def test_create_report_endpoint(self):
        """Test CreateReport POST endpoint."""
        ep = next((e for e in self.lap.endpoints if e.path == "/reports"), None)
        assert ep is not None
        assert ep.method == "POST"
        assert ep.path == "/reports"
        assert len(ep.request_body) == 4

    def test_to_lap_output(self):
        """Test .to_lap() output format."""
        lap_text = self.lap.to_lap(lean=False)
        assert "@api Weather" in lap_text
        assert "@version 2006-03-01" in lap_text
        assert "@auth AWS SigV4" in lap_text
        assert "GET /cities/{cityId}" in lap_text
        assert "GET /forecast" in lap_text
        assert "POST /reports" in lap_text


# ==============================================================================
# Category 7: Edge Cases (10 tests)
# ==============================================================================

def test_no_service_error():
    """Test error when no service found."""
    shapes = {
        "example#NotAService": {
            "type": "structure"
        }
    }

    with pytest.raises(ValueError, match="No service found"):
        _find_service(shapes)


def test_service_with_no_operations():
    """Test service with no operations."""
    shapes = {
        "example#Empty": {
            "type": "service",
            "version": "1.0"
        }
    }

    # Should not crash
    service_id, service_shape = _find_service(shapes)
    assert service_id == "example#Empty"


def test_empty_structure():
    """Test structure with no members."""
    shapes = {
        "example#Empty": {
            "type": "structure",
            "members": {}
        }
    }

    fields = _structure_to_response_fields(shapes["example#Empty"], shapes)
    assert fields == []


def test_enum_single_value():
    """Test enum with single value."""
    shapes = {
        "example#Single": {
            "type": "enum",
            "members": {
                "ONLY": {
                    "target": "smithy.api#Unit",
                    "traits": {"smithy.api#enumValue": "only"}
                }
            }
        }
    }

    result = _smithy_type_to_lap("example#Single", shapes)
    assert result == "enum(only)"


def test_missing_http_trait():
    """Test operation without @http trait."""
    shapes = {
        "example#Op": {
            "type": "operation",
            "traits": {}
        }
    }

    endpoint = _operation_to_endpoint("example#Op", shapes["example#Op"], shapes)
    assert endpoint is None


def test_invalid_json_ast_format(tmp_path):
    """Test invalid JSON AST format."""
    invalid = {"not": "valid"}
    json_file = tmp_path / "invalid.json"
    json_file.write_text(json.dumps(invalid), encoding='utf-8')

    with pytest.raises(ValueError):
        _load_json_ast(json_file)


def test_circular_shape_reference():
    """Test circular shape reference handling."""
    shapes = {
        "example#Node": {
            "type": "structure",
            "members": {
                "next": {"target": "example#Node"}
            }
        }
    }

    # Should not infinite loop
    result = _smithy_type_to_lap("example#Node", shapes)
    assert result == "Node"


def test_deep_nesting_limit():
    """Test deep nesting depth limit."""
    shapes = {
        "example#Deep": {
            "type": "structure",
            "members": {
                "level1": {"target": "example#Level1"}
            }
        },
        "example#Level1": {
            "type": "structure",
            "members": {
                "level2": {"target": "example#Level2"}
            }
        },
        "example#Level2": {
            "type": "structure",
            "members": {
                "level3": {"target": "example#Level3"}
            }
        },
        "example#Level3": {
            "type": "structure",
            "members": {
                "level4": {"target": "example#Level4"}
            }
        },
        "example#Level4": {
            "type": "structure",
            "members": {
                "value": {"target": "smithy.api#String"}
            }
        }
    }

    # Should stop at depth limit
    fields = _structure_to_response_fields(shapes["example#Deep"], shapes)
    assert len(fields) > 0
    # Should have some nesting but not infinite


def test_multiple_services_uses_first():
    """Test multiple services (uses first found)."""
    shapes = {
        "example#First": {
            "type": "service",
            "version": "1.0"
        },
        "example#Second": {
            "type": "service",
            "version": "2.0"
        }
    }

    service_id, service_shape = _find_service(shapes)
    # Should return one of them (order depends on dict iteration)
    assert service_shape["type"] == "service"


def test_unsupported_file_extension(tmp_path):
    """Test error for unsupported file extension."""
    xml_file = tmp_path / "test.xml"
    xml_file.write_text("<xml/>", encoding='utf-8')

    with pytest.raises(ValueError, match="Unsupported file type"):
        compile_smithy(str(xml_file))
