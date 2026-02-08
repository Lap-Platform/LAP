# ToolLean — Compressed AI Tool Manifests

**Part of the LAP (Lean Agent Protocol)**

ToolLean is a compact, structured format for describing AI tools and skills. Think of it as DocLean for tool manifests — optimized for LLM agent discovery, understanding, and invocation.

## Why ToolLean?

AI agents discover tools from many sources: MCP servers, OpenClaw skills, Claude tools, custom APIs. Each has its own format. ToolLean provides a universal compressed representation that:

- **Saves tokens** — compact syntax vs verbose JSON schemas
- **Is parseable** — round-trips cleanly to/from structured data
- **Is universal** — works for any tool source
- **Is readable** — humans and LLMs both understand it instantly

## Format Specification

### Header

```
@toollean v0.1
```

Every ToolLean document starts with a version header.

### Directives

| Directive | Required | Description |
|-----------|----------|-------------|
| `@tool <name>` | ✅ | Tool identifier |
| `@desc <text>` | ✅ | What the tool does |
| `@in <param>:<type>[?] <desc>` | | Input parameter (? = optional) |
| `@out <field>:<type> <desc>` | | Output field |
| `@auth <type>` | | Auth: none/apikey/oauth/token |
| `@tags <t1,t2>` | | Categorization tags |
| `@source <url>` | | Where to get/install it |
| `@requires <dep>` | | Dependencies (repeatable) |
| `@example [desc]` | | Usage example block |

### Types

Compact type system matching JSON Schema:

| ToolLean | JSON Schema | Notes |
|----------|-------------|-------|
| `str` | `string` | |
| `int` | `integer` | |
| `num` | `number` | |
| `bool` | `boolean` | |
| `map` | `object` | |
| `list` | `array` | |
| `[str]` | `array` of `string` | Typed arrays |
| `str(fmt)` | `string` + format | With format hint |

### Parameter Syntax

```
@in name:type description
@in name:type? description          # optional
@in name:type=default description   # with default
@in name:str(a/b/c) description     # with enum
```

### Example Blocks

```
@example Description of the example
  > {"input": "value"}
  < {"output": "result"}
```

## Complete Example

```
@toollean v0.1
@tool brave_web_search
@desc Search the web using Brave Search API
@auth apikey
@tags search,web
@source https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search
@in query:str Search query
@in count:int? Number of results (1-20)
@out results:list Search result items
@example Web search
  > {"query": "rust async runtime", "count": 5}
```

## Compiling to ToolLean

### From MCP Tool Manifest

```python
from toollean_compiler import compile_mcp_file

bundle = compile_mcp_file("mcp-server-tools.json")
print(bundle.to_toollean())
```

### From OpenClaw SKILL.md

```python
from toollean_compiler import compile_skill_file

spec = compile_skill_file("SKILL.md")
print(spec.to_toollean())
```

### From Generic JSON

```python
from toollean_compiler import compile_generic_json

spec = compile_generic_json({
    "name": "my_tool",
    "description": "Does something useful",
    "parameters": {
        "properties": {
            "input": {"type": "string", "description": "The input"}
        },
        "required": ["input"]
    }
})
print(spec.to_toollean())
```

## Parsing ToolLean

```python
from toollean_parser import parse_toollean, parse_single_tool

# Parse a file with multiple tools
bundle = parse_toollean(open("tools.toollean").read())
for tool in bundle.tools:
    print(f"{tool.name}: {len(tool.inputs)} params")

# Parse a single tool
tool = parse_single_tool(text)
```

## CLI Usage

```bash
# Compile from various sources
python toollean.py compile-mcp manifest.json -o tools.toollean
python toollean.py compile-skill SKILL.md -o skill.toollean
python toollean.py compile-json tool.json -o tool.toollean

# Parse and inspect
python toollean.py parse tools.toollean
python toollean.py stats tools.toollean

# Maximum compression (strip descriptions)
python toollean.py compile-mcp manifest.json --lean
```

## Multi-Tool Bundles

Multiple tools in one file (e.g., an MCP server with many tools):

```
# Filesystem Server
# File operations for the local filesystem

@toollean v0.1
@tool read_file
@desc Read complete contents of a file
@in path:str File path to read

@toollean v0.1
@tool write_file
@desc Create or overwrite a file
@in path:str File path to write
@in content:str Content to write
```

## Comparison: JSON vs ToolLean

**MCP JSON (267 bytes):**
```json
{"name":"read_file","description":"Read complete contents of a file from the filesystem","inputSchema":{"type":"object","properties":{"path":{"type":"string","description":"The path of the file to read"}},"required":["path"]}}
```

**ToolLean (120 bytes, 55% smaller):**
```
@toollean v0.1
@tool read_file
@desc Read complete contents of a file from the filesystem
@in path:str The path of the file to read
```

## Relationship to DocLean

DocLean compresses **API documentation** (endpoints, request/response schemas).
ToolLean compresses **tool manifests** (what a tool does, its inputs/outputs).

They're complementary: a tool might use DocLean for its underlying API docs, and ToolLean for its agent-facing manifest.
