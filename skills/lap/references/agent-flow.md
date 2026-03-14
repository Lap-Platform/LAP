# Agent Flow -- Discovering and Using APIs

This reference covers the full workflow for AI agents consuming APIs through LAP.

---

## Step 1: Discover APIs

### Basic Search

```bash
lapsh search payment
lapsh search "email sending"
lapsh search stripe
```

### Filtered Search

```bash
# By tag
lapsh search api --tag fintech
lapsh search api --tag ai

# By popularity
lapsh search payment --sort popularity

# Paginated
lapsh search api --limit 10 --offset 20
```

### JSON Output for Scripting

```bash
# All results as JSON
lapsh search payment --json

# Extract names with skills
lapsh search payment --json | jq '.results[] | select(.has_skill) | .name'

# Get endpoint counts
lapsh search payment --json | jq '.results[] | {name, endpoints}'

# Find large APIs (50+ endpoints)
lapsh search api --json | jq '.results[] | select(.endpoints > 50) | .name'
```

### Reading Search Results

Human-readable output columns:
- **Name** -- API identifier (use with `get` and `skill-install`)
- **Endpoints** -- Number of endpoints in the spec
- **Ratio** -- Compression ratio vs. original spec
- **Description** -- Short summary
- **[skill]** -- Marker indicating a pre-built skill is available

---

## Step 2: Acquire the API

### Option A: Install a Pre-built Skill

Best when: the search result has a `[skill]` marker and you want to use the API immediately.

```bash
lapsh skill-install stripe
# Installs to ~/.claude/skills/stripe/
```

The installed skill contains:
- `SKILL.md` -- Metadata and usage instructions
- `references/` -- LAP spec and additional context

Custom install location:
```bash
lapsh skill-install stripe --dir ./project-skills/stripe
```

### Option B: Download the Spec

Best when: you need the raw LAP spec for custom processing or the API has no skill.

```bash
# Standard (includes descriptions)
lapsh get stripe -o stripe.lap

# Lean (maximum compression)
lapsh get stripe --lean -o stripe.lean.lap
```

**Standard vs. Lean:**
- **Standard**: Preserves descriptions, examples, and documentation. Better for understanding what an API does.
- **Lean**: Strips descriptions, keeps only structural information. 2-3x smaller than standard. Better when context window is tight.

### Option C: Compile a Local Spec

Best when: you have the original API spec file locally.

```bash
# Auto-detect format
lapsh compile petstore.yaml -o petstore.lap

# Lean mode
lapsh compile petstore.yaml -o petstore.lean.lap --lean

# Force format detection
lapsh compile spec.json -f openapi -o spec.lap

# Compile GraphQL schema
lapsh compile schema.graphql -o schema.lap

# Compile Postman collection
lapsh compile collection.json -f postman -o collection.lap
```

Supported source formats:
- OpenAPI 3.x (YAML or JSON)
- GraphQL SDL
- AsyncAPI
- Protobuf
- Postman Collection v2.x
- Smithy

---

## Step 3: Read the LAP Spec

LAP is a line-oriented, token-efficient format designed for AI consumption. You can read `.lap` files directly.

### Key Markers

| Marker | Purpose | Example |
|--------|---------|---------|
| `@api` | API name, version, base URL | `@api Stripe Charges v1 https://api.stripe.com` |
| `@toc` | Table of contents | `@toc GET /v1/charges -- List charges` |
| `@endpoint` | Endpoint definition | `@endpoint GET /v1/charges` |
| `@desc` | Description (standard mode only) | `@desc List all charges` |
| `@param` | Parameter | `@param query limit integer -- Max results` |
| `@body` | Request body | `@body application/json` |
| `@response` | Response definition | `@response 200 application/json` |
| `@required` | Required fields | `@required amount currency` |
| `@error` | Error response | `@error 401 -- Unauthorized` |
| `@field` | Object field | `@field id string -- Unique identifier` |
| `@auth` | Authentication | `@auth bearer` |

### Reading Strategy

1. Start with `@api` to understand the API identity and base URL
2. Scan `@toc` for a quick overview of all endpoints
3. Jump to specific `@endpoint` blocks as needed
4. Look at `@required` to understand mandatory fields
5. Check `@error` blocks for failure modes

---

## End-to-End Example

**Scenario**: "I need to integrate a payment API"

```bash
# 1. Search for payment APIs
lapsh search payment --sort popularity

# Output shows:
#   stripe        120 endpoints  5.8x  Stripe payment processing  [skill]
#   square        85 endpoints   4.2x  Square payments API        [skill]
#   ...

# 2. Install the Stripe skill (has [skill] marker)
lapsh skill-install stripe

# 3. The skill is now at ~/.claude/skills/stripe/
# Claude Code auto-discovers it for Stripe API tasks

# Alternative: get the raw spec for custom use
lapsh get stripe -o stripe.lap

# Or compile a local spec you already have
lapsh compile my-openapi.yaml -o my-api.lap --lean
```

**Scenario**: "Find me an AI/ML API with a skill"

```bash
# Search with tag filter
lapsh search ai --tag ai --json | jq '.results[] | select(.has_skill) | {name, endpoints, description}'

# Install the one you want
lapsh skill-install openai
```

---

## Tips

- Always check for `[skill]` in search results before manually compiling -- pre-built skills save time
- Use `--lean` when context window is tight; use standard when you need to understand the API
- Pipe `--json` output through `jq` for programmatic discovery
- LAP specs are plain text -- you can grep, diff, and version-control them
- The `@toc` section gives you a quick overview without reading the entire spec
