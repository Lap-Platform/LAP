# CLI Reference

## Overview

```
lapsh [-h] {compile,benchmark,benchmark-all,inspect,convert,diff,registry} ...
```

## Commands

### `lapsh compile`

Compile an OpenAPI spec to LAP format.

```
lapsh compile [-h] [-o OUTPUT] [--lean] spec
```

| Argument | Description |
|----------|-------------|
| `spec` | Path to OpenAPI spec (YAML/JSON) |
| `-o, --output` | Output file path (default: stdout) |
| `--lean` | Maximum compression, strip descriptions |

**Examples:**

```bash
# Compile to stdout
$ lapsh compile examples/verbose/openapi/stripe-charges.yaml

@lap v0.1
@api Stripe Charges API
@base https://api.stripe.com
@version 2024-12-18
@auth Bearer bearer

@endpoint POST /v1/charges
@desc Create a charge
@required {amount: int # Amount intended to be collected by this payment, in cents., currency: str # Three-letter ISO 4217 currency code, in lowercase.}
...

# Compile to file
$ lapsh compile examples/verbose/openapi/stripe-charges.yaml -o stripe.lap
✓ Compiled stripe-charges.yaml → stripe.lap
✓ 5 endpoints | 4,291 chars | standard mode

# Lean mode
$ lapsh compile examples/verbose/openapi/stripe-charges.yaml --lean

@lap v0.1
@api Stripe Charges API
@base https://api.stripe.com
@version 2024-12-18
@auth Bearer bearer

@endpoint POST /v1/charges
@required {amount: int, currency: str}
@optional {source: str, customer: str, description: str, metadata: map, ...}
@returns(200) {id: str, object: str, amount: int, ...}
@errors {400, 401, 402, 429}
...
```

---

### `lapsh benchmark`

Benchmark token usage comparing verbose docs vs LAP for a single spec.

```
lapsh benchmark [-h] spec
```

**Example:**

```bash
$ lapsh benchmark examples/verbose/openapi/stripe-charges.yaml

📊 LAP LAP Token Benchmark

📏 Character Count:
  Raw OpenAPI spec:      11,160 chars
  Verbose (human-readable):    3,536 chars
  LAP (compressed):    4,291 chars

🔢 Token Counts:
  Model                   Verbose    LAP  Reduction    Ratio
  ------------------   ---------- ---------- ---------- --------
  gpt-4o                      852        992     -16.4%     0.9x
  claude-sonnet-4             852        992     -16.4%     0.9x

📐 Endpoints compiled: 5
```

---

### `lapsh benchmark-all`

Benchmark all specs in a directory.

```
lapsh benchmark-all [-h] directory
```

**Example:**

```bash
$ lapsh benchmark-all examples/verbose/openapi/
```

---

### `lapsh inspect`

Parse and display a LAP file in a structured, readable format.

```
lapsh inspect [-h] [--endpoint ENDPOINT] file
```

| Argument | Description |
|----------|-------------|
| `file` | Path to `.lap` file |
| `-e, --endpoint` | Filter to specific endpoint, e.g. `"POST /v1/charges"` |

**Example:**

```bash
$ lapsh inspect output/stripe-charges.lap

╭──────────────────────── LAP Spec ────────────────────────╮
│ Stripe Charges API v2024-12-18                               │
│ Base: https://api.stripe.com                                 │
│ Auth: Bearer bearer                                          │
│ Endpoints: 5                                                 │
╰──────────────────────────────────────────────────────────────╯

POST /v1/charges  Create a charge
  Required:
    amount: int # Amount intended to be collected, in cents.
    currency: str # Three-letter ISO 4217 currency code.
  Optional:
    source: str
    customer: str
    description: str
    ...
  → 200 Returns the charge object (21 fields)
  Errors: 400, 401, 402, 429

GET /v1/charges  List all charges
  ...

# Filter to one endpoint
$ lapsh inspect output/stripe-charges.lap -e "POST /v1/charges"
```

---

### `lapsh convert`

Convert a LAP file back to OpenAPI format.

```
lapsh convert [-h] [-f FORMAT] [-o OUTPUT] file
```

| Argument | Description |
|----------|-------------|
| `file` | Path to `.lap` file |
| `-f, --format` | Output format (default: `openapi`) |
| `-o, --output` | Output file path |

**Example:**

```bash
$ lapsh convert output/stripe-charges.lap -f openapi -o stripe-roundtrip.yaml
```

---

### `lapsh diff`

Diff two LAP files to detect API changes.

```
lapsh diff [-h] [--format {summary,changelog}] [--version VERSION] old new
```

| Argument | Description |
|----------|-------------|
| `old` | Path to old `.lap` file |
| `new` | Path to new `.lap` file |
| `--format` | Output format: `summary` or `changelog` |
| `--version` | Version label for changelog output |

**Example:**

```bash
$ lapsh diff v1.lap v2.lap --format changelog --version "2.0"
```

