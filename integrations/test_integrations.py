#!/usr/bin/env python3
"""
Tests for all LAP integrations — works WITHOUT any framework installed.
Tests the conversion logic, not the framework wrappers.
"""

import sys
from pathlib import Path

# Ensure src is importable

from core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema


def _make_test_spec() -> LAPSpec:
    """Create a minimal test spec."""
    return LAPSpec(
        api_name="TestAPI",
        base_url="https://api.test.com/v1",
        version="1.0",
        auth_scheme="Bearer token",
        endpoints=[
            Endpoint(
                method="get",
                path="/users/{id}",
                summary="Get a user by ID",
                required_params=[Param(name="id", type="int", required=True, description="User ID")],
                optional_params=[Param(name="fields", type="str", description="Comma-separated fields")],
                response_schemas=[ResponseSchema(
                    status_code="200",
                    description="Success",
                    fields=[
                        ResponseField(name="id", type="int"),
                        ResponseField(name="name", type="str"),
                        ResponseField(name="email", type="str", nullable=True),
                    ],
                )],
                error_schemas=[ErrorSchema(code="404", description="User not found")],
            ),
            Endpoint(
                method="post",
                path="/users",
                summary="Create a new user",
                required_params=[
                    Param(name="name", type="str", required=True, description="User name"),
                    Param(name="email", type="str(email)", required=True, description="Email address"),
                ],
                optional_params=[
                    Param(name="role", type="str", enum=["admin", "user", "guest"], default="user"),
                ],
            ),
            Endpoint(
                method="get",
                path="/users",
                summary="List all users",
                optional_params=[
                    Param(name="limit", type="int", default="20"),
                    Param(name="offset", type="int", default="0"),
                ],
            ),
        ],
    )


def test_langchain_loader():
    """Test LangChain document loader conversion."""
    from langchain.lap_loader import LAPLoader, LAPRetriever

    spec = _make_test_spec()
    loader = LAPLoader(spec=spec)
    docs = loader.load()

    assert len(docs) == 3, f"Expected 3 docs, got {len(docs)}"
    assert docs[0].metadata["api"] == "TestAPI"
    assert docs[0].metadata["method"] == "GET"
    assert docs[0].metadata["path"] == "/users/{id}"
    assert docs[0].metadata["params_count"] == 2  # 1 required + 1 optional
    assert "@endpoint GET /users/{id}" in docs[0].page_content

    # Test retriever
    retriever = LAPRetriever(spec=spec)
    results = retriever.get_relevant_documents("create user")
    assert len(results) > 0
    assert any("POST" in d.metadata["method"] for d in results)

    # Search by path keyword
    results = retriever.get_relevant_documents("users")
    assert len(results) == 3  # All endpoints match

    print("  ✅ LangChain loader & retriever")


def test_crewai_tool():
    """Test CrewAI tool lookup."""
    from crewai.lap_tool import LAPLookup

    spec = _make_test_spec()
    tool = LAPLookup()
    tool.add_spec("testapi", spec)

    # Full spec lookup
    result = tool._run("testapi")
    assert "@api TestAPI" in result
    assert "@endpoint GET /users/{id}" in result

    # Filtered by endpoint
    result = tool._run("testapi", endpoint="users/{id}")
    assert "GET /users/{id}" in result
    assert "POST /users" not in result  # Should not include create

    # Not found
    result = tool._run("nonexistent")
    assert "not found" in result.lower()

    # Fuzzy match
    result = tool._run("test")
    assert "@api TestAPI" in result

    print("  ✅ CrewAI tool")


def test_openai_functions():
    """Test OpenAI function-calling conversion."""
    from openai.function_converter import lap_to_functions, endpoint_to_function

    spec = _make_test_spec()
    functions = lap_to_functions(spec)

    assert len(functions) == 3
    
    # Check structure
    f0 = functions[0]
    assert f0["type"] == "function"
    assert "name" in f0["function"]
    assert "parameters" in f0["function"]
    assert f0["function"]["parameters"]["type"] == "object"

    # Check GET /users/{id}
    assert f0["function"]["name"] == "get_users_id"
    props = f0["function"]["parameters"]["properties"]
    assert "id" in props
    assert props["id"]["type"] == "integer"
    assert "fields" in props
    assert f0["function"]["parameters"]["required"] == ["id"]

    # Check POST /users
    f1 = functions[1]
    assert f1["function"]["name"] == "post_users"
    props = f1["function"]["parameters"]["properties"]
    assert "name" in props
    assert "email" in props
    assert "role" in props
    assert props["role"]["enum"] == ["admin", "user", "guest"]
    assert props["role"]["default"] == "user"
    assert set(f1["function"]["parameters"]["required"]) == {"name", "email"}

    # Description includes API name
    assert "[TestAPI]" in f1["function"]["description"]

    print("  ✅ OpenAI function converter")


def test_mcp_server():
    """Test MCP server tool generation."""
    from mcp.lap_mcp_server import LAPMCPServer, endpoint_to_mcp_tool

    spec = _make_test_spec()
    server = LAPMCPServer()
    server.add_spec(spec)

    tools = server.list_tools()
    assert len(tools) == 3

    # Check tool structure
    t0 = tools[0]
    assert "name" in t0
    assert "description" in t0
    assert "inputSchema" in t0
    assert t0["inputSchema"]["type"] == "object"
    assert "id" in t0["inputSchema"]["properties"]

    # Check tool naming includes API prefix
    assert "testapi" in t0["name"]

    # Test call_tool
    result = server.call_tool(t0["name"], {"id": 42})
    assert "content" in result
    assert "isError" not in result

    # Unknown tool
    result = server.call_tool("nonexistent")
    assert result["isError"] is True

    # Test manifest
    manifest = server.to_mcp_manifest()
    assert manifest["name"] == "lap-lap-server"
    assert len(manifest["tools"]) == 3

    print("  ✅ MCP server")


if __name__ == "__main__":
    print("Testing LAP integrations (no frameworks required):\n")
    test_langchain_loader()
    test_crewai_tool()
    test_openai_functions()
    test_mcp_server()
    print("\n🎉 All integration tests passed!")
