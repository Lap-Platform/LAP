"""
AWS SDK JSON compiler for LAP format.

Compiles AWS SDK service definitions (used by aws-sdk-js and other AWS SDKs) into LAP format.
This format is different from standard Smithy - it's AWS's proprietary service definition format.

AWS SDK JSON structure:
- version: "2.0" (optional, absent in newer specs)
- metadata: {apiVersion, serviceFullName, protocol, signatureVersion, etc.}
- operations: {OperationName: {name, http, input, output, errors}}
- shapes: {ShapeName: {type, members, required, etc.}}

AWS SDK → LAP mapping:
- metadata → LAPSpec (api_name, version, auth_scheme)
- operations → Endpoints (method, path from http trait)
- shapes → Parameters and response schemas
"""

import json
from pathlib import Path
from typing import Optional

from lap.core.formats.lap import (
    LAPSpec,
    Endpoint,
    Param,
    ResponseSchema,
    ResponseField,
    ErrorSchema,
)
from lap.core.utils import read_file_safe, strip_html


# AWS SDK scalar types → LAP types
_AWS_SDK_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "long": "int(i64)",
    "boolean": "bool",
    "double": "num(f64)",
    "float": "num(f32)",
    "timestamp": "str(timestamp)",
    "blob": "bytes",
}


def compile_aws_sdk(spec_path: str) -> LAPSpec:
    """
    Main entry point for AWS SDK JSON compilation.

    Args:
        spec_path: Path to AWS SDK JSON file

    Returns:
        LAPSpec object ready for .to_lap() conversion

    Raises:
        ValueError: If spec is invalid
    """
    path = Path(spec_path)

    if not path.is_file() or path.suffix != ".json":
        raise ValueError(f"AWS SDK format requires a .json file, got: {spec_path}")

    # Load and validate JSON
    model = _load_aws_sdk_json(path)

    # Extract service metadata
    metadata = model.get("metadata", {})
    api_name = metadata.get("serviceFullName", metadata.get("serviceId", "UnknownService"))
    version = metadata.get("apiVersion", "")
    auth_scheme = _extract_auth_scheme(metadata)

    # Build shape index
    shapes = model.get("shapes", {})

    # Convert operations to endpoints
    endpoints = []
    operations = model.get("operations", {})

    for op_name, op_def in operations.items():
        endpoint = _operation_to_endpoint(op_name, op_def, shapes)
        if endpoint:  # Only include HTTP-bound operations
            endpoints.append(endpoint)

    return LAPSpec(
        api_name=api_name,
        version=version,
        auth_scheme=auth_scheme,
        endpoints=endpoints,
    )


def _load_aws_sdk_json(path: Path) -> dict:
    """Load and validate AWS SDK JSON file."""
    try:
        content = read_file_safe(str(path))
        if content is None:
            raise ValueError(f"Could not read file: {path}")
        model = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")

    # Validate AWS SDK JSON structure
    # Accept either version "2.0" or metadata-based (newer specs omit version key)
    version = model.get("version")
    meta = model.get("metadata")
    has_version = version == "2.0"
    has_meta = isinstance(meta, dict) and "apiVersion" in meta and "protocol" in meta
    if not has_version and not has_meta:
        raise ValueError(
            f"Not a valid AWS SDK JSON: expected version '2.0' or metadata with apiVersion/protocol, "
            f"got version={version!r}"
        )
    if "shapes" not in model:
        raise ValueError(f"Not a valid AWS SDK JSON: missing 'shapes' field")
    if "operations" not in model:
        raise ValueError(f"Not a valid AWS SDK JSON: missing 'operations' field")

    return model


def _extract_auth_scheme(metadata: dict) -> str:
    """Extract authentication scheme from metadata."""
    # Check signatureVersion
    sig_version = metadata.get("signatureVersion", "")
    if sig_version == "v4":
        return "AWS SigV4"

    # Check auth array
    auth = metadata.get("auth", [])
    if "aws.auth#sigv4" in auth:
        return "AWS SigV4"

    return ""


def _aws_sdk_type_to_lap(shape_name: str, shapes: dict, visited: set = None) -> str:
    """
    Convert AWS SDK type to LAP type string.

    Args:
        shape_name: Shape name reference
        shapes: Shape definitions
        visited: Set of visited shapes (for cycle detection)

    Returns:
        LAP type string
    """
    if visited is None:
        visited = set()

    # Cycle detection
    if shape_name in visited:
        return "any"

    if shape_name not in shapes:
        return "any"

    shape = shapes[shape_name]
    shape_type = shape.get("type", "")

    visited_copy = visited | {shape_name}

    # Primitive types
    if shape_type in _AWS_SDK_TYPE_MAP:
        return _AWS_SDK_TYPE_MAP[shape_type]

    # List type
    if shape_type == "list":
        member_name = shape.get("member", {}).get("shape", "string")
        element_type = _aws_sdk_type_to_lap(member_name, shapes, visited_copy)
        return f"[{element_type}]"

    # Map type
    if shape_type == "map":
        key_name = shape.get("key", {}).get("shape", "string")
        value_name = shape.get("value", {}).get("shape", "string")
        key_type = _aws_sdk_type_to_lap(key_name, shapes, visited_copy)
        value_type = _aws_sdk_type_to_lap(value_name, shapes, visited_copy)
        return f"map<{key_type},{value_type}>"

    # Structure type
    if shape_type == "structure":
        return shape_name

    # Default
    return "any"


def _structure_to_response_fields(shape_name: str, shapes: dict, depth: int = 0, visited: set = None) -> list[ResponseField]:
    """Convert structure to nested response fields."""
    if visited is None:
        visited = set()

    if depth > 3 or shape_name in visited:
        return []

    if shape_name not in shapes:
        return []

    shape = shapes[shape_name]
    if shape.get("type") != "structure":
        return []

    members = shape.get("members", {})
    required_set = set(shape.get("required", []))
    fields = []

    for member_name, member_def in members.items():
        member_shape = member_def.get("shape", "string")
        nullable = member_name not in required_set

        # Get type
        field_type = _aws_sdk_type_to_lap(member_shape, shapes, visited)

        # Check if nested structure
        children = []
        if member_shape in shapes:
            target_shape = shapes[member_shape]
            if target_shape.get("type") == "structure":
                visited_copy = visited | {shape_name}
                children = _structure_to_response_fields(
                    member_shape, shapes, depth + 1, visited_copy
                )

        fields.append(ResponseField(
            name=member_name,
            type=field_type,
            nullable=nullable,
            children=children,
        ))

    return fields


def _extract_operation_params(input_shape_name: Optional[str], http_config: dict, shapes: dict) -> tuple[list[Param], list[Param], list[Param]]:
    """Extract parameters from operation input."""
    if not input_shape_name or input_shape_name not in shapes:
        return [], [], []

    input_shape = shapes[input_shape_name]
    members = input_shape.get("members", {})
    required_set = set(input_shape.get("required", []))

    required_params = []
    optional_params = []
    body_fields = []

    # Get URI pattern to identify path parameters
    uri = http_config.get("requestUri", "/")
    path_params = set()
    import re
    path_params = set(re.findall(r'\{(\w+)\}', uri))

    for member_name, member_def in members.items():
        member_shape = member_def.get("shape", "string")
        location = member_def.get("location", "")
        location_name = member_def.get("locationName", member_name)
        required = member_name in required_set
        field_type = _aws_sdk_type_to_lap(member_shape, shapes)

        # Classify by location
        if location == "uri" or member_name in path_params:
            # Path parameter (always required)
            required_params.append(Param(
                name=member_name,
                type=field_type,
                description="",
                required=True,
            ))
        elif location == "querystring":
            # Query parameter
            param = Param(
                name=location_name,
                type=field_type,
                description="",
                required=required,
            )
            if required:
                required_params.append(param)
            else:
                optional_params.append(param)
        elif location == "header":
            # Header parameter
            param = Param(
                name=location_name,
                type=field_type,
                description="",
                required=required,
            )
            if required:
                required_params.append(param)
            else:
                optional_params.append(param)
        else:
            # Body field
            body_fields.append(Param(
                name=member_name,
                type=field_type,
                description="",
                required=required,
            ))

    return required_params, optional_params, body_fields


def _operation_to_endpoint(op_name: str, op_def: dict, shapes: dict) -> Optional[Endpoint]:
    """Convert AWS SDK operation to LAP Endpoint."""
    http_config = op_def.get("http", {})

    # Extract HTTP method and URI
    method = http_config.get("method", "POST")
    path = http_config.get("requestUri", "/")

    # Extract documentation
    summary = op_def.get("documentation", "")
    if summary:
        summary = strip_html(summary).strip()

    # Extract input parameters
    input_shape = op_def.get("input", {}).get("shape")
    required_params, optional_params, request_body = _extract_operation_params(
        input_shape, http_config, shapes
    )

    # Extract output
    output_shape = op_def.get("output", {}).get("shape")
    response_schemas = []
    if output_shape and output_shape in shapes:
        response_fields = _structure_to_response_fields(output_shape, shapes)
        if response_fields:
            response_schemas.append(ResponseSchema(
                status_code="200",
                fields=response_fields,
            ))

    # Extract errors
    error_schemas = []
    errors = op_def.get("errors", [])
    for error in errors:
        error_shape = error.get("shape", "")
        if error_shape in shapes:
            error_def = shapes[error_shape]
            # Try to get HTTP status code
            # AWS SDK doesn't always include this, default to 400 for client errors, 500 for server errors
            code = "400" if "Client" in error_shape else "500"
            description = error_def.get("documentation", "")
            if description:
                description = strip_html(description).strip()

            error_schemas.append(ErrorSchema(
                code=code,
                type=error_shape,
                description=description,
            ))

    return Endpoint(
        method=method,
        path=path,
        summary=summary,
        required_params=required_params if required_params else [],
        optional_params=optional_params if optional_params else [],
        request_body=request_body if request_body else [],
        response_schemas=response_schemas if response_schemas else [],
        error_schemas=error_schemas if error_schemas else [],
    )
