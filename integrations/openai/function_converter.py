"""
Convert LAP specs to OpenAI function-calling format.

Automatically generates function definitions from LAP endpoints,
enabling direct use with OpenAI's function calling API.

Example usage:
    >>> from integrations.openai.function_converter import lap_to_functions
    >>> from lap.core.parser import parse_lap
    >>>
    >>> spec = parse_lap(open("examples/lap/openapi/petstore.lap").read())
    >>> functions = lap_to_functions(spec)
    >>> print(functions[0])
    {
        'type': 'function',
        'function': {
            'name': 'get_repos_owner_repo',
            'description': 'Get a repository',
            'parameters': {
                'type': 'object',
                'properties': {
                    'owner': {'type': 'string', 'description': 'Repository owner'},
                    'repo': {'type': 'string', 'description': 'Repository name'}
                },
                'required': ['owner', 'repo']
            }
        }
    }

    # Use with OpenAI API:
    >>> import openai
    >>> response = openai.chat.completions.create(
    ...     model="gpt-4o",
    ...     messages=[{"role": "user", "content": "List repos for octocat"}],
    ...     tools=functions
    ... )
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from lap.core.formats.lap import LAPSpec, Endpoint, Param


# LAP type → JSON Schema type mapping
_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "num": "number",
    "bool": "boolean",
    "map": "object",
    "any": "string",
}


def _lap_type_to_json_schema(type_str: str) -> dict[str, Any]:
    """Convert a LAP type string to JSON Schema."""
    # Array: [inner]
    if type_str.startswith("[") and type_str.endswith("]"):
        inner = type_str[1:-1]
        return {"type": "array", "items": _lap_type_to_json_schema(inner)}

    # Type with format: str(email), int(unix-timestamp)
    m = re.match(r"^(\w+)\(([^)]+)\)$", type_str)
    if m:
        base, fmt = m.group(1), m.group(2)
        schema = _lap_type_to_json_schema(base)
        # Map common formats
        if fmt in ("email", "uri", "date-time", "date", "uuid"):
            schema["format"] = fmt
        return schema

    return {"type": _TYPE_MAP.get(type_str, "string")}


def _param_to_property(param: Param) -> dict[str, Any]:
    """Convert a LAP Param to a JSON Schema property."""
    prop = _lap_type_to_json_schema(param.type)
    if param.description:
        prop["description"] = param.description
    if param.enum:
        prop["enum"] = param.enum
    if param.default is not None:
        prop["default"] = param.default
    return prop


def _endpoint_to_function_name(endpoint: Endpoint) -> str:
    """Generate a function name from method + path.

    Examples:
        GET /repos/{owner}/{repo} → get_repos_owner_repo
        POST /issues → post_issues
    """
    # Remove braces and clean path
    clean = endpoint.path.strip("/")
    clean = re.sub(r"\{(\w+)\}", r"\1", clean)
    clean = re.sub(r"[^a-zA-Z0-9/]", "_", clean)
    parts = [p for p in clean.split("/") if p]
    name = endpoint.method.lower() + "_" + "_".join(parts)
    # Ensure valid function name
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:64]  # OpenAI has a 64-char limit


def endpoint_to_function(endpoint: Endpoint, api_name: str = "") -> dict[str, Any]:
    """Convert a single LAP endpoint to an OpenAI function tool definition.

    Returns a dict in the OpenAI tools format:
    {'type': 'function', 'function': {'name': ..., 'description': ..., 'parameters': ...}}
    """
    all_params = (
        endpoint.required_params
        + endpoint.optional_params
        + endpoint.request_body
    )

    properties = {}
    required = []

    for param in all_params:
        properties[param.name] = _param_to_property(param)
        if param.required:
            required.append(param.name)

    parameters: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        parameters["required"] = required

    description = endpoint.summary or f"{endpoint.method.upper()} {endpoint.path}"
    if api_name:
        description = f"[{api_name}] {description}"

    return {
        "type": "function",
        "function": {
            "name": _endpoint_to_function_name(endpoint),
            "description": description,
            "parameters": parameters,
        },
    }


def lap_to_functions(spec: LAPSpec) -> list[dict[str, Any]]:
    """Convert all endpoints in a LAP spec to OpenAI function definitions.

    Args:
        spec: A parsed LAPSpec object

    Returns:
        List of OpenAI tool definitions ready for the `tools` parameter
    """
    return [
        endpoint_to_function(ep, api_name=spec.api_name)
        for ep in spec.endpoints
    ]
