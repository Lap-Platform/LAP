# DocLean Registry

Lightweight HTTP API for serving and discovering DocLean specs.

## Quick Start

```bash
# Start server (port 8420)
python -m registry.server

# Or with custom port/output dir
DOCLEAN_PORT=9000 DOCLEAN_OUTPUT=./output python -m registry.server
```

## API Reference

| Endpoint | Description |
|---|---|
| `GET /v1/apis` | List all APIs |
| `GET /v1/apis/{name}` | Get spec (DocLean text) |
| `GET /v1/apis/{name}?format=lean` | Get lean/compressed version |
| `GET /v1/apis/{name}?format=openapi` | Get structured metadata |
| `GET /v1/search?q=keyword` | Search by name/description |
| `GET /v1/stats` | Registry statistics |

### Content Negotiation

- `Accept: application/doclean+v1` → DocLean text
- `Accept: application/json` → JSON metadata

## Examples

```bash
# List APIs
curl http://localhost:8420/v1/apis

# Get a spec
curl http://localhost:8420/v1/apis/stripe-charges

# Search
curl http://localhost:8420/v1/search?q=payment

# Stats
curl http://localhost:8420/v1/stats
```

## Python Client

```python
from registry.client import RegistryClient

client = RegistryClient("http://localhost:8420")
client.list()                          # all APIs
client.get("stripe-charges")           # full spec text
client.get("stripe-charges", format="lean")  # compressed
client.search("payment")              # search
client.stats()                         # statistics
```
