# Registry Guide

The LAP registry at [lap.sh](https://lap.sh) hosts pre-compiled LAP specs for discovery, search, and download.

## Using the Registry Client

### Python SDK

```python
from lap import Registry

registry = Registry("examples/lap/openapi/")

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

To publish your API spec to the registry, use the [publisher page](https://registry.lap.sh/#publish) or the CLI:

```bash
lapsh publish my-api.yaml --provider acme
```

See [contributing guide](contributing.md) for details.

### Pre-built Registry

The registry at [lap.sh](https://lap.sh) hosts 1,500+ pre-compiled specs covering popular APIs:

Stripe, GitHub, GitLab, Discord, Slack, Notion, Jira, Asana, Spotify, Twitter, Cloudflare, DigitalOcean, Vercel, Netlify, Zoom, Twilio, SendGrid, Plaid, OpenAI, and more.
