# CLI Reference

## Overview

```
lap [-h] {compile,validate,benchmark,benchmark-all,inspect,convert,diff,registry,toollean} ...
```

## Commands

### `lap compile`

Compile an OpenAPI spec to DocLean format.

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

@doclean v0.1
@api Stripe Charges API
@base https://api.stripe.com
@version 2024-12-18
@auth Bearer bearer

@endpoint POST /v1/charges
@desc Create a charge
@required {amount: int # Amount intended to be collected by this payment, in cents., currency: str # Three-letter ISO 4217 currency code, in lowercase.}
...

# Compile to file
$ lap compile specs/stripe-charges.yaml -o output/stripe.doclean
✓ Compiled stripe-charges.yaml → output/stripe.doclean
✓ 5 endpoints | 4,291 chars | standard mode

# Lean mode
$ lap compile specs/stripe-charges.yaml --lean

@doclean v0.1
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

Validate that DocLean compilation preserves all information from the source spec.

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

Benchmark token usage comparing verbose docs vs DocLean for a single spec.

```
lap benchmark [-h] spec
```

**Example:**

```bash
$ lap benchmark specs/stripe-charges.yaml

📊 LAP DocLean Token Benchmark

📏 Character Count:
  Raw OpenAPI spec:      11,160 chars
  Verbose (human-readable):    3,536 chars
  DocLean (compressed):    4,291 chars

🔢 Token Counts:
  Model                   Verbose    DocLean  Reduction    Ratio
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

Parse and display a DocLean file in a structured, readable format.

```
lap inspect [-h] [--endpoint ENDPOINT] file
```

| Argument | Description |
|----------|-------------|
| `file` | Path to `.doclean` file |
| `-e, --endpoint` | Filter to specific endpoint, e.g. `"POST /v1/charges"` |

**Example:**

```bash
$ lap inspect output/stripe-charges.doclean

╭──────────────────────── DocLean Spec ────────────────────────╮
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
$ lap inspect output/stripe-charges.doclean -e "POST /v1/charges"
```

---

### `lap convert`

Convert a DocLean file back to OpenAPI format.

```
lap convert [-h] [-f FORMAT] [-o OUTPUT] file
```

| Argument | Description |
|----------|-------------|
| `file` | Path to `.doclean` file |
| `-f, --format` | Output format (default: `openapi`) |
| `-o, --output` | Output file path |

**Example:**

```bash
$ lap convert output/stripe-charges.doclean -f openapi -o stripe-roundtrip.yaml
```

---

### `lap diff`

Diff two DocLean files to detect API changes.

```
lap diff [-h] [--format {summary,changelog}] [--version VERSION] old new
```

| Argument | Description |
|----------|-------------|
| `old` | Path to old `.doclean` file |
| `new` | Path to new `.doclean` file |
| `--format` | Output format: `summary` or `changelog` |
| `--version` | Version label for changelog output |

**Example:**

```bash
$ lap diff v1.doclean v2.doclean --format changelog --version "2.0"
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

### `lap toollean`

Compile, parse, and inspect ToolLean tool manifests.

#### `lap toollean compile-mcp`

Compile an MCP server tool manifest to ToolLean format.

```
lap toollean compile-mcp [-h] [-o OUTPUT] [--lean] input
```

| Argument | Description |
|----------|-------------|
| `input` | Path to MCP manifest JSON |
| `-o, --output` | Output file path (default: stdout) |
| `--lean` | Strip descriptions for maximum compression |

**Example:**

```bash
$ lap toollean compile-mcp mcp-server-tools.json -o tools.toollean

@toollean v0.1
@tool read_file
@desc Read complete contents of a file
@in path:str File path to read

@toollean v0.1
@tool write_file
@desc Create or overwrite a file
@in path:str File path to write
@in content:str Content to write
```

#### `lap toollean compile-skill`

Compile an OpenClaw/ClawHub SKILL.md to ToolLean format.

```
lap toollean compile-skill [-h] [-o OUTPUT] [--lean] input
```

**Example:**

```bash
$ lap toollean compile-skill SKILL.md -o skill.toollean
```

#### `lap toollean compile-json`

Compile a generic JSON tool definition to ToolLean format.

```
lap toollean compile-json [-h] [-o OUTPUT] [--lean] input
```

**Example:**

```bash
$ lap toollean compile-json tool.json -o tool.toollean
```

#### `lap toollean parse`

Parse a ToolLean file and display structured tool information.

```
lap toollean parse [-h] input
```

**Example:**

```bash
$ lap toollean parse tools.toollean

Tool: read_file
  Desc: Read complete contents of a file
  Auth: none
  Tags: []
  Inputs: 1
    path: str — File path to read
  Outputs: 0
```

#### `lap toollean stats`

Show size and tool statistics for a ToolLean file.

```
lap toollean stats [-h] input
```

**Example:**

```bash
$ lap toollean stats tools.toollean

File: tools.toollean
Size: 240 bytes
Tools: 2
Total params: 3
```
