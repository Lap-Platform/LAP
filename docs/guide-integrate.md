# Framework Integration Guide

LAP integrates with popular agent frameworks. Each integration converts DocLean specs into the framework's native tool/document format.

## Using with LangChain

LAP provides a LangChain-compatible `DocumentLoader` that loads DocLean files as LangChain `Document` objects.

### Installation

```bash
pip install lap-sdk[langchain]
```

### Loading API docs

```python
from lap.middleware import LAPDocLoader

# Load a DocLean file — one Document per endpoint
loader = LAPDocLoader("output/stripe-charges.doclean")
docs = loader.load()

print(f"Loaded {len(docs)} endpoint documents")
for doc in docs:
    print(f"--- {doc.metadata['method']} {doc.metadata['path']} ---")
    print(doc.page_content[:200])
```

Each `Document` contains:
- `page_content`: The endpoint signature, parameters, and response schema
- `metadata`: `source`, `api`, `method`, `path`

### Full context mode

For injecting the entire API spec as a single document:

```python
full_docs = loader.load_full()
print(f"Full context: {len(full_docs[0].page_content)} chars")
```

### With a retrieval chain

```python
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings

# Index all endpoints
loader = LAPDocLoader("output/github-core.doclean")
docs = loader.load()
vectorstore = FAISS.from_documents(docs, OpenAIEmbeddings())

# Query
results = vectorstore.similarity_search("create a repository")
# Returns the POST /repos endpoint document
```

## Using with CrewAI

LAP provides a CrewAI-compatible tool for API lookup.

```python
from crewai import Agent, Task, Crew
from integrations.crewai.lap_tool import DocLeanLookup

# Create the tool
api_lookup = DocLeanLookup(specs_dir="output/")

# Use it in an agent
agent = Agent(
    role="API Developer",
    tools=[api_lookup],
    goal="Find the right API endpoint for any task"
)

task = Task(
    description="Find how to create a Stripe charge",
    agent=agent
)

crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
```

### Standalone usage (without CrewAI)

```python
from integrations.crewai.lap_tool import DocLeanLookup

tool = DocLeanLookup(specs_dir="output/")
result = tool._run("stripe", endpoint="charges")
print(result)
```

## Using with OpenAI Function Calling

Convert DocLean endpoints to OpenAI function schemas:

```python
from lap import LAPClient

client = LAPClient()
doc = client.load("output/stripe-charges.doclean")

# Convert each endpoint to an OpenAI function definition
functions = []
for ep in doc.endpoints:
    properties = {}
    required = []

    for p in ep.required_params:
        properties[p.name] = {"type": _map_type(p.type), "description": p.description}
        required.append(p.name)

    for p in ep.optional_params:
        properties[p.name] = {"type": _map_type(p.type), "description": p.description}

    functions.append({
        "name": f"{ep.method.lower()}_{ep.path.replace('/', '_').strip('_')}",
        "description": ep.summary,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    })

def _map_type(t):
    return {"str": "string", "int": "integer", "num": "number",
            "bool": "boolean", "map": "object"}.get(t, "string")
```

Then use with the OpenAI API:

```python
import openai

response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Charge $50 to customer cus_123"}],
    functions=functions,
)
```

## Using with MCP

LAP complements MCP — it compresses the documentation that MCP tools expose. The MCP integration serves DocLean endpoints as MCP tools.

```python
from integrations.mcp.lap_mcp_server import DocLeanMCPServer

# Load specs and serve as MCP tools
server = DocLeanMCPServer("output/")
server.load_spec("output/github-core.doclean")

# List available tools
tools = server.list_tools()
for tool in tools:
    print(f"{tool['name']}: {tool['description'][:60]}")
    print(f"  Input: {json.dumps(tool['inputSchema'], indent=2)[:100]}...")
```

Each DocLean endpoint becomes an MCP tool with:
- `name`: Derived from method + path (e.g., `github_get_repos_owner_repo`)
- `description`: From `@desc`
- `inputSchema`: JSON Schema generated from `@required` and `@optional` params

### How LAP + MCP work together

- **MCP** defines the protocol for tool discovery and invocation
- **LAP** compresses the API documentation each tool exposes
- An MCP server uses DocLean for compact tool descriptions
- The agent sees shorter, typed schemas instead of verbose JSON Schema

## Custom Integration

For frameworks not listed above, use the Python or TypeScript SDK directly:

### Python

```python
from lap import LAPClient

client = LAPClient()
doc = client.load("output/stripe-charges.doclean")

# Get full context string for LLM injection
context = doc.to_context(lean=True)
print(f"Context: {doc.token_count(lean=True)} tokens")

# Query specific endpoints
ep = doc.get_endpoint("POST", "/v1/charges")
print(f"Required: {[p.name for p in ep.required_params]}")
print(f"Optional: {[p.name for p in ep.optional_params]}")
```

### TypeScript

```typescript
import { LAPClient, toContext } from '@anthropic/lap-sdk';

const client = new LAPClient();
const spec = client.loadFile('output/stripe-charges.doclean');

// Full context
const context = toContext(spec, { lean: true });

// Filter specific endpoints
const filtered = toContext(spec, {
  lean: true,
  endpoints: ['POST /v1/charges', 'GET /v1/charges']
});
```

### From a Registry

```typescript
const spec = await client.fromRegistry('http://localhost:8420', 'stripe-charges');
const context = toContext(spec);
```
