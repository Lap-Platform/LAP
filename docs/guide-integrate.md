# Framework Integration Guide

LAP integrates with popular agent frameworks. Each integration converts LAP specs into the framework's native tool/document format.

## Using with LangChain

LAP provides a LangChain-compatible `DocumentLoader` that loads LAP files as LangChain `Document` objects.

### Installation

```bash
pip install lapsh[langchain]
```

### Loading API docs

```python
from lap.middleware import LAPDocLoader

# Load a LAP file — one Document per endpoint
loader = LAPDocLoader("output/stripe-charges.lap")
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
loader = LAPDocLoader("output/github-core.lap")
docs = loader.load()
vectorstore = FAISS.from_documents(docs, OpenAIEmbeddings())

# Query
results = vectorstore.similarity_search("create a repository")
# Returns the POST /repos endpoint document
```

## Using with Context Hub

[Context Hub](https://github.com/andrewyng/context-hub) equips coding agents with curated, versioned documentation. The LAP registry is a supported Context Hub source - agents can discover and fetch LAP specs directly.

### Setup

Add the LAP registry to your `config.yaml`:

```yaml
sources:
  - name: default
    url: https://cdn.aichub.org/v1
  - name: lap
    url: https://registry.lap.sh/chub
```

### Usage

```bash
# Search for API docs via Context Hub
chub search stripe --source lap

# Fetch a spec
chub get stripe --source lap
```

Agents using Context Hub will automatically discover LAP specs alongside other documentation sources.

## Custom Integration

For frameworks not listed above, use the Python or TypeScript SDK directly:

### Python

```python
from lap import LAPClient

client = LAPClient()
doc = client.load("output/stripe-charges.lap")

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
import { LAPClient, toContext } from '@lap-platform/lapsh';

const client = new LAPClient();
const spec = client.loadFile('output/stripe-charges.lap');

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
