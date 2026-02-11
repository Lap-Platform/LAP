# LAP Format Specification v0.3

## Abstract

LAP (LLM API Protocol) is a line-oriented, directive-based text format for describing HTTP APIs in a form optimized for machine consumption. It achieves 60–80% token reduction over OpenAPI/JSON while preserving full structural fidelity, enabling round-trip conversion and direct tool-call generation by LLM agents.

## 1. Goals & Non-Goals

### Goals
- Minimal token footprint for LLM context windows
- Human-readable without tooling
- Lossless round-trip: OpenAPI → LAP → structured data
- Self-describing completeness (parsers can detect truncation)
- Two verbosity modes (standard and lean)

### Non-Goals
- Replacing OpenAPI as a source-of-truth format
- Supporting non-HTTP protocols (gRPC is compiled to HTTP-equivalent)
- Inline request/response examples (use `@example_request` sparingly)
- Schema reuse across files (single-document scope)

## 2. Document Structure

A LAP document is a sequence of UTF-8 lines. Each meaningful line is either a **directive** (prefixed with `@`), a **comment** (prefixed with `#`), or blank (ignored).

```
Document     ::= Preamble EndpointBlock* '@end' NL
Preamble     ::= VersionLine Comment? Header* CountLine TOCLine?
VersionLine  ::= '@lap' SP VERSION NL
Header       ::= ('@api' | '@base' | '@version' | '@auth') SP VALUE NL
CountLine    ::= '@endpoints' SP INTEGER NL
TOCLine      ::= '@toc' SP TocEntry (',' SP TocEntry)* NL
TocEntry     ::= IDENT '(' INTEGER ')'
```

## 3. Grammar (EBNF)

```ebnf
(* Primitives *)
NL           = '\n'
SP           = ' '+
IDENT        = [a-zA-Z_$] [a-zA-Z0-9_$.-:]*
VERSION      = 'v' DIGIT+ '.' DIGIT+
INTEGER      = DIGIT+
VALUE        = <any characters to end of line>
COMMENT      = '#' SP VALUE NL

(* Preamble *)
Document     = '@lap' SP VERSION NL
               { COMMENT }
               '@api' SP VALUE NL
               [ '@base' SP VALUE NL ]
               [ '@version' SP VALUE NL ]
               [ '@auth' SP VALUE NL ]
               [ CommonFields ]
               '@endpoints' SP INTEGER NL
               [ '@hint' SP VALUE NL ]
               [ '@toc' SP TocList NL ]
               { TypeDef }
               { GroupOrEndpoint }
               '@end' NL

CommonFields = '@common_fields' SP BracedParams NL
TypeDef      = '@type' SP IDENT SP BracedFields NL

(* Grouping *)
GroupOrEndpoint = Group | EndpointBlock
Group        = '@group' SP IDENT NL EndpointBlock+ '@endgroup' NL

(* Endpoint *)
EndpointBlock = '@endpoint' SP METHOD SP PATH NL
                [ '@desc' SP VALUE NL ]
                [ '@auth' SP VALUE NL ]
                [ '@body' SP '→' SP IDENT NL ]
                [ '@required' SP BracedParams NL ]
                [ '@optional' SP BracedParams NL ]
                { ReturnsLine }
                [ ErrorsLine ]
                [ '@example_request' SP VALUE NL ]

METHOD       = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS'
PATH         = '/' { PATHSEG | PATHPARAM }
PATHSEG      = [a-zA-Z0-9._-]+
PATHPARAM    = '{' IDENT '}'

(* Parameters *)
BracedParams = '{' ParamDef { ',' SP ParamDef } '}'
ParamDef     = IDENT ':' SP Type [ '=' DEFAULT ] [ SP COMMENT ]
DEFAULT      = <non-whitespace token>

(* Returns & Errors *)
ReturnsLine  = '@returns(' CODE ')' [ SP ( BracedFields [ SP COMMENT ] | VALUE ) ] NL
ErrorsLine   = '@errors' SP '{' ErrorEntry { ',' SP ErrorEntry } '}' NL
ErrorEntry   = CODE [ ':' TYPE ] [ ':' SP VALUE ]
CODE         = DIGIT+

(* Fields *)
BracedFields = '{' FieldDef { ',' SP FieldDef } '}'
FieldDef     = IDENT ':' SP Type [ '?' ] [ BracedFields ]
```

## 4. Type System

| Notation | Meaning |
|---|---|
| `str` | String |
| `int` | Integer |
| `float` | Floating-point number |
| `bool` | Boolean |
| `map` | Key-value object (untyped) |
| `[T]` | Array of type T |
| `enum(a/b/c)` | Enumeration, slash-delimited |
| `str(format)` | String with format hint, e.g. `str(email)`, `str(uuid)` |
| `int(format)` | Integer with format hint, e.g. `int(unix-timestamp)`, `int(int64)` |
| `T?` | Nullable — field may be null |
| `map{...}` | Typed nested object with inline field definitions |

**Custom types** may be defined with `@type Name {fields}` and referenced by name (uppercase-initial identifier).

## 5. Directive Reference

### Preamble Directives

| Directive | Required | Description |
|---|---|---|
| `@lap <version>` | ✅ | Format version. MUST be the first non-blank line. |
| `@api <name>` | ✅ | Human-readable API name. |
| `@base <url>` | | Base URL for all endpoints. |
| `@version <string>` | | API version identifier. |
| `@auth <scheme>` | | Default authentication scheme (e.g. `Bearer bearer`, `ApiKey header:X-Api-Key`). |
| `@common_fields {…}` | | Parameters implicitly available on all endpoints. |
| `@endpoints <n>` | ✅ | Declared endpoint count. Enables truncation detection. |
| `@hint <token>` | | Processing hint (e.g. `download_for_search` for large specs). |
| `@toc <entries>` | | Table of contents: `group(count), group(count)`. |
| `@type <Name> {…}` | | Reusable named type definition. |

### Endpoint Directives

| Directive | Scope | Description |
|---|---|---|
| `@endpoint <METHOD> <PATH>` | | Begins an endpoint block. |
| `@desc <text>` | endpoint | One-line summary. |
| `@auth <scheme>` | endpoint | Override preamble auth for this endpoint. |
| `@body → <TypeName>` | endpoint | Request body references a named `@type`. |
| `@required {…}` | endpoint | Required parameters (path, query, or body). |
| `@optional {…}` | endpoint | Optional parameters with defaults and descriptions. |
| `@returns(<code>) …` | endpoint | Response contract. May include `{fields}` or text description. |
| `@errors {…}` | endpoint | Error codes with optional type and description. |
| `@example_request <text>` | endpoint | Inline request example (omitted in lean mode). |

### Structural Directives

| Directive | Description |
|---|---|
| `@group <name>` | Begin a named endpoint group. |
| `@endgroup` | End the current group. |
| `@end` | Document terminator. MUST be the last directive. |

## 6. Lean vs Standard Mode

LAP supports two serialization modes from the same data model:

| Feature | Standard | Lean |
|---|---|---|
| `@desc` summaries | ✅ | ❌ omitted |
| `# comment` on params | ✅ | ❌ omitted |
| `# comment` on returns | ✅ | ❌ omitted |
| Error descriptions | ✅ | ❌ codes only |
| Response descriptions | ✅ | ❌ omitted |
| `@example_request` | ✅ | ❌ omitted |

Lean mode targets minimum token count for context-constrained scenarios. Both modes are syntactically valid LAP.

## 7. Completeness Signals

LAP provides three mechanisms to detect incomplete or truncated documents:

1. **`@endpoints <n>`** — Declared count. A parser SHOULD warn if the actual endpoint count differs.
2. **`@end`** — Terminal marker. Absence indicates truncation.
3. **`@toc`** — Group-level summary. Enables partial validation even if endpoints are streamed.

## 8. Examples

### Example 1: Stripe Charges (Standard Mode)

```
@lap v0.3
# Machine-readable API spec. Each @endpoint block is one API call.
@api Stripe Charges API
@base https://api.stripe.com
@version 2024-12-18
@auth Bearer bearer
@endpoints 5
@toc charges(5)

@endpoint POST /v1/charges
@desc Create a charge
@required {amount: int # Amount in cents., currency: str # ISO 4217 code.}
@optional {source: str # Payment source ID., customer: str, capture: bool}
@returns(200) {id: str, amount: int, currency: str, status: str, paid: bool}
@errors {400: Invalid request., 402: Card declined., 429: Too many requests.}

@endpoint GET /v1/charges/{charge}
@desc Retrieve a charge
@required {charge: str # Charge identifier.}
@returns(200) Returns the charge object.
@errors {404: Charge not found.}

@end
```

### Example 2: Minimal Key-Value Store (Lean Mode)

```
@lap v0.3
@api KV Store
@base https://kv.example.com/v1
@auth ApiKey header:X-Api-Key
@endpoints 3
@toc keys(3)

@endpoint GET /keys
@optional {prefix: str, limit: int=100}
@returns(200) {keys: [str], cursor: str?}

@endpoint GET /keys/{key}
@required {key: str}
@returns(200) {key: str, value: str, ttl: int?}
@errors {404}

@endpoint PUT /keys/{key}
@required {key: str, value: str}
@optional {ttl: int}
@returns(201)

@end
```

## 9. Media Type & File Extension

| Property | Value |
|---|---|
| MIME type | `text/x-lap` (recommended) or `application/x-lap` |
| File extension | `.lap` |
| Character encoding | UTF-8 (no BOM) |
| Line endings | LF (`\n`) preferred; CRLF tolerated |

## 10. Versioning

The `@lap` directive carries a semantic version. Minor versions (v0.3 → v0.4) add directives but do not remove or change existing ones. Parsers SHOULD ignore unrecognized directives and continue processing.

---

*LAP Format Specification v0.3 — February 2026*
