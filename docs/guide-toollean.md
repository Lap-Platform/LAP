# LAP — Compressed AI Tool Manifests

**Part of the LAP (Lean API Platform)**

LAP is a compact, structured format for describing AI tools and skills. Think of it as LAP for tool manifests — optimized for LLM agent discovery, understanding, and invocation.

## Why LAP?

AI agents discover tools from many sources: MCP servers, OpenClaw skills, Claude tools, custom APIs. Each has its own format. LAP provides a universal compressed representation that:

- **Saves tokens** — compact syntax vs verbose JSON schemas
- **Is parseable** — round-trips cleanly to/from structured data
- **Is universal** — works for any tool source
- **Is readable** — humans and LLMs both understand it instantly

## Format Specification

### Header

```
@lap v0.1
```

Every LAP document starts with a version header.

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

| LAP | JSON Schema | Notes |
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
@lap v0.1
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

## Compiling to LAP

### From MCP Tool Manifest

```python
from lap_compiler import compile_mcp_file

bundle = compile_mcp_file("mcp-server-tools.json")
print(bundle.to_lap())
```

### From OpenClaw SKILL.md

```python
from lap_compiler import compile_skill_file

spec = compile_skill_file("SKILL.md")
print(spec.to_lap())
```

### From Generic JSON

```python
from lap_compiler import compile_generic_json

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
print(spec.to_lap())
```

## Parsing LAP

```python
from lap_parser import parse_lap_tools, parse_single_tool

# Parse a file with multiple tools
bundle = parse_lap_tools(open("tools.lap").read())
for tool in bundle.tools:
    print(f"{tool.name}: {len(tool.inputs)} params")

# Parse a single tool
tool = parse_single_tool(text)
```

## CLI Usage

These commands are available via the standalone tool script (`lap/core/compilers/lap_tools_advanced.py`):

```bash
# Compile from various sources
python -m lap.core.compilers.lap_tools_advanced compile-mcp manifest.json -o tools.lap
python -m lap.core.compilers.lap_tools_advanced compile-skill SKILL.md -o skill.lap
python -m lap.core.compilers.lap_tools_advanced compile-json tool.json -o tool.lap

# Parse and inspect
python -m lap.core.compilers.lap_tools_advanced parse tools.lap
python -m lap.core.compilers.lap_tools_advanced stats tools.lap

# Maximum compression (strip descriptions)
python -m lap.core.compilers.lap_tools_advanced compile-mcp manifest.json --lean
```

## Multi-Tool Bundles

Multiple tools in one file (e.g., an MCP server with many tools):

```
# Filesystem Server
# File operations for the local filesystem

@lap v0.1
@tool read_file
@desc Read complete contents of a file
@in path:str File path to read

@lap v0.1
@tool write_file
@desc Create or overwrite a file
@in path:str File path to write
@in content:str Content to write
```

## Comparison: JSON vs LAP

**MCP JSON (267 bytes):**
```json
{"name":"read_file","description":"Read complete contents of a file from the filesystem","inputSchema":{"type":"object","properties":{"path":{"type":"string","description":"The path of the file to read"}},"required":["path"]}}
```

**LAP (120 bytes, 55% smaller):**
```
@lap v0.1
@tool read_file
@desc Read complete contents of a file from the filesystem
@in path:str The path of the file to read
```

## Relationship to LAP

LAP compresses **API documentation** (endpoints, request/response schemas).
LAP compresses **tool manifests** (what a tool does, its inputs/outputs).

They're complementary: a tool might use LAP for its underlying API docs, and LAP for its agent-facing manifest.
