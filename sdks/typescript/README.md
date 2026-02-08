# @lap/sdk — TypeScript SDK for DocLean

Parse and work with DocLean API specifications in TypeScript/JavaScript.

## Quick Start

```typescript
import { LAPClient, toContext } from '@lap/sdk';

const client = new LAPClient();
const spec = client.loadFile('./stripe-charges.doclean');

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

- **`loadFile(path)`** — Parse a `.doclean` file from disk
- **`loadString(text)`** — Parse DocLean text directly
- **`fromRegistry(url, apiName)`** — Fetch from a LAP registry (async)

### `parse(text): DocLeanSpec`

Low-level parser. Returns a `DocLeanSpec` with:

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
