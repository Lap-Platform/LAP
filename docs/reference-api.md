# API Reference

## Python SDK

### `LAPClient`

Main client for loading LAP documents.

```python
from lap import LAPClient

client = LAPClient()
```

#### `client.load(path: str) -> LAPDoc`

Load a `.lap` file and return a queryable document.

```python
doc = client.load("output/stripe-charges.lap")
```

Raises `FileNotFoundError` if the file doesn't exist.

---

### `LAPDoc`

A loaded LAP document with query and formatting methods.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `api_name` | `str` | API name from `@api` directive |
| `base_url` | `str` | Base URL from `@base` directive |
| `version` | `str` | Version from `@version` directive |
| `endpoints` | `List[EndpointInfo]` | All endpoints in the spec |

#### `doc.get_endpoint(method: str, path: str) -> Optional[EndpointInfo]`

Find an endpoint by HTTP method and path.

```python
ep = doc.get_endpoint("POST", "/v1/charges")
```

#### `doc.to_context(lean: bool = False) -> str`

Format the full spec as a string for LLM context injection.

```python
context = doc.to_context(lean=True)
# Inject into prompt: f"API Reference:\n{context}"
```

#### `doc.token_count(lean: bool = False) -> int`

Count tokens using tiktoken.

```python
tokens = doc.token_count(lean=True)
print(f"{tokens} tokens")
```

---

### `EndpointInfo`

Structured endpoint data.

| Property | Type | Description |
|----------|------|-------------|
| `method` | `str` | HTTP method (GET, POST, etc.) |
| `path` | `str` | URL path |
| `summary` | `str` | Description from `@desc` |
| `required_params` | `List[Param]` | Required parameters |
| `optional_params` | `List[Param]` | Optional parameters |
| `request_body` | `List[Param]` | Request body fields |
| `response_schemas` | `List[ResponseSchema]` | Response schemas |
| `response_schema` | `Optional[ResponseSchema]` | Primary (first) response |
| `error_schemas` | `List[ErrorSchema]` | Error definitions |

---

### `Param`

Parameter definition.

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Parameter name |
| `type` | `str` | Type string (`str`, `int`, etc.) |
| `required` | `bool` | Whether required |
| `description` | `str` | Description text |
| `enum` | `list` | Enum values (if any) |
| `default` | `Optional[str]` | Default value |

---

### `Registry`

Local registry for browsing LAP files in a directory.

```python
from lap import Registry

registry = Registry("output/")
```

#### `registry.list() -> List[str]`

List all available spec names.

```python
names = registry.list()
# ['asana', 'box', 'cloudflare', 'discord', 'github-core', ...]
```

#### `registry.get(name: str) -> Optional[LAPDoc]`

Get a spec by name (exact or partial match).

```python
doc = registry.get("stripe")
```

#### `registry.search(query: str) -> List[LAPDoc]`

Search across all specs by name or content.

```python
results = registry.search("webhook")
```

---

### `LAPDocLoader` (LangChain)

LangChain-compatible document loader.

```python
from lap.middleware import LAPDocLoader

loader = LAPDocLoader("output/stripe.lap", lean=True)
docs = loader.load()       # List[Document] — one per endpoint
full = loader.load_full()  # List[Document] — single document with full context
```

---

## TypeScript SDK

### `LAPClient`

```typescript
import { LAPClient } from '@lap-platform/sdk';

const client = new LAPClient();
```

#### `client.loadFile(filePath: string): LAPSpec`

Load a `.lap` file from disk.

```typescript
const spec = client.loadFile('output/stripe-charges.lap');
```

#### `client.loadString(text: string): LAPSpec`

Parse a LAP string directly.

```typescript
const spec = client.loadString(lapText);
```

#### `client.fromRegistry(registryUrl: string, apiName: string): Promise<LAPSpec>`

Fetch a spec from a registry server.

```typescript
const spec = await client.fromRegistry('http://localhost:8420', 'stripe-charges');
```

---

### `LAPSpec`

| Property | Type | Description |
|----------|------|-------------|
| `apiName` | `string` | API name |
| `baseUrl` | `string` | Base URL |
| `version` | `string` | API version |
| `auth` | `string` | Auth scheme |
| `endpoints` | `Endpoint[]` | All endpoints |

### `Endpoint`

| Property | Type | Description |
|----------|------|-------------|
| `method` | `string` | HTTP method |
| `path` | `string` | URL path |
| `description` | `string` | Description |
| `requiredParams` | `Param[]` | Required parameters |
| `optionalParams` | `Param[]` | Optional parameters |
| `responses` | `ResponseSchema[]` | Response schemas |

### `Param`

| Property | Type | Description |
|----------|------|-------------|
| `name` | `string` | Parameter name |
| `type` | `string` | Type string |
| `nullable` | `boolean` | Is nullable |
| `isArray` | `boolean` | Is array type |
| `enumValues` | `string[]` | Enum values |
| `defaultValue` | `string` | Default value |
| `description` | `string` | Description |

### `toContext(spec, opts?): string`

Format a spec for LLM context injection.

```typescript
import { toContext } from '@lap-platform/sdk';

const context = toContext(spec, { lean: true });
const filtered = toContext(spec, {
  endpoints: ['POST /v1/charges']
});
```

---

## Registry Server API

The registry server (`registry/server.py`) exposes a REST API on port 8420.

### `GET /specs`

List all available specs.

**Response:** `200 OK`
```json
{
  "specs": [
    {
      "name": "stripe-charges",
      "description": "Stripe Charges API",
      "version": "2024-12-18",
      "endpoints": 5,
      "size": 4291,
      "lean_size": 1847,
      "last_updated": "2026-02-08T00:00:00+00:00"
    }
  ]
}
```

### `GET /specs/{name}`

Get the raw LAP text for a spec.

**Query params:** `format=lean` for lean version.

**Response:** `200 OK` — raw LAP text (`text/plain`)

### `GET /specs/{name}/meta`

Get metadata for a spec.

**Response:** `200 OK`
```json
{
  "name": "stripe-charges",
  "description": "Stripe Charges API",
  "version": "2024-12-18",
  "base_url": "https://api.stripe.com",
  "endpoints": 5
}
```

### `GET /search?q={query}`

Search across all specs.

**Response:** `200 OK` — array of matching specs
