# @lap-platform/lapsh -- TypeScript SDK for LAP

Parse and work with LAP (Lean API Platform) API specifications in TypeScript/JavaScript.

## Install

```bash
npm install @lap-platform/lapsh
```

## Quick Start

```typescript
import { LAPClient, toContext } from '@lap-platform/lapsh';

const client = new LAPClient();
const spec = client.loadFile('./stripe-charges.lap');

// Get a specific endpoint
const ep = spec.getEndpoint('POST', '/v1/charges');
console.log(ep.requiredParams);  // [{ name: 'amount', type: 'int', ... }, ...]
console.log(ep.responses);       // [{ statusCode: 200, fields: [...] }]
console.log(ep.errors);          // [{ statusCode: 400, description: '...' }, ...]

// Generate LLM-friendly context
const ctx = toContext(spec, { lean: true });
```

## API

### `LAPClient`

- **`loadFile(path)`** — Parse a `.lap` file from disk
- **`loadString(text)`** — Parse LAP text directly
- **`fromRegistry(url, apiName)`** — Fetch from a LAP registry (async)

### `parse(text): LAPSpec`

Low-level parser. Returns a `LAPSpec` with:

- `apiName`, `baseUrl`, `apiVersion`, `auth`
- `endpoints: Endpoint[]`
- `getEndpoint(method, path): Endpoint | undefined`

### `toContext(spec, opts): string`

Format a spec for LLM consumption. Options:
- `lean: boolean` — omit descriptions
- `endpoints: string[]` — filter by `"METHOD /path"`

### Types

```typescript
interface Param {
  name: string; type: string; required: boolean;
  nullable: boolean; isArray: boolean;
  enumValues?: string[]; defaultValue?: string;
  description?: string; format?: string;
  nested?: ResponseField[];
}

interface ResponseField {
  name: string; type: string; nullable: boolean;
  description?: string; enumValues?: string[];
  format?: string; nested?: ResponseField[];
}

interface Endpoint {
  method: string; path: string; description?: string;
  requiredParams: Param[]; optionalParams: Param[];
  allParams: Param[];
  responses: ResponseSchema[]; errors: ErrorSchema[];
}
```

## Build & Test

```bash
npm install
npx tsc
node dist/tests/parser.test.js
```

## Zero Dependencies

No runtime dependencies — just TypeScript types and Node.js built-ins.
