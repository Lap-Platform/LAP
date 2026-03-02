# Original Documentation Sources

This directory documents the "original" documentation format for each spec type used in LAP benchmarks. The purpose is to ensure benchmarks compare local-to-local (no network fetching skewing results).

## Structure

```
specs/originals/
├── openapi/         # Human-readable markdown docs for OpenAPI specs
├── graphql/         # GraphQL schema documentation
├── asyncapi/        # AsyncAPI documentation
├── postman/         # Postman collection documentation
└── protobuf/        # Protobuf documentation
```

## What is "Original Documentation"?

For each spec type, the "original" refers to:

### OpenAPI
- **Spec**: `specs/*.yaml` (structured OpenAPI YAML)
- **Original docs**: Human-readable markdown from API provider websites (e.g., docs.stripe.com, docs.github.com)
- **Location**: `specs/real-docs/*.md` (existing) and this directory (organized)
- **Format**: Markdown prose describing endpoints, parameters, responses

### GraphQL
- **Spec**: `specs/graphql/*.graphql` (GraphQL SDL schema)
- **Original docs**: The schema itself IS the original + any schema documentation comments
- **Note**: GraphQL schemas are self-documenting through descriptions and comments

### AsyncAPI
- **Spec**: `specs/asyncapi/*.yaml` (structured AsyncAPI YAML)
- **Original docs**: Similar to OpenAPI - vendor documentation if available
- **Note**: Most AsyncAPI specs in this repo are synthetic examples

### Postman
- **Spec**: `specs/postman/*.json` (Postman Collection v2.1 format)
- **Original docs**: Collection descriptions + request documentation within JSON
- **Note**: Postman collections embed documentation in the JSON itself

### Protobuf
- **Spec**: `specs/protobuf/*.proto` (Protocol Buffer definitions)
- **Original docs**: The .proto files with comments ARE the original documentation
- **Note**: Protobuf documentation is inline via comments

## Real vs Synthetic Specs

### Real Specs (from actual APIs)
These have corresponding "original" documentation from vendor websites:
- `specs/openai-core.yaml` → `specs/real-docs/openai-core.md`
- `specs/github-core.yaml` → `specs/real-docs/github-core.md`
- `specs/stripe-charges.yaml` → `specs/real-docs/stripe-charges.md`

### Synthetic Specs (examples/tests)
Most specs in this repo are synthetic test cases:
- `specs/petstore.yaml` - Standard OpenAPI example
- `specs/graphql/ecommerce.graphql` - Synthetic GraphQL schema
- `specs/asyncapi/chat-websocket.yaml` - Example AsyncAPI spec
- `specs/postman/crud-api.json` - Example Postman collection
- `specs/protobuf/chat.proto` - Example proto definition

For synthetic specs, the spec file itself IS the original documentation source.

## Benchmark Usage

When benchmarks run, they should:
1. **For real specs with human docs**: Compare DocLean output against `specs/real-docs/*.md`
2. **For synthetic specs**: Compare DocLean output against the generated verbose representation
3. **Never fetch from network**: All comparisons must be local-to-local

## Adding New Real Docs

When adding documentation for a real API:

1. Fetch the official docs (e.g., from docs.stripe.com)
2. Save as markdown in `specs/real-docs/{api-name}.md`
3. Include source URL and fetch date in the markdown header
4. Update this README to document the mapping

Example header:
```markdown
# Stripe Charges API Documentation

Source: https://stripe.com/docs/api/charges (fetched 2026-02-08)
```
