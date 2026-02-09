# LAP MCP Integration — Phase 2 Results

## TL;DR

**ToolLean achieves 48.7% token savings vs pretty-printed JSON Schema and 35.4% vs compact JSON**, with 100% round-trip fidelity across all 6 tested MCP servers.

Phase 1's description-only compression got 3.7%. The real waste is in JSON Schema's structural overhead — and ToolLean eliminates it.

## Token Comparison (cl100k_base)

| MCP Server | Tools | JSON (pretty) | JSON (compact) | ToolLean | Savings vs Pretty | Savings vs Compact |
|------------|------:|---------------:|---------------:|---------:|-------------------:|-------------------:|
| brave-search | 6 | 1,403 | 1,154 | 797 | **43.2%** | 30.9% |
| filesystem | 14 | 764 | 615 | 427 | **44.1%** | 30.6% |
| github | 8 | 1,778 | 1,388 | 831 | **53.3%** | 40.1% |
| memory | 9 | 470 | 371 | 243 | **48.3%** | 34.5% |
| postgres | 8 | 1,369 | 1,068 | 669 | **51.1%** | 37.4% |
| slack | 9 | 1,596 | 1,265 | 822 | **48.5%** | 35.0% |
| **TOTAL** | **54** | **7,380** | **5,861** | **3,789** | **48.7%** | **35.4%** |

### With description compression (lean mode)

| | Tokens | Savings vs Pretty |
|--|-------:|-------------------:|
| ToolLean (full) | 3,789 | 48.7% |
| ToolLean (lean) | 2,701 | 63.4% |

## Where the Savings Come From

The JSON Schema tax per parameter:
```json
"owner": {
  "type": "string",
  "description": "Repository owner"
}
```
→ ToolLean: `@in owner:str Repository owner`

That's **~10 tokens → ~5 tokens per parameter**. Multiply by dozens of parameters across a server's tools and it adds up fast.

Additional structural overhead eliminated:
- `"type": "object"`, `"properties": {}`, `"required": []` wrappers per tool
- `"inputSchema"` nesting
- JSON punctuation: braces, colons, commas, quotes

## Example: Before & After

### Before (JSON Schema — 2 GitHub tools, 484 tokens)

```json
{
  "name": "github",
  "tools": [
    {
      "name": "create_or_update_file",
      "description": "Create or update a single file in a GitHub repository...",
      "inputSchema": {
        "type": "object",
        "properties": {
          "owner": {
            "type": "string",
            "description": "Repository owner (username or organization)"
          },
          "repo": {
            "type": "string",
            "description": "Repository name"
          },
          ...5 more params...
        },
        "required": ["owner", "repo", "path", "content", "message"]
      }
    },
    ...
  ]
}
```

### After (ToolLean — same 2 tools, 243 tokens)

```
# github
# MCP server for GitHub API integration

@toollean v0.1
@tool create_or_update_file
@desc Create or update a single file in a GitHub repository...
@in owner:str Repository owner (username or organization)
@in repo:str Repository name
@in path:str Path where to create/update the file
@in content:str Content of the file (will be base64 encoded automatically)
@in message:str Commit message
@in branch:str? Branch to create/update the file in (defaults to repo's default branch)
@in sha:str? SHA of the file being replaced (required when updating existing files)

@toollean v0.1
@tool search_repositories
@desc Search for GitHub repositories...
@in query:str Search query (supports GitHub search syntax)
@in page:int? Page number for pagination (default: 1)
@in perPage:int? Number of results per page, max 100 (default: 30)
```

## Round-Trip Fidelity

The LAP MCP Proxy can reconstruct the original JSON Schema from ToolLean with **100% fidelity**:

| Server | Tools | Fidelity | Issues |
|--------|------:|---------:|--------|
| brave-search | 6 | ✓ 100% | None |
| filesystem | 14 | ✓ 100% | None |
| github | 8 | ✓ 100% | None |
| memory | 9 | ✓ 100% | None |
| postgres | 8 | ✓ 100% | None |
| slack | 9 | ✓ 100% | None |

All parameter names, types, required flags, descriptions, and enums survive the round trip.

## Architecture: LAP MCP Proxy

```
MCP Server → tools/list JSON → [LAP Proxy] → ToolLean text → LLM
                                     ↓
                              Stored ToolLean
                                     ↓
LLM → tools/call → [LAP Proxy] → JSON Schema validation → MCP Server
```

The proxy is transparent: MCP servers don't need changes, LLMs see compressed tool listings, and tool calls work normally.

See: `lap_mcp_proxy.py`

## Honest Assessment

**The good:**
- 35-53% token savings are real and meaningful
- Higher savings for parameter-rich tools (github: 53%)
- 100% round-trip fidelity — no information loss
- Format is LLM-friendly (structured text, clear semantics)
- Works as a drop-in proxy, no MCP protocol changes needed

**The caveats:**
- Savings are on the **tool discovery** portion of context, not the entire conversation
- For a typical session with 10 MCP tools, we're saving ~1,000-2,000 tokens
- At $3/MTok (Claude Sonnet), that's ~$0.003-0.006 per session — negligible cost savings
- The real value is **context window budget**: those saved tokens can hold more conversation

**Where this matters most:**
- Agents with 50+ tools (e.g., full MCP ecosystem with multiple servers)
- Context-constrained models (8K-32K windows)
- High-volume agent deployments where tokens × sessions = real money

## Files

- `phase2_measure.py` — Token measurement script
- `lap_mcp_proxy.py` — MCP proxy with ToolLean compression + round-trip reconstruction
- `phase2_data.json` — Raw measurement data
- `phase2_example_before.json` / `phase2_example_after.txt` — Full before/after examples
