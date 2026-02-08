<![CDATA[<div align="center">

# LAP — Lean Agent Protocol

**The translation layer between APIs and AI.**

Losslessly compiles any API spec — REST, GraphQL, gRPC, AsyncAPI, Postman — into a unified, token-efficient format purpose-built for autonomous agents.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

</div>

---

## What is LAP?

Large language models waste thousands of tokens parsing verbose API specifications. A typical OpenAPI spec for Stripe is 1.5M characters — most of it boilerplate, redundant schemas, and prose that agents don't need. LAP fixes this.

LAP compiles API specifications into **DocLean**, a typed, deterministically parsable format that preserves every endpoint, parameter, type constraint, and authentication requirement — while stripping everything an agent doesn't need. The result: **median 2.8× compression** across 162 real-world API specs, with OpenAPI specs seeing up to **75× reduction**.

LAP also includes **ToolLean**, a companion format for tool manifests (MCP servers, function definitions) that follows the same design philosophy: typed, compact, zero ambiguity.

## Quick Start

```bash
# Install
pip install -e .

# Compile an OpenAPI spec to DocLean
lap compile examples/petstore.yaml -o petstore.doclean

# Inspect the result
lap inspect petstore.doclean
```

## Supported Formats

| Format | Command | Median Compression | Description |
|--------|---------|------------------:|-------------|
| **OpenAPI** (REST) | `lap compile` | **8.86×** | Swagger / OpenAPI 3.x YAML/JSON |
| **GraphQL** | `lap graphql` | **1.35×** | GraphQL SDL schemas |
| **AsyncAPI** | `lap asyncapi` | **2.15×** | Event-driven / WebSocket / Kafka |
| **Protobuf** (gRPC) | `lap protobuf` | **1.78×** | `.proto` files and directories |
| **Postman** | `lap postman` | **6.13×** | Postman Collection v2.1 JSON |

## How It Works

LAP's **DocLean** format replaces verbose specification markup with a typed, line-oriented notation. Here's a before/after:

**OpenAPI (verbose):**
```yaml
paths:
  /v1/charges:
    post:
      summary: Create a charge
      operationId: createCharge
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
                  description: ISO 4217 currency code
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    enum: [succeeded, pending, failed]
                  amount:
                    type: integer
```

**DocLean (compiled):**
```
## POST /v1/charges — Create a charge
@required {amount: int # in cents, currency: str(ISO4217)}
@returns(200) {status: enum(succeeded|pending|failed), amount: int}
```

Same information. Fraction of the tokens.

## Benchmark Results

Tested across **162 real-world API specs** spanning **5,228 endpoints** (5.9M → 336K tokens):

| Format | Specs | Endpoints | Median | Min | Max |
|--------|------:|----------:|-------:|----:|----:|
| OpenAPI | 30 | 3,596 | **8.86×** | 5.49× | 74.75× |
| GraphQL | 30 | 548 | **1.35×** | 1.13× | 2.07× |
| AsyncAPI | 31 | 126 | **2.15×** | 1.69× | 14.04× |
| Protobuf | 35 | 406 | **1.78×** | 1.40× | 117.38× |
| Postman | 36 | 552 | **6.13×** | 4.68× | 18.0× |
| **All** | **162** | **5,228** | **2.8×** | | |

Top compressions: Notion API **74.75×**, Snyk **71.98×**, Zoom **71.77×**, Stripe Full **14.19×**.

See [`benchmarks/results/full_benchmark_v2.md`](benchmarks/results/full_benchmark_v2.md) for complete results.

## CLI Usage

```bash
# Compile OpenAPI spec
lap compile api.yaml -o api.doclean
lap compile api.yaml --lean -o api.lean.doclean   # max compression

# Compile other formats
lap graphql schema.graphql -o schema.doclean
lap asyncapi events.yaml -o events.doclean
lap protobuf service.proto -o service.doclean
lap postman collection.json -o collection.doclean

# Inspect a compiled spec
lap inspect api.doclean
lap inspect api.doclean -e "POST /v1/charges"     # single endpoint

# Validate an OpenAPI spec
lap validate api.yaml

# Benchmark a directory of specs
lap benchmark-all examples/

# Convert DocLean back to OpenAPI
lap convert api.doclean -f openapi -o api-roundtrip.yaml

# Diff two DocLean files
lap diff old.doclean new.doclean --format changelog --version 2.0

# Registry (search compiled specs)
lap registry-list
lap registry-search stripe
```

## Python SDK

```python
from lap import LAPClient

client = LAPClient()

# Compile a spec
doc = client.compile("examples/petstore.yaml")
print(f"{doc.endpoint_count} endpoints, {doc.token_count} tokens")

# Access endpoints
for ep in doc.endpoints:
    print(f"{ep.method} {ep.path} — {ep.summary}")
```

## Project Structure

```
├── core/                       # Core library
│   ├── compilers/              # Format compilers
│   │   ├── openapi.py          # OpenAPI → DocLean
│   │   ├── graphql.py          # GraphQL → DocLean
│   │   ├── asyncapi.py         # AsyncAPI → DocLean
│   │   ├── protobuf.py         # Protobuf → DocLean
│   │   ├── postman.py          # Postman → DocLean
│   │   ├── toollean.py         # ToolLean compiler
│   │   └── toollean_advanced.py# ToolLean CLI & advanced ops
│   ├── formats/                # Data models
│   │   ├── doclean.py          # DocLean data model
│   │   └── toollean.py         # ToolLean data model
│   ├── parser.py               # DocLean parser
│   ├── converter.py            # DocLean → OpenAPI roundtrip
│   ├── differ.py               # DocLean diff engine
│   └── utils.py                # Shared utilities
├── cli/                        # CLI entry point
│   └── main.py
├── sdks/                       # Language SDKs
│   ├── python/
│   └── typescript/
├── examples/                   # Example API specs (207 specs)
├── benchmarks/                 # Benchmark suite & results
├── integrations/               # LangChain, CrewAI, OpenAI, MCP
├── tests/                      # Test suite
└── docs/                       # Documentation
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on running tests, code style, and the PR process.

## License

Apache License 2.0 with patent grant. See [LICENSE](LICENSE) for details.
]]>