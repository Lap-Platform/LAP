# LAP Framework Integrations

Drop-in integrations that bring LAP's compressed API documentation to popular AI frameworks.

## Integrations

### 🦜 LangChain (`langchain/lap_loader.py`)

**LAPLoader** — Load LAP specs as LangChain Documents for RAG pipelines.
- One `Document` per endpoint with metadata (api, method, path, params_count)
- **LAPRetriever** — Keyword search over endpoints

```python
from integrations.langchain.lap_loader import LAPLoader, LAPRetriever

loader = LAPLoader("specs/github.lap")
docs = loader.load()  # → List[Document], one per endpoint

retriever = LAPRetriever("specs/github.lap")
results = retriever.get_relevant_documents("create issue")
```

### 🚢 CrewAI (`crewai/lap_tool.py`)

**LAPLookup** — A CrewAI tool for API documentation lookup.
- Fuzzy API name matching
- Endpoint filtering by keyword
- Agents can self-serve API docs

```python
from integrations.crewai.lap_tool import LAPLookup

tool = LAPLookup(specs_dir="specs/")
result = tool._run("github", endpoint="repos")
```

### 🤖 OpenAI Functions (`openai/function_converter.py`)

**lap_to_functions** — Auto-generate OpenAI function-calling schemas from LAP.
- Each endpoint → one function definition
- Parameters typed and validated
- Enum and default support

```python
from integrations.openai.function_converter import lap_to_functions

functions = lap_to_functions(spec)
# Pass directly to: openai.chat.completions.create(tools=functions)
```

### 🔌 MCP Server (`mcp/lap_mcp_server.py`)

**LAPMCPServer** — Serve LAP specs as MCP tools.
- Each endpoint → one MCP tool
- Full input schema with types
- Shows LAP complementing MCP, not competing

```python
from integrations.mcp.lap_mcp_server import LAPMCPServer

server = LAPMCPServer("specs/")
tools = server.list_tools()
result = server.call_tool("github_get_repos_owner_repo", {"owner": "octocat", "repo": "hello-world"})
```

## Testing

All tests run **without** any framework installed:

```bash
cd integrations && python test_integrations.py
```

## Design Principles

- **No framework dependencies** — graceful ImportError handling with stubs
- **Import from `src/`** — reuses existing LAP parser, format, and utilities
- **One endpoint = one unit** — consistent across all integrations
- **LAP complements, not competes** — each integration shows LAP adding value to existing tools
