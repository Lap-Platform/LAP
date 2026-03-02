# Registry Guide

The LAP registry is a lightweight server for discovering, searching, and serving LAP specs over HTTP.

## Running the Registry Server

### Quick Start

```bash
# Compile some specs first
lapsh compile specs/stripe-charges.yaml -o output/stripe-charges.lap
lapsh compile specs/github-core.yaml -o output/github-core.lap

# Start the registry server
python3 registry/server.py
```

The server starts on port 8420 by default (configurable via `LAP_PORT` env var).

### Configuration

| Env Variable | Default | Purpose |
|---|---|---|
| `LAP_PORT` | `8420` | Server port |
| `LAP_OUTPUT` | `./output` | Directory containing `.lap` files |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET /specs` | | List all available specs |
| `GET /specs/{name}` | | Get a specific spec (raw LAP text) |
| `GET /specs/{name}?format=lean` | | Get lean version |
| `GET /specs/{name}/meta` | | Get metadata (endpoints, version, etc.) |
| `GET /search?q=...` | | Search across all specs |

### Example Requests

```bash
# List all specs
curl http://localhost:8420/specs

# Get a spec
curl http://localhost:8420/specs/stripe-charges

# Get metadata
curl http://localhost:8420/specs/stripe-charges/meta
```

## Using the Registry Client

### Python SDK

```python
from lap import Registry

registry = Registry("output/")

# List all available specs
specs = registry.list()
print(specs)  # ['asana', 'box', 'circleci', 'cloudflare', ...]

# Get a specific spec
doc = registry.get("stripe-charges")
print(doc.api_name)       # "Stripe Charges API"
print(doc.base_url)       # "https://api.stripe.com"
print(len(doc.endpoints)) # 5

# Search across all specs
results = registry.search("webhook")
for doc in results:
    print(f"{doc.api_name}: {len(doc.endpoints)} endpoints")
```

### TypeScript SDK

```typescript
import { LAPClient } from '@lap-platform/lapsh';

const client = new LAPClient();

// Load from a running registry server
const spec = await client.fromRegistry('http://localhost:8420', 'stripe-charges');
console.log(spec.apiName);  // "Stripe Charges API"
```

## Contributing Specs to the Registry

### Adding a New API Spec

1. **Find or create the OpenAPI spec**

   Place it in `specs/`:
   ```bash
   cp ~/my-api-spec.yaml specs/my-api.yaml
   ```

2. **Compile it**

   ```bash
   lapsh compile specs/my-api.yaml -o output/my-api.lap
   lapsh compile specs/my-api.yaml -o output/my-api.lean.lap --lean
   ```

3. **Validate**

   ```bash
   lapsh validate specs/my-api.yaml
   ```

4. **Test with the registry**

   ```bash
   python3 registry/server.py  # Picks up new files in output/
   curl http://localhost:8420/specs/my-api
   ```

### Spec Quality Checklist

- [ ] All endpoints compile without warnings
- [ ] Validation passes (100% endpoints, parameters, error codes)
- [ ] Both standard and lean versions generated
- [ ] Lean mode produces meaningful output (types are correct)
- [ ] API name and version are set correctly in the OpenAPI source

### Pre-built Registry

LAP ships with 30+ pre-compiled specs in `output/`. These cover popular APIs:

Stripe, GitHub, GitLab, Discord, Slack, Notion, Jira, Asana, Spotify, Twitter, Cloudflare, DigitalOcean, Vercel, Netlify, Zoom, Twilio, SendGrid, Plaid, OpenAI, and more.
