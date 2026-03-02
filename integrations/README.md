# LAP Framework Integrations

Drop-in integrations that bring DocLean's compressed API documentation to popular AI frameworks.

## Integrations

### 🦜 LangChain (`langchain/lap_loader.py`)

**DocLeanLoader** — Load DocLean specs as LangChain Documents for RAG pipelines.
- One `Document` per endpoint with metadata (api, method, path, params_count)
- **DocLeanRetriever** — Keyword search over endpoints

```python
from integrations.langchain.lap_loader import DocLeanLoader, DocLeanRetriever

loader = DocLeanLoader("specs/github.doclean")
docs = loader.load()  # → List[Document], one per endpoint

retriever = DocLeanRetriever("specs/github.doclean")
results = retriever.get_relevant_documents("create issue")
```

### 🚢 CrewAI (`crewai/lap_tool.py`)

**DocLeanLookup** — A CrewAI tool for API documentation lookup.
- Fuzzy API name matching
- Endpoint filtering by keyword
- Agents can self-serve API docs

```python
from integrations.crewai.lap_tool import DocLeanLookup

tool = DocLeanLookup(specs_dir="specs/")
result = tool._run("github", endpoint="repos")
```

### 🤖 OpenAI Functions (`openai/function_converter.py`)

**doclean_to_functions** — Auto-generate OpenAI function-calling schemas from DocLean.
- Each endpoint → one function definition
- Parameters typed and validated
- Enum and default support

```python
from integrations.openai.function_converter import doclean_to_functions

functions = doclean_to_functions(spec)
# Pass directly to: openai.chat.completions.create(tools=functions)
```

### 🔌 MCP Server (`mcp/lap_mcp_server.py`)

**DocLeanMCPServer** — Serve DocLean specs as MCP tools.
- Each endpoint → one MCP tool
- Full input schema with types
- Shows LAP complementing MCP, not competing

```python
from integrations.mcp.lap_mcp_server import DocLeanMCPServer

server = DocLeanMCPServer("specs/")
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
- **Import from `src/`** — reuses existing DocLean parser, format, and utilities
- **One endpoint = one unit** — consistent across all integrations
- **LAP complements, not competes** — each integration shows DocLean adding value to existing tools
