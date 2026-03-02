<div align="center">

# LAP — Lean API Platform

**Cut API spec tokens by 10×. Same information. Fraction of the cost.**

[![PyPI](https://img.shields.io/pypi/v/lap.svg)](https://pypi.org/project/lap/)
[![CI](https://github.com/Lean-Agent-Protocol/lap/actions/workflows/ci.yml/badge.svg)](https://github.com/Lean-Agent-Protocol/lap/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

LAP compiles API specs into **LAP** — a typed, token-efficient format built for AI agents.
OpenAPI, GraphQL, AsyncAPI, Protobuf, Postman, Smithy → one compact format.

</div>

## Why LAP?

LLMs waste thousands of tokens parsing bloated API specs. Stripe's OpenAPI spec is **1M+ tokens** — mostly boilerplate. LAP strips what agents don't need and keeps everything they do.

- **10.3× overall compression** across 162 real-world specs
- **Up to 39.6×** on large OpenAPI specs (Notion, Snyk, Zoom)
- **Zero information loss** — every endpoint, param, and type constraint preserved
- **6 formats supported** — one CLI, one output format

![Compression by Format](https://raw.githubusercontent.com/Lean-Agent-Protocol/lap/main/benchmarks/results/charts/format_comparison.png)

## Quick Start

```bash
pip install lap
lap compile api.yaml -o api.lap
```

## Before / After

**OpenAPI (26 lines):**
```yaml
paths:
  /v1/charges:
    post:
      summary: Create a charge
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [amount, currency]
              properties:
                amount:
                  type: integer
                  description: Amount in cents
                currency:
                  type: string
```

**LAP (2 lines):**
```
## POST /v1/charges — Create a charge
@required {amount: int # in cents, currency: str(ISO4217)}
```

## Benchmarks

162 specs · 5,228 endpoints · 4.37M → 423K tokens

| Format | Specs | Median | Best |
|--------|------:|-------:|-----:|
| **OpenAPI** | 30 | **5.2×** | 39.6× |
| **Postman** | 36 | **6.1×** | 18.0× |
| **AsyncAPI** | 31 | **2.2×** | 14.0× |
| **Protobuf** | 35 | **1.8×** | 117.4× |
| **GraphQL** | 30 | **1.4×** | 2.1× |

![Compression Ratios](https://raw.githubusercontent.com/Lean-Agent-Protocol/lap/main/benchmarks/results/charts/compression_bar_chart.png)

→ [Full benchmark results](BENCHMARKS.md)

## How It Works

![How LAP Works](https://raw.githubusercontent.com/Lean-Agent-Protocol/lap/main/benchmarks/results/charts/pipeline.png)

**Five compression stages:**

1. **Structural noise removal** — Strip YAML scaffolding, `$ref` resolution, empty fields (~30%)
2. **Directive grammar** — Flat `@directives` replace 4-8 levels of nesting (~25%)
3. **Type compression** — `str(uuid)` instead of `type: string, format: uuid` (~10%)
4. **Redundancy elimination** — Deduplicate error schemas, shared params, common fields (~20%)
5. **Description stripping** (lean mode) — LLMs infer meaning from param names (~15%)

## LAP Format Conventions

LAP uses `@directives` — a flat, line-oriented grammar designed for LLM parsing.

### Header Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@lap` | Format version | `@lap v0.3` |
| `@api` | API name | `@api Stripe Charges API` |
| `@base` | Base URL | `@base https://api.stripe.com` |
| `@version` | API version | `@version 2024-12-18` |
| `@auth` | Auth scheme | `@auth Bearer bearer` |
| `@endpoints` | Total endpoint count | `@endpoints 5` |
| `@toc` | Table of contents | `@toc charges(5)` |
| `@end` | End of document | `@end` |

### Endpoint Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@endpoint` | Method + path | `@endpoint POST /v1/charges` |
| `@desc` | Description (standard mode) | `@desc Create a charge` |
| `@required` | Required params with types | `@required {amount: int, currency: str}` |
| `@optional` | Optional params with types | `@optional {limit: int=10, cursor: str}` |
| `@returns(code)` | Response schema | `@returns(200) {id: str, status: str}` |
| `@errors` | Error codes | `@errors {400, 401, 404}` |

### Type System

| Type | Meaning | Example |
|------|---------|---------|
| `str` | String | `name: str` |
| `int` | Integer | `amount: int` |
| `bool` | Boolean | `capture: bool` |
| `float` | Float | `price: float` |
| `map` | Object/dict | `metadata: map` |
| `[T]` | Array of T | `items: [str]` |
| `T?` | Nullable | `email: str?` |
| `str(format)` | Typed string | `id: str(uuid)` |
| `int(format)` | Typed int | `created: int(unix-timestamp)` |
| `enum(a\|b\|c)` | Enum values | `status: enum(active\|inactive)` |
| `T=default` | Default value | `limit: int=10` |
| `map{k: T}` | Typed object | `billing: map{name: str, email: str}` |

### Standard vs Lean Mode

- **Standard** — includes `@desc` and inline `# comments` after fields
- **Lean** — strips descriptions and comments; LLMs infer meaning from param names

```
# Standard:  @required {amount: int # Amount in cents., currency: str # ISO 4217 code.}
# Lean:      @required {amount: int, currency: str}
```

### Example (Lean)

```
@lap v0.3
@api Stripe Charges API
@base https://api.stripe.com
@auth Bearer bearer

@endpoint POST /v1/charges
@required {amount: int, currency: str}
@optional {source: str, customer: str, metadata: map}
@returns(200) {id: str, amount: int, status: str, paid: bool}
@errors {400, 401, 402}

@endpoint GET /v1/charges/{charge}
@required {charge: str}
@returns(200)
@errors {404}

@end
```

## Supported Formats

```bash
lap compile     api.yaml           # OpenAPI 3.x / Swagger
lap graphql     schema.graphql     # GraphQL SDL
lap asyncapi    events.yaml        # AsyncAPI
lap protobuf    service.proto      # Protobuf / gRPC
lap postman     collection.json    # Postman v2.1
lap compile     model.json         # AWS Smithy (JSON AST or .smithy)
```

## Python SDK

```python
from lap import LAPClient

doc = LAPClient().compile("api.yaml")
for ep in doc.endpoints:
    print(f"{ep.method} {ep.path}")
```

## Also: LAP

Companion format for **tool manifests** (MCP servers, function definitions). Same philosophy: typed, compact, zero ambiguity.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 — See [LICENSE](LICENSE)
