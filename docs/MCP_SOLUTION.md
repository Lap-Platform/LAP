# LAP ↔ MCP Solution Architecture

## The Problem

MCP servers today expose tools with verbose, uncompressed documentation. A typical MCP server for a large API (Stripe, GitHub, Snyk) sends the full tool manifest — names, descriptions, JSON Schema — to the LLM on every interaction. This creates two problems:

1. **Token bloat in tool descriptions**: Each `tools/list` response dumps the full schema into the LLM context. For a 50-endpoint API, that's 10-100KB of JSON Schema — repeated every turn.
2. **Verbose tool results**: `tools/call` responses often return full JSON blobs, human-readable error messages, and documentation-style text that could be compressed.

LAP (via LAP and LAP) already solves this for API documentation. The MCP integration bridges these two worlds.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        LLM Host                              │
│  (Claude Desktop, Cursor, OpenClaw, custom app)              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    MCP Client                         │   │
│  │  Receives tool definitions, sends tool calls          │   │
│  └──────┬───────────────────────────────────┬───────────┘   │
│         │ JSON-RPC (stdio/SSE/HTTP)          │               │
└─────────┼───────────────────────────────────┼───────────────┘
          │                                    │
          ▼                                    ▼
┌──────────────────┐              ┌──────────────────────┐
│ Standard MCP     │              │ LAP-Enhanced MCP     │
│ Server           │              │ Server (Proxy)       │
│                  │              │                      │
│ tools/list →     │              │ tools/list →         │
│  verbose JSON    │              │  LAP-compressed │
│  Schema          │              │  descriptions        │
│                  │              │                      │
│ tools/call →     │              │ tools/call →         │
│  full response   │              │  LAP-compressed  │
│                  │              │  response            │
└──────────────────┘              └──────────┬───────────┘
                                             │
                                    ┌────────▼────────┐
                                    │ LAP Compiler     │
                                    │                  │
                                    │ LAP: tool   │
                                    │  manifests       │
                                    │ LAP: API     │
                                    │  docs/responses  │
                                    └──────────────────┘
```

---

## Two Modes of Operation

### Mode 1: LAP Proxy Server (wraps existing MCP servers)

A transparent MCP proxy that sits between the host and any standard MCP server. It intercepts `tools/list` and `tools/call` messages, compressing them via LAP.

```
Host ←→ [LAP Proxy MCP Server] ←→ [Original MCP Server]
```

**How it works:**
1. On `tools/list`: Fetches tools from upstream, compiles each tool's description + inputSchema → LAP format, returns compressed tool definitions
2. On `tools/call`: Passes through to upstream, optionally compresses the response via LAP
3. On `initialize`: Negotiates capabilities with both host and upstream

**Key design decisions:**
- The proxy is **stateful** — it caches the LAP-compiled manifests and refreshes on `notifications/tools/list_changed`
- Tool names pass through unchanged (the proxy is transparent to the host)
- inputSchema stays as JSON Schema (MCP spec requires it) but descriptions get compressed
- The **real savings** come from description compression + response compression

### Mode 2: Native LAP MCP Server (serves pre-compiled specs)

A standalone MCP server that directly serves LAP/LAP specs as tools. No upstream server needed.

```
Host ←→ [LAP Native MCP Server] ← reads → [.lap / .lap files]
```

**How it works:**
1. Loads pre-compiled `.lap` and `.lap` files at startup
2. Each endpoint/tool becomes an MCP tool with compressed descriptions
3. `tools/call` returns the lean documentation needed to make the actual API call

**Use case:** When you have API specs and want to serve them efficiently to any MCP-compatible host, without an existing MCP server.

---

## What Gets Compressed (and What Doesn't)

### LAP compression targets (tool manifest):

| Field | Standard MCP | LAP-Enhanced | Savings |
|-------|-------------|-------------|---------|
| `description` | Full prose: "This tool allows you to retrieve detailed information about a specific repository, including its name, description, stars, forks, and other metadata." | "Get repo details: name, desc, stars, forks, metadata" | ~60-70% |
| `inputSchema.properties.*.description` | "The owner of the repository. This should be the GitHub username or organization name." | "Repo owner (username/org)" | ~50-60% |
| Enum descriptions | Full sentences per option | Compact `type(opt1/opt2/opt3)` | ~70-80% |

### What stays as-is:
- `name` — MCP spec requires it, already compact
- `inputSchema.type` / `required` / structural JSON Schema — must remain valid JSON Schema
- `title` — short already

### Response compression targets (tool results):

| Content | Standard | LAP-Enhanced | Savings |
|---------|----------|-------------|---------|
| Error messages | Full prose + stack traces | Structured error codes + lean descriptions | ~50% |
| API documentation in results | Raw OpenAPI/markdown | LAP format | 50-95% (proven in benchmarks) |
| JSON data responses | Pass-through | Pass-through (no compression — it's data, not docs) | 0% |

---

## Detailed Component Design

### 1. LAP Proxy Server (`lap_mcp_proxy.py`)

```python
class LAPProxyServer:
    """MCP server that proxies another MCP server with LAP compression."""
    
    def __init__(self, upstream_command: list[str], compression_level: str = "balanced"):
        self.upstream = None  # MCP client connection to upstream
        self.tool_cache = {}  # name → (original_tool, compressed_tool)
        self.compression = compression_level  # "lean" | "balanced" | "verbose"
    
    # --- MCP Server interface (what the host sees) ---
    
    async def handle_list_tools(self, cursor=None) -> dict:
        """Intercepts tools/list, returns compressed tool definitions."""
        upstream_tools = await self.upstream.list_tools(cursor)
        compressed = []
        for tool in upstream_tools:
            compressed_tool = self.compress_tool_manifest(tool)
            self.tool_cache[tool["name"]] = (tool, compressed_tool)
            compressed.append(compressed_tool)
        return {"tools": compressed}
    
    async def handle_call_tool(self, name: str, arguments: dict) -> dict:
        """Passes tool call to upstream, optionally compresses response."""
        result = await self.upstream.call_tool(name, arguments)
        if self.compression != "verbose":
            result = self.compress_tool_result(result)
        return result
    
    # --- Compression ---
    
    def compress_tool_manifest(self, tool: dict) -> dict:
        """Compress a tool's descriptions using LAP."""
        compressed = tool.copy()
        # Compress top-level description
        compressed["description"] = compile_description_lean(tool["description"])
        # Compress parameter descriptions within inputSchema
        if "properties" in tool.get("inputSchema", {}):
            compressed["inputSchema"] = compress_schema_descriptions(
                tool["inputSchema"]
            )
        return compressed
    
    def compress_tool_result(self, result: dict) -> dict:
        """Compress text content in tool results."""
        compressed_content = []
        for item in result.get("content", []):
            if item["type"] == "text":
                compressed_content.append({
                    "type": "text",
                    "text": compile_text_lean(item["text"])
                })
            else:
                compressed_content.append(item)  # images, audio pass through
        return {**result, "content": compressed_content}
```

### 2. Native LAP Server (`lap_mcp_native.py`)

```python
class LAPNativeServer:
    """MCP server that serves pre-compiled LAP/LAP specs."""
    
    def __init__(self, specs_dir: str):
        self.specs = {}       # api_name → LAPSpec
        self.tools = []       # MCP tool definitions
        self.tool_map = {}    # tool_name → (spec, endpoint)
        self.load_specs(specs_dir)
    
    def load_specs(self, specs_dir: str):
        """Load .lap and .lap files."""
        for f in Path(specs_dir).glob("*.lap"):
            spec = parse_lap(f.read_text())
            self.register_spec(spec)
        for f in Path(specs_dir).glob("*.lap"):
            bundle = parse_lap_tools(f.read_text())
            self.register_bundle(bundle)
    
    async def handle_list_tools(self, cursor=None) -> dict:
        """Return pre-compiled tool definitions."""
        return {"tools": self.tools}
    
    async def handle_call_tool(self, name: str, arguments: dict) -> dict:
        """Return lean documentation for the endpoint."""
        spec, endpoint = self.tool_map[name]
        return {
            "content": [{
                "type": "text",
                "text": endpoint.to_lap(lean=True)
            }]
        }
```

### 3. Description Compiler (`compress.py`)

The core compression logic for tool descriptions:

```python
def compile_description_lean(description: str) -> str:
    """Compress a verbose tool description to lean format.
    
    Rules:
    1. Remove filler: "This tool allows you to", "You can use this to"
    2. Compress to verb-first imperative: "Get", "Create", "List", "Delete"
    3. Keep parameter mentions but compress: "the repository owner" → "repo owner"
    4. Preserve semantic meaning — never lose information that affects tool selection
    """
    ...

def compress_schema_descriptions(schema: dict) -> dict:
    """Compress descriptions within a JSON Schema's properties.
    
    Preserves schema validity — only touches 'description' fields.
    """
    ...
```

---

## Test Plan

### Test 1: Compression Ratio (Unit)
**Goal:** Measure token savings on real MCP tool manifests.

**Setup:**
- Collect tool manifests from 5+ popular MCP servers (filesystem, GitHub, Slack, database, web-search)
- Compile each through LAP compression
- Measure: character count, token count (tiktoken), JSON size

**Expected:** 40-60% description token reduction while preserving all semantic info.

### Test 2: Semantic Preservation (Unit)
**Goal:** Verify compressed descriptions don't lose meaning.

**Setup:**
- For each original vs compressed tool description pair:
  - Feed both to an LLM with the same task prompt
  - Compare: Does the LLM select the same tool? Does it fill the same parameters?
- Test with ambiguous tasks where description quality matters

**Expected:** 95%+ tool selection agreement between verbose and lean.

### Test 3: Proxy Round-Trip (Integration)
**Goal:** Verify the proxy correctly intercepts and compresses MCP messages.

**Setup:**
- Stand up a mock MCP server with known tool definitions
- Connect through LAP proxy
- Verify: `tools/list` returns compressed tools, `tools/call` passes through correctly
- Verify: tool names unchanged, inputSchema structurally valid

**Expected:** 100% protocol compliance, all tool calls work.

### Test 4: End-to-End Agent Benchmark (System)
**Goal:** Real LLM agent performance comparison: standard MCP vs LAP-enhanced MCP.

**Setup:**
- Same approach as our LAP benchmarks:
  - Agent A: standard MCP server (verbose tools)
  - Agent B: LAP proxy MCP server (compressed tools)
  - Same model, same tasks, same system prompt
- Tasks: real integration scenarios (file operations, API calls, data queries)
- Measure: total tokens, tool selection accuracy, task completion rate

**Expected:** 30-50% input token reduction, equivalent task accuracy.

### Test 5: Large Server Stress Test (Performance)
**Goal:** Test with a server exposing 100+ tools (realistic for enterprise APIs).

**Setup:**
- Generate a mock MCP server with 100-200 tools
- Measure: `tools/list` response size (verbose vs compressed)
- Test: LLM's ability to find the right tool in a large manifest

**Expected:** This is where LAP shines most — 100+ tool manifests are where context window pressure becomes critical.

---

## What LAP Adds to MCP (Value Proposition)

1. **Reduces context window pressure** — Fewer tokens per tool = more tools fit in context = better tool selection
2. **Transparent to hosts** — Proxy mode works with ANY MCP host (Claude Desktop, Cursor, etc.) without host modifications
3. **Composable** — Can be stacked: `Host ↔ LAP Proxy ↔ Auth Proxy ↔ MCP Server`
4. **Pre-compilation** — Native mode serves pre-optimized specs, zero runtime compilation overhead
5. **Protocol-compliant** — Returns valid JSON Schema, valid MCP messages; hosts can't tell the difference

---

## What LAP Does NOT Do

- **Replace MCP** — LAP is a compression layer, not a protocol replacement
- **Compress structured data** — JSON data responses pass through; only documentation/descriptions get compressed
- **Modify tool behavior** — Same tools, same parameters, same results; just leaner descriptions
- **Require host changes** — Works as a proxy; no changes needed in Claude Desktop, Cursor, etc.

---

## Implementation Priority

1. **Phase 1: LAP MCP Compiler** — Compile real MCP tool manifests → compressed format
2. **Phase 2: Mock Tests** — Unit + integration tests with mock servers
3. **Phase 3: Proxy Server** — Full MCP proxy with stdio transport
4. **Phase 4: Live Benchmark** — End-to-end agent comparison with real MCP servers
5. **Phase 5: Native Server** — Standalone server for pre-compiled specs

---

## File Structure

```
integrations/mcp/
├── __init__.py
├── lap_mcp_proxy.py       # Mode 1: Proxy server
├── lap_mcp_native.py      # Mode 2: Native server (existing, enhanced)
├── compress.py             # Core compression for MCP manifests
├── transport.py            # stdio/SSE transport handling
├── test_fixtures/
│   ├── filesystem_tools.json    # Real MCP tool manifests
│   ├── github_tools.json
│   ├── slack_tools.json
│   ├── database_tools.json
│   └── large_server_tools.json  # 100+ tools stress test
├── tests/
│   ├── test_compression.py      # Test 1: Compression ratio
│   ├── test_semantic.py         # Test 2: Semantic preservation
│   ├── test_proxy.py            # Test 3: Round-trip proxy
│   ├── test_benchmark.py        # Test 4: Agent benchmark
│   └── test_stress.py           # Test 5: Large server
└── README.md
```
