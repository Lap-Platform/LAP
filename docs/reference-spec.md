# LAP Format Specification Reference

## Quick Reference Card

### Header Directives

```
@lap v0.1              # Format version (required, first line)
@api <name>                # API name
@base <url>                # Base URL for all endpoints
@version <version>         # API version string
@auth <scheme> <token>     # Authentication scheme
```

### Endpoint Directives

```
@endpoint <METHOD> <path>                    # Endpoint definition
@desc <text>                                 # Description (standard mode only)
@required {param: type, ...}                 # Required parameters
@optional {param: type, ...}                 # Optional parameters
@body {field: type, ...}                     # Request body schema
@returns(<code>) {field: type, ...}          # Response schema
@returns(<code>) <description>               # Response with description only
@errors {<code>: <message>, ...}             # Error codes (standard)
@errors {<code>, ...}                        # Error codes (lean)
```

### Parameter Syntax

```
name: type                    # Basic parameter
name: type # description      # With inline comment
name: type?                   # Nullable
name: type=default            # With default value
name: type(format)            # With format hint
name: enum(a|b|c)             # Enumeration
name: [type]                  # Array of type
name: map                     # Object/dictionary
name: map{key: type, ...}     # Object with known fields
```

---

## Type System Cheat Sheet

### Primitive Types

| LAP | JSON Schema | Description |
|---------|------------|-------------|
| `str` | `string` | String value |
| `int` | `integer` | Integer value |
| `num` | `number` | Floating-point number |
| `bool` | `boolean` | Boolean (true/false) |
| `map` | `object` | Key-value object |
| `any` | `{}` | Any type |

### Modifiers

| Syntax | Meaning | Example |
|--------|---------|---------|
| `type?` | Nullable | `email: str?` |
| `[type]` | Array | `tags: [str]` |
| `type=val` | Default value | `limit: int=10` |
| `type(fmt)` | Format hint | `created: int(unix-timestamp)` |
| `enum(a\|b)` | Enum constraint | `status: enum(active\|inactive)` |

### Format Hints

Common format hints used with types:

| Format | Applied to | Example |
|--------|-----------|---------|
| `email` | `str` | `str(email)` |
| `uri` | `str` | `str(uri)` |
| `uuid` | `str` | `str(uuid)` |
| `date` | `str` | `str(date)` |
| `date-time` | `str` | `str(date-time)` |
| `unix-timestamp` | `int` | `int(unix-timestamp)` |
| `ISO4217` | `str` | `str(ISO4217)` |

### Nested Objects

Objects with known fields use `map{...}` syntax:

```
billing_details: map{name: str?, email: str?, phone: str?, address: map}
outcome: map{network_status: str, risk_level: str, risk_score: int, type: str}
```

### Complete Example

```
@lap v0.1
@api Stripe Charges API
@base https://api.stripe.com
@version 2024-12-18
@auth Bearer bearer

@endpoint POST /v1/charges
@desc Create a charge
@required {amount: int # Amount in cents., currency: str(ISO4217)}
@optional {source: str, customer: str, description: str, metadata: map,
           capture: bool, transfer_data: map, application_fee_amount: int}
@returns(200) {id: str, object: str, amount: int, amount_captured: int,
               currency: str, customer: str?, status: enum(succeeded|pending|failed),
               paid: bool, captured: bool, livemode: bool, metadata: map,
               created: int(unix-timestamp),
               billing_details: map{name: str?, email: str?, address: map},
               outcome: map{network_status: str, risk_level: str, risk_score: int}}
@errors {400: Invalid request., 401: Auth failed., 402: Card declined., 429: Rate limited.}

@endpoint GET /v1/charges
@desc List all charges
@optional {customer: str, limit: int=10, starting_after: str, ending_before: str}
@returns(200) Returns a list of charge objects.
@errors {401: Auth failed.}
```

---

## Compression Levels

| Level | Name | Content | Use Case |
|-------|------|---------|----------|
| L0 | Markdown | Human-readable docs | Documentation sites |
| L1 | LAP Standard | Typed contract + descriptions | Development, debugging |
| L2 | LAP Lean | Typed contract, no descriptions | Production agents |
| L3 | SHA-256 Reference | Content-addressable hash | Registry lookups, caching |

### Content Negotiation

LAP supports MIME-type content negotiation:

```
Accept: application/lap; level=2; q=1.0,
        application/lap; level=1; q=0.8,
        application/openapi+yaml; q=0.5
```

## Grammar (EBNF Summary)

```ebnf
document     = header, { endpoint_block } ;
header       = "@lap", version, { header_dir } ;
header_dir   = "@api" | "@base" | "@version" | "@auth" ;
endpoint_block = "@endpoint", method, path, { endpoint_dir } ;
endpoint_dir = "@desc" | "@required" | "@optional" | "@body"
             | "@returns" | "@errors" ;
param_list   = "{", param, { ",", param }, "}" ;
param        = name, ":", type, [ "?"] , [ "=", default ], [ "#", comment ] ;
type         = primitive | array_type | map_type | enum_type | format_type ;
primitive    = "str" | "int" | "num" | "bool" | "map" | "any" ;
array_type   = "[", type, "]" ;
map_type     = "map", [ "{", param, { ",", param }, "}" ] ;
enum_type    = "enum(", value, { "|", value }, ")" ;
format_type  = primitive, "(", format_hint, ")" ;
```
