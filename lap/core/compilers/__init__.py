"""LAP compilers -- OpenAPI, GraphQL, AsyncAPI, Protobuf, Postman, Smithy, LAP.

Unified compile() and detect_format() for the CLI.
"""

import json
import os
from pathlib import Path

from lap.core.yaml_compat import _SafeLoaderCompat


def detect_format(spec_path: str) -> str:
    """Auto-detect API spec format from file extension and content.

    Returns one of: openapi, graphql, asyncapi, protobuf, postman, smithy.
    Raises ValueError if format cannot be determined.
    """
    p = Path(spec_path)
    ext = p.suffix.lower()

    # Extension-based detection
    if ext in (".graphql", ".gql"):
        return "graphql"
    if ext == ".proto":
        return "protobuf"
    if ext == ".smithy":
        return "smithy"
    if p.is_dir():
        # Directory with .proto files
        if list(p.glob("*.proto")):
            return "protobuf"
        # Directory with smithy-build.json
        if (p / "smithy-build.json").exists():
            return "smithy"
        raise ValueError(
            f"Directory '{spec_path}' has no .proto files or smithy-build.json. "
            "Use -f to specify the format."
        )

    # Content-based detection for YAML/JSON
    if ext in (".yaml", ".yml", ".json"):
        text = p.read_text(encoding="utf-8")
        try:
            if ext == ".json":
                data = json.loads(text)
            else:
                import yaml
                data = yaml.load(text, Loader=_SafeLoaderCompat)
        except Exception:
            raise ValueError(
                f"Cannot parse '{spec_path}' as {'JSON' if ext == '.json' else 'YAML'}. "
                "Use -f to specify the format."
            )

        if not isinstance(data, dict):
            raise ValueError(
                f"Expected a mapping in '{spec_path}', got {type(data).__name__}. "
                "Use -f to specify the format."
            )

        # Smithy JSON AST
        if "smithy" in data and "shapes" in data:
            return "smithy"

        # AsyncAPI
        if "asyncapi" in data:
            return "asyncapi"

        # OpenAPI / Swagger
        if "openapi" in data or "swagger" in data:
            return "openapi"

        # Postman Collection
        info = data.get("info", {})
        if isinstance(info, dict):
            if info.get("_postman_id"):
                return "postman"
            schema = info.get("schema", "")
            if isinstance(schema, str) and "postman" in schema.lower():
                return "postman"
        # Wrapped Postman: {"collection": {...}}
        coll = data.get("collection")
        if isinstance(coll, dict):
            coll_info = coll.get("info", {})
            if isinstance(coll_info, dict):
                schema = coll_info.get("schema", "")
                if isinstance(schema, str) and "postman" in schema.lower():
                    return "postman"

        # GraphQL introspection JSON
        if "__schema" in data:
            return "graphql"
        inner = data.get("data")
        if isinstance(inner, dict) and "__schema" in inner:
            return "graphql"

        raise ValueError(
            f"Cannot detect format of '{spec_path}'. "
            "Use -f FORMAT (openapi, graphql, asyncapi, protobuf, postman, smithy)."
        )

    raise ValueError(
        f"Unsupported file extension '{ext}' for '{spec_path}'. "
        "Use -f FORMAT (openapi, graphql, asyncapi, protobuf, postman, smithy)."
    )


def compile(spec_path: str, format: str = None):
    """Compile an API spec to LAP.

    Args:
        spec_path: Path to the spec file or directory.
        format: One of openapi, graphql, asyncapi, protobuf, postman, smithy.
                Auto-detected if None.

    Returns:
        LAPSpec, or list[LAPSpec] for protobuf directories.
    """
    if format is None:
        format = detect_format(spec_path)

    if format == "openapi":
        from lap.core.compilers.openapi import compile_openapi
        return compile_openapi(spec_path)

    if format == "graphql":
        from lap.core.compilers.graphql import compile_graphql
        return compile_graphql(spec_path)

    if format == "asyncapi":
        from lap.core.compilers.asyncapi import compile_asyncapi
        return compile_asyncapi(spec_path)

    if format == "protobuf":
        from lap.core.compilers.protobuf import compile_proto, compile_proto_dir
        if Path(spec_path).is_dir():
            return compile_proto_dir(spec_path)
        return compile_proto(spec_path)

    if format == "postman":
        from lap.core.compilers.postman import compile_postman
        return compile_postman(spec_path)

    if format == "smithy":
        from lap.core.compilers.smithy import compile_smithy
        return compile_smithy(spec_path)

    raise ValueError(f"Unknown format: {format}")
