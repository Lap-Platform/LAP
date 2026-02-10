# CLI Reference

## Overview

```
lap [-h] {compile,validate,benchmark,benchmark-all,inspect,convert,diff,registry,lap} ...
```

## Commands

### `lap compile`

Compile an OpenAPI spec to LAP format.

```
lap compile [-h] [-o OUTPUT] [--lean] spec
```

| Argument | Description |
|----------|-------------|
| `spec` | Path to OpenAPI spec (YAML/JSON) |
| `-o, --output` | Output file path (default: stdout) |
| `--lean` | Maximum compression, strip descriptions |

**Examples:**

```bash
# Compile to stdout
$ lap compile specs/stripe-charges.yaml

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
$ lap compile specs/stripe-charges.yaml -o output/stripe.lap
✓ Compiled stripe-charges.yaml → output/stripe.lap
✓ 5 endpoints | 4,291 chars | standard mode

# Lean mode
$ lap compile specs/stripe-charges.yaml --lean

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

### `lap validate`

Validate that LAP compilation preserves all information from the source spec.

```
lap validate [-h] spec
```

**Example:**

```bash
$ lap validate specs/stripe-charges.yaml

  Check               Result   Status
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoints       5/5 (100%)     ✅
  Parameters    32/32 (100%)     ✅
  Error Codes     8/8 (100%)     ✅

PASS — Zero information loss!
```

---

### `lap benchmark`

Benchmark token usage comparing verbose docs vs LAP for a single spec.

```
lap benchmark [-h] spec
```

**Example:**

```bash
$ lap benchmark specs/stripe-charges.yaml

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

### `lap benchmark-all`

Benchmark all specs in a directory.

```
lap benchmark-all [-h] directory
```

**Example:**

```bash
$ lap benchmark-all specs/
```

---

### `lap inspect`

Parse and display a LAP file in a structured, readable format.

```
lap inspect [-h] [--endpoint ENDPOINT] file
```

| Argument | Description |
|----------|-------------|
| `file` | Path to `.lap` file |
| `-e, --endpoint` | Filter to specific endpoint, e.g. `"POST /v1/charges"` |

**Example:**

```bash
$ lap inspect output/stripe-charges.lap

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
$ lap inspect output/stripe-charges.lap -e "POST /v1/charges"
```

---

### `lap convert`

Convert a LAP file back to OpenAPI format.

```
lap convert [-h] [-f FORMAT] [-o OUTPUT] file
```

| Argument | Description |
|----------|-------------|
| `file` | Path to `.lap` file |
| `-f, --format` | Output format (default: `openapi`) |
| `-o, --output` | Output file path |

**Example:**

```bash
$ lap convert output/stripe-charges.lap -f openapi -o stripe-roundtrip.yaml
```

---

### `lap diff`

Diff two LAP files to detect API changes.

```
lap diff [-h] [--format {summary,changelog}] [--version VERSION] old new
```

| Argument | Description |
|----------|-------------|
| `old` | Path to old `.lap` file |
| `new` | Path to new `.lap` file |
| `--format` | Output format: `summary` or `changelog` |
| `--version` | Version label for changelog output |

**Example:**

```bash
$ lap diff v1.lap v2.lap --format changelog --version "2.0"
```

---

### `lap registry`

Registry operations for browsing compiled specs.

#### `lap registry list`

```
lap registry list [-h] directory
```

**Example:**

```bash
$ lap registry list output/
```

#### `lap registry search`

```
lap registry search [-h] directory query
```

**Example:**

```bash
$ lap registry search output/ "create"
```

---

### `lap lap`

Compile, parse, and inspect LAP tool manifests.

#### `lap lap compile-mcp`

Compile an MCP server tool manifest to LAP format.

```
lap lap compile-mcp [-h] [-o OUTPUT] [--lean] input
```

| Argument | Description |
|----------|-------------|
| `input` | Path to MCP manifest JSON |
| `-o, --output` | Output file path (default: stdout) |
| `--lean` | Strip descriptions for maximum compression |

**Example:**

```bash
$ lap lap compile-mcp mcp-server-tools.json -o tools.lap

@lap v0.1
@tool read_file
@desc Read complete contents of a file
@in path:str File path to read

@lap v0.1
@tool write_file
@desc Create or overwrite a file
@in path:str File path to write
@in content:str Content to write
```

#### `lap lap compile-skill`

Compile an OpenClaw/ClawHub SKILL.md to LAP format.

```
lap lap compile-skill [-h] [-o OUTPUT] [--lean] input
```

**Example:**

```bash
$ lap lap compile-skill SKILL.md -o skill.lap
```

#### `lap lap compile-json`

Compile a generic JSON tool definition to LAP format.

```
lap lap compile-json [-h] [-o OUTPUT] [--lean] input
```

**Example:**

```bash
$ lap lap compile-json tool.json -o tool.lap
```

#### `lap lap parse`

Parse a LAP file and display structured tool information.

```
lap lap parse [-h] input
```

**Example:**

```bash
$ lap lap parse tools.lap

Tool: read_file
  Desc: Read complete contents of a file
  Auth: none
  Tags: []
  Inputs: 1
    path: str — File path to read
  Outputs: 0
```

#### `lap lap stats`

Show size and tool statistics for a LAP file.

```
lap lap stats [-h] input
```

**Example:**

```bash
$ lap lap stats tools.lap

File: tools.lap
Size: 240 bytes
Tools: 2
Total params: 3
```
