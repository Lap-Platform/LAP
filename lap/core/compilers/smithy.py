"""
AWS Smithy compiler for LAP format.

Compiles Smithy JSON AST (and optionally .smithy IDL via Smithy CLI) into LAP format.
Focuses on HTTP-bound operations (operations with @http trait).

Smithy → LAP mapping:
- Service → LAPSpec (api_name, version, auth_scheme)
- Operation → Endpoint (method, path from @http trait)
- Operation input → required_params, optional_params, request_body (based on HTTP binding traits)
- Operation output → response_schemas
- Operation errors → error_schemas
- @httpLabel → required_params (path parameters)
- @httpQuery → optional_params or required_params (based on @required trait)
- @httpHeader → optional_params or required_params
- @httpPayload → request_body
- Unbound members → request_body (JSON body)
"""

import json
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Any

from lap.core.formats.lap import (
    LAPSpec,
    Endpoint,
    Param,
    ResponseSchema,
    ResponseField,
    ErrorSchema,
)
from lap.core.utils import read_file_safe


# Smithy scalar types → LAP types
_SMITHY_SCALAR_MAP = {
    "smithy.api#String": "str",
    "smithy.api#Integer": "int",
    "smithy.api#Long": "int(i64)",
    "smithy.api#Short": "int",
    "smithy.api#Byte": "int",
    "smithy.api#Boolean": "bool",
    "smithy.api#Float": "num(f32)",
    "smithy.api#Double": "num(f64)",
    "smithy.api#BigInteger": "int(big)",
    "smithy.api#BigDecimal": "num(big)",
    "smithy.api#Timestamp": "str(timestamp)",
    "smithy.api#Blob": "bytes",
    "smithy.api#Document": "any",
}

# Smithy auth traits → LAP auth strings
_AUTH_TRAIT_MAP = {
    "smithy.api#httpBasicAuth": "HTTP Basic",
    "smithy.api#httpBearerAuth": "Bearer token",
    "smithy.api#httpApiKeyAuth": "ApiKey",
    "aws.auth#sigv4": "AWS SigV4",
    "aws.auth#sigv4a": "AWS SigV4",
}


# ==============================================================================
# Phase 1: Core Compiler Structure
# ==============================================================================

def compile_smithy(spec_path: str) -> LAPSpec:
    """
    Main entry point for Smithy compilation.

    Accepts:
    - .json files (Smithy JSON AST) → parse directly
    - .smithy files (Smithy IDL) → convert via Smithy CLI → parse JSON AST
    - directories with smithy-build.json → build project → parse output

    Args:
        spec_path: Path to Smithy spec file or directory

    Returns:
        LAPSpec object ready for .to_lap() conversion

    Raises:
        ValueError: If spec is invalid or Smithy CLI not available for .smithy files
    """
    path = Path(spec_path)

    # Determine input type and load JSON AST
    if path.is_file():
        if path.suffix == ".json":
            json_ast = _load_json_ast(path)
        elif path.suffix == ".smithy":
            json_ast = _smithy_idl_to_json(path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}. Expected .json or .smithy")
    elif path.is_dir():
        # Check for smithy-build.json
        if (path / "smithy-build.json").exists():
            json_ast = _build_smithy_project(path)
        else:
            raise ValueError(f"Directory {path} does not contain smithy-build.json")
    else:
        raise ValueError(f"Path does not exist: {spec_path}")

    # Build shape index for reference resolution
    shapes = _build_shape_index(json_ast)

    # Find service shape
    service_id, service_shape = _find_service(shapes)

    # Extract service metadata
    api_name = service_id.split("#")[1] if "#" in service_id else service_id
    metadata = _extract_service_metadata(service_shape)
    auth_scheme = _extract_auth_scheme(service_shape, shapes)

    # Convert operations to endpoints
    endpoints = []
    if "operations" in service_shape:
        for op_ref in service_shape["operations"]:
            op_id = op_ref["target"]
            if op_id in shapes:
                endpoint = _operation_to_endpoint(op_id, shapes[op_id], shapes)
                if endpoint:  # Only include HTTP-bound operations
                    endpoints.append(endpoint)

    return LAPSpec(
        api_name=api_name,
        version=metadata.get("version", ""),
        auth_scheme=auth_scheme,
        endpoints=endpoints,
    )


def _load_json_ast(path: Path) -> dict:
    """Load and validate Smithy JSON AST."""
    try:
        content = read_file_safe(str(path))
        if content is None:
            raise ValueError(f"Could not read file: {path}")
        json_ast = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")

    # Validate structure
    if "smithy" not in json_ast:
        raise ValueError(f"Not a valid Smithy JSON AST: missing 'smithy' version field")
    if "shapes" not in json_ast:
        raise ValueError(f"Not a valid Smithy JSON AST: missing 'shapes' field")

    return json_ast


def _smithy_idl_to_json(smithy_path: Path) -> dict:
    """Convert .smithy IDL file to JSON AST via Smithy CLI."""
    # Check if Smithy CLI is available
    if not shutil.which("smithy"):
        raise ValueError(
            "Smithy CLI not found. To compile .smithy files, install Smithy CLI:\n"
            "https://smithy.io/2.0/guides/smithy-cli.html\n\n"
            "Alternatively, provide a JSON AST file (.json) directly."
        )

    try:
        # Run: smithy ast <file>
        result = subprocess.run(
            ["smithy", "ast", str(smithy_path)],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
        )
        json_ast = json.loads(result.stdout)
        return json_ast
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Smithy CLI failed: {e.stderr}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Smithy CLI produced invalid JSON: {e}")


def _build_smithy_project(project_dir: Path) -> dict:
    """Build Smithy project and extract JSON AST."""
    # Check if Smithy CLI is available
    if not shutil.which("smithy"):
        raise ValueError(
            "Smithy CLI not found. To build Smithy projects, install Smithy CLI:\n"
            "https://smithy.io/2.0/guides/smithy-cli.html"
        )

    try:
        # Run: smithy build (in project directory)
        result = subprocess.run(
            ["smithy", "build"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
        )

        # Look for model.json in build output
        build_dir = project_dir / "build" / "smithy"
        model_file = build_dir / "model.json"

        if not model_file.exists():
            # Try to find any .json file in build output
            json_files = list(build_dir.glob("**/*.json"))
            if json_files:
                model_file = json_files[0]
            else:
                raise ValueError("No model.json found in build output")

        return _load_json_ast(model_file)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Smithy build failed: {e.stderr}")


def _build_shape_index(json_ast: dict) -> dict:
    """
    Build {shape_id: shape_def} lookup dictionary.

    Makes shape resolution O(1) instead of O(n).
    """
    return json_ast.get("shapes", {})


# ==============================================================================
# Phase 2: Service & Metadata Extraction
# ==============================================================================

def _find_service(shapes: dict) -> tuple[str, dict]:
    """Find first service shape in model."""
    for shape_id, shape_def in shapes.items():
        if shape_def.get("type") == "service":
            return shape_id, shape_def
    raise ValueError("No service found in Smithy model")


def _extract_service_metadata(service_shape: dict) -> dict:
    """Extract version, description from service shape."""
    metadata = {}

    # Version
    if "version" in service_shape:
        metadata["version"] = service_shape["version"]

    # Description from @documentation trait
    traits = service_shape.get("traits", {})
    if "smithy.api#documentation" in traits:
        metadata["description"] = traits["smithy.api#documentation"]
    elif "smithy.api#title" in traits:
        metadata["description"] = traits["smithy.api#title"]

    return metadata


def _extract_auth_scheme(service_shape: dict, shapes: dict) -> str:
    """Map @auth trait to LAP auth string."""
    traits = service_shape.get("traits", {})
    auth_schemes = []

    # Check for auth traits
    for trait_id in traits:
        if trait_id in _AUTH_TRAIT_MAP:
            auth_schemes.append(_AUTH_TRAIT_MAP[trait_id])
        elif trait_id == "smithy.api#auth":
            # @auth references other auth schemes
            auth_refs = traits[trait_id]
            for auth_ref in auth_refs:
                auth_id = auth_ref.get("target", auth_ref) if isinstance(auth_ref, dict) else auth_ref
                if auth_id in _AUTH_TRAIT_MAP:
                    auth_schemes.append(_AUTH_TRAIT_MAP[auth_id])

    # Return joined string or empty
    return " | ".join(auth_schemes) if auth_schemes else ""


# ==============================================================================
# Phase 3: Type Resolution
# ==============================================================================

def _smithy_type_to_lap(shape_id: str, shapes: dict, visited: set = None) -> str:
    """
    Convert Smithy type to LAP type string.

    Handles:
    - Scalar types (String → str, Integer → int, etc.)
    - Collections (list → [type], map → map<k,v>)
    - Structures (by name or inline)
    - Enums (enum(A/B/C))
    - References (resolve with cycle detection)

    Args:
        shape_id: Smithy shape ID (e.g., "smithy.api#String", "example#MyStruct")
        shapes: Shape index
        visited: Set of visited shape IDs (for cycle detection)

    Returns:
        LAP type string
    """
    if visited is None:
        visited = set()

    # Cycle detection
    if shape_id in visited:
        return "any"  # Break cycle

    # Check scalar map first
    if shape_id in _SMITHY_SCALAR_MAP:
        return _SMITHY_SCALAR_MAP[shape_id]

    # Resolve shape definition
    if shape_id not in shapes:
        return "any"  # Unknown type

    shape_def = shapes[shape_id]
    shape_type = shape_def.get("type")

    visited_copy = visited | {shape_id}

    if shape_type == "list":
        # List type: [element_type]
        member = shape_def.get("member", {})
        member_target = member.get("target", "smithy.api#String")
        element_type = _smithy_type_to_lap(member_target, shapes, visited_copy)
        return f"[{element_type}]"

    elif shape_type == "map":
        # Map type: map<key_type, value_type>
        key = shape_def.get("key", {})
        value = shape_def.get("value", {})
        key_target = key.get("target", "smithy.api#String")
        value_target = value.get("target", "smithy.api#String")
        key_type = _smithy_type_to_lap(key_target, shapes, visited_copy)
        value_type = _smithy_type_to_lap(value_target, shapes, visited_copy)
        return f"map<{key_type},{value_type}>"

    elif shape_type == "structure":
        # Structure: return name (will be defined in @type or inline)
        name = shape_id.split("#")[1] if "#" in shape_id else shape_id
        return name

    elif shape_type == "enum":
        # Enum: enum(VALUE1/VALUE2/VALUE3)
        members = shape_def.get("members", {})
        enum_values = []
        for member_name, member_def in members.items():
            # Get enum value from @enumValue trait, or use member name
            traits = member_def.get("traits", {})
            if "smithy.api#enumValue" in traits:
                enum_values.append(traits["smithy.api#enumValue"])
            else:
                enum_values.append(member_name)
        return f"enum({'/'.join(enum_values)})" if enum_values else "str"

    elif shape_type == "union":
        # Union: treat as structure with optional fields
        name = shape_id.split("#")[1] if "#" in shape_id else shape_id
        return name

    else:
        # Default to any for unknown types
        return "any"


def _resolve_shape_ref(shape_id: str, shapes: dict, visited: set = None) -> dict:
    """Resolve shape reference with cycle detection."""
    if visited is None:
        visited = set()

    if shape_id in visited or shape_id not in shapes:
        return {}

    return shapes[shape_id]


def _structure_to_response_fields(struct_shape: dict, shapes: dict, depth: int = 0, visited: set = None) -> list[ResponseField]:
    """
    Convert structure to nested response fields.

    Args:
        struct_shape: Structure shape definition
        shapes: Shape index
        depth: Current nesting depth (for limiting recursion)
        visited: Set of visited shape IDs

    Returns:
        List of ResponseField objects
    """
    if visited is None:
        visited = set()

    if depth > 3:  # Limit nesting depth
        return []

    fields = []
    members = struct_shape.get("members", {})

    for member_name, member_def in members.items():
        member_target = member_def.get("target", "smithy.api#String")
        traits = member_def.get("traits", {})

        # Check if nullable (opposite of required in Smithy)
        nullable = "smithy.api#required" not in traits

        # Get type
        field_type = _smithy_type_to_lap(member_target, shapes, visited)

        # Check if nested structure
        children = []
        if member_target in shapes:
            target_shape = shapes[member_target]
            if target_shape.get("type") == "structure" and member_target not in visited:
                visited_copy = visited | {member_target}
                children = _structure_to_response_fields(
                    target_shape, shapes, depth + 1, visited_copy
                )

        fields.append(ResponseField(
            name=member_name,
            type=field_type,
            nullable=nullable,
            children=children,
        ))

    return fields


# ==============================================================================
# Phase 4: HTTP Binding Extraction
# ==============================================================================

def _parse_http_trait(traits: dict) -> tuple[str, str, int]:
    """
    Extract HTTP method, URI pattern, status code from @http trait.

    Returns:
        (method, uri_pattern, status_code)
    """
    http_trait = traits.get("smithy.api#http", {})
    method = http_trait.get("method", "GET")
    uri = http_trait.get("uri", "/")
    code = http_trait.get("code", 200)
    return method, uri, code


def _extract_uri_params(uri_pattern: str) -> list[str]:
    """
    Parse {param} placeholders from URI pattern.

    Examples:
        "/cities/{cityId}" → ["cityId"]
        "/users/{userId}/posts/{postId}" → ["userId", "postId"]
    """
    import re
    return re.findall(r'\{(\w+)\}', uri_pattern)


def _extract_http_bindings(
    input_shape_id: Optional[str],
    http_trait: dict,
    shapes: dict,
) -> tuple[list[Param], list[Param], list[Param]]:
    """
    Extract HTTP bindings from operation input.

    Returns:
        (required_params, optional_params, request_body)
    """
    if not input_shape_id or input_shape_id not in shapes:
        return [], [], []

    input_shape = shapes[input_shape_id]
    members = input_shape.get("members", {})

    required_params = []
    optional_params = []
    body_fields = []
    payload_member = None

    # Check if there's a designated @httpPayload member
    for member_name, member_def in members.items():
        if "smithy.api#httpPayload" in member_def.get("traits", {}):
            payload_member = member_name
            break

    for member_name, member_def in members.items():
        member_target = member_def.get("target", "smithy.api#String")
        traits = member_def.get("traits", {})
        required = "smithy.api#required" in traits
        description = traits.get("smithy.api#documentation", "")
        field_type = _smithy_type_to_lap(member_target, shapes)

        # Classify by HTTP binding trait
        if "smithy.api#httpLabel" in traits:
            # Path parameter (always required)
            required_params.append(Param(
                name=member_name,
                type=field_type,
                description=description,
                required=True,
            ))
        elif "smithy.api#httpQuery" in traits:
            # Query parameter
            query_name = traits.get("smithy.api#httpQuery")
            if isinstance(query_name, dict):
                query_name = query_name.get("value", member_name)
            elif query_name is True:
                query_name = member_name

            param = Param(
                name=query_name,
                type=field_type,
                description=description,
                required=required,
            )
            if required:
                required_params.append(param)
            else:
                optional_params.append(param)
        elif "smithy.api#httpHeader" in traits:
            # Header parameter
            header_name = traits.get("smithy.api#httpHeader")
            if isinstance(header_name, dict):
                header_name = header_name.get("value", member_name)
            elif header_name is True:
                header_name = member_name

            param = Param(
                name=header_name,
                type=field_type,
                description=description,
                required=required,
            )
            if required:
                required_params.append(param)
            else:
                optional_params.append(param)
        elif member_name == payload_member:
            # Explicit @httpPayload member → entire body
            body_fields.append(Param(
                name=member_name,
                type=field_type,
                description=description,
                required=required,
            ))
        else:
            # Unbound member → JSON body
            body_fields.append(Param(
                name=member_name,
                type=field_type,
                description=description,
                required=required,
            ))

    return required_params, optional_params, body_fields


# ==============================================================================
# Phase 5: Operation Conversion
# ==============================================================================

def _operation_to_endpoint(op_id: str, op_shape: dict, shapes: dict) -> Optional[Endpoint]:
    """
    Convert Smithy operation to LAP Endpoint.

    Returns None if operation has no @http trait (not HTTP-bound).
    """
    traits = op_shape.get("traits", {})

    # Check for @http trait
    if "smithy.api#http" not in traits:
        return None  # Skip non-HTTP operations

    # Extract HTTP metadata
    method, uri_pattern, status_code = _parse_http_trait(traits)

    # Extract operation name and summary
    op_name = op_id.split("#")[1] if "#" in op_id else op_id
    summary = traits.get("smithy.api#documentation", "")

    # Extract input bindings
    input_ref = op_shape.get("input", {}).get("target")
    required_params, optional_params, request_body = _extract_http_bindings(
        input_ref, traits["smithy.api#http"], shapes
    )

    # Extract output
    output_ref = op_shape.get("output", {}).get("target")
    response_schemas = _extract_operation_output(output_ref, shapes, status_code)

    # Extract errors
    error_refs = op_shape.get("errors", [])
    error_schemas = _extract_operation_errors(error_refs, shapes)

    return Endpoint(
        method=method,
        path=uri_pattern,
        summary=summary,
        required_params=required_params if required_params else [],
        optional_params=optional_params if optional_params else [],
        request_body=request_body if request_body else [],
        response_schemas=response_schemas if response_schemas else [],
        error_schemas=error_schemas if error_schemas else [],
    )


def _extract_operation_output(
    output_ref: Optional[str],
    shapes: dict,
    default_status: int = 200,
) -> list[ResponseSchema]:
    """Build response schema from output structure."""
    if not output_ref or output_ref not in shapes:
        return []

    output_shape = shapes[output_ref]

    # Convert structure to response fields
    response_fields = _structure_to_response_fields(output_shape, shapes)

    if not response_fields:
        return []

    return [ResponseSchema(
        status_code=str(default_status),
        fields=response_fields,
    )]


def _extract_operation_errors(error_refs: list, shapes: dict) -> list[ErrorSchema]:
    """Extract error codes and types from error shapes."""
    error_schemas = []

    for error_ref in error_refs:
        error_id = error_ref.get("target", error_ref) if isinstance(error_ref, dict) else error_ref

        if error_id not in shapes:
            continue

        error_shape = shapes[error_id]
        traits = error_shape.get("traits", {})

        # Get HTTP status code from @httpError trait
        code = str(traits.get("smithy.api#httpError", 500))

        # Get error type from shape name
        error_type = error_id.split("#")[1] if "#" in error_id else error_id

        # Get description
        description = traits.get("smithy.api#documentation", "")

        error_schemas.append(ErrorSchema(
            code=code,
            type=error_type,
            description=description,
        ))

    return error_schemas


# ==============================================================================
# Phase 6: Integration & Testing (handled in __init__.py and cli/main.py)
# ==============================================================================
