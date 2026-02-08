# Getting Started with LAP

## Installation

### Python SDK

```bash
pip install lap-sdk

# Or from source:
git clone https://github.com/anthropics/lap.git
cd lap
pip install -r requirements.txt
```

Dependencies: `pyyaml`, `tiktoken`, `rich`

Optional extras:
```bash
pip install lap-sdk[langchain]   # LangChain integration
pip install lap-sdk[tokens]      # Token counting with tiktoken
```

### TypeScript SDK

```bash
npm install @anthropic/lap-sdk
```

Or from source:
```bash
cd sdk/typescript
npm install
npm run build
```

### CLI Only

If you just need the compiler:

```bash
git clone https://github.com/anthropics/lap.git
cd lap
pip install pyyaml tiktoken rich
python3 cli.py --help
```

---

## Quick Start: Compile Your First API in 60 Seconds

### 1. Compile an OpenAPI spec

```bash
python3 cli.py compile specs/stripe-charges.yaml -o stripe.doclean
```

Output:
```
✓ Compiled stripe-charges.yaml → stripe.doclean
✓ 5 endpoints | 4,291 chars | standard mode
```

### 2. See the result

The compiled DocLean file:

```
@doclean v0.1
@api Stripe Charges API
@base https://api.stripe.com
@version 2024-12-18
@auth Bearer bearer

@endpoint POST /v1/charges
@desc Create a charge
@required {amount: int # Amount in cents., currency: str # ISO 4217 code.}
@optional {source: str, customer: str, description: str, metadata: map, ...}
@returns(200) {id: str, amount: int, currency: str, status: str, paid: bool, ...}
@errors {400: Invalid request., 401: Auth failed., 402: Card declined., 429: Rate limited.}
```

### 3. Try lean mode for maximum compression

```bash
python3 cli.py compile specs/stripe-charges.yaml --lean
```

Output (lean mode strips descriptions):
```
@doclean v0.1
@api Stripe Charges API
@base https://api.stripe.com
@version 2024-12-18
@auth Bearer bearer

@endpoint POST /v1/charges
@required {amount: int, currency: str}
@optional {source: str, customer: str, description: str, metadata: map, ...}
@returns(200) {id: str, amount: int, currency: str, status: str, paid: bool, ...}
@errors {400, 401, 402, 429}
```

### 4. Validate zero information loss

```bash
python3 cli.py validate specs/stripe-charges.yaml
```

```
  Check               Result   Status
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoints       5/5 (100%)     ✅
  Parameters    32/32 (100%)     ✅
  Error Codes     8/8 (100%)     ✅

PASS — Zero information loss!
```

---

## Understanding DocLean Output

DocLean is a structured, typed format for API documentation. Here's what each directive means:

### Header Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@doclean` | Format version | `@doclean v0.1` |
| `@api` | API name | `@api Stripe Charges API` |
| `@base` | Base URL | `@base https://api.stripe.com` |
| `@version` | API version | `@version 2024-12-18` |
| `@auth` | Auth scheme | `@auth Bearer bearer` |

### Endpoint Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@endpoint` | Method + path | `@endpoint POST /v1/charges` |
| `@desc` | Description | `@desc Create a charge` |
| `@required` | Required params | `@required {amount: int, currency: str}` |
| `@optional` | Optional params | `@optional {limit: int=10}` |
| `@returns(N)` | Response schema | `@returns(200) {id: str, status: str}` |
| `@errors` | Error codes | `@errors {400, 401, 429}` |

### Type System

| Type | Meaning | Example |
|------|---------|---------|
| `str` | String | `name: str` |
| `int` | Integer | `amount: int` |
| `num` | Number (float) | `price: num` |
| `bool` | Boolean | `active: bool` |
| `map` | Object/dict | `metadata: map` |
| `any` | Any type | `data: any` |
| `[type]` | Array | `tags: [str]` |
| `type?` | Nullable | `email: str?` |
| `type(format)` | Format hint | `created: int(unix-timestamp)` |
| `enum(a\|b\|c)` | Enumeration | `status: enum(active\|inactive)` |
| `type=default` | Default value | `limit: int=10` |

### Standard vs Lean

- **Standard mode** — keeps `@desc` and `# comment` annotations. Best for debugging and human review.
- **Lean mode** (`--lean`) — strips all descriptions. Maximum compression for production agent use.

---

## Next Steps

- [Compiling OpenAPI Specs](guide-compile.md) — batch compilation, handling large specs
- [Framework Integration](guide-integrate.md) — LangChain, CrewAI, OpenAI, MCP
- [CLI Reference](reference-cli.md) — all commands with examples
