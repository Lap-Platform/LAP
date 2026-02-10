# LAP Strategic Positioning

## The Problem

AI agents consume API documentation as unstructured text — markdown pages, verbose OpenAPI YAML, HTML docs. This causes systematic failures:

- **Wrong parameter types.** An agent reads "amount" and passes `10.00` (dollars) instead of `1000` (cents). Nothing in the prose enforced the unit.
- **Hallucinated values.** An agent guesses `status: "success"` when the API only accepts `succeeded|pending|failed`. Prose docs mentioned the field but not the enum.
- **Missed constraints.** A required field was buried in paragraph 3 of a description. The agent skipped it. 400 error.
- **Ambiguous semantics.** Does `null` mean "not provided" or "explicitly empty"? The docs don't say. The agent guesses wrong.

These aren't edge cases. They're the default failure mode when agents interpret prose documentation at scale.

## The Solution

**Compiled, typed API contracts that agents can parse deterministically.**

LAP is a structured format where:
- Every field has a concrete type: `amount: int`, `email: str(email)`, `status: enum(succeeded|pending|failed)`
- Required vs optional is explicit: `@required` vs `@optional`
- Nullable fields are marked: `str?`
- Error contracts are enumerated: `@errors {400, 401, 402, 429}`
- Response schemas are typed: `@returns(200) {id: str, amount: int, status: str}`

A LAP file isn't documentation — it's a **contract**. And it has a formal grammar and a working parser, so it can be consumed by code, not just by LLMs.

## Why Not Just OpenAPI?

OpenAPI is excellent for what it was designed for: code generators, documentation sites, and human developers. But it's a poor fit for LLM agent consumption:

| | OpenAPI | LAP |
|---|---|---|
| **Designed for** | Code generators, humans | LLM agents |
| **Verbosity** | High (YAML boilerplate, nested schemas, $ref indirection) | Minimal (line-oriented, flat structure) |
| **Parsability** | Requires YAML parser + OpenAPI resolver | Parsable with simple line-oriented grammar |
| **Agent-specific annotations** | None | Compression levels, content negotiation, cached references |
| **Token cost** | 2,000+ tokens for a typical API | 500-700 tokens for the same API |

OpenAPI wasn't wrong — it was designed for a different consumer. LAP is designed for the consumer that's growing fastest: autonomous agents.

## Competitive Landscape

### MCP (Model Context Protocol — Anthropic)

MCP defines how agents **connect to** tools and data sources. It's a transport and capability protocol. LAP defines how agents **understand** the APIs they're calling. They're complementary:

- MCP says "here's a tool you can call"
- LAP says "here's exactly what that tool expects, in a typed contract"

A LAP spec can be served *through* MCP as a tool description. LAP makes MCP tools more precise.

### A2A (Agent-to-Agent — Google)

A2A defines how agents discover and communicate with each other. Agent Cards describe capabilities at a high level. LAP operates at a lower level — the specific API contracts those agents use. A2A tells you *what* an agent can do; LAP tells you *exactly how* to ask it.

### Function Calling Schemas (OpenAI, Anthropic, Google)

Native function calling provides parameter schemas, but these are per-tool, per-provider, and lack cross-provider standardization. LAP is provider-agnostic and includes response schemas, error contracts, and versioning — none of which function calling schemas provide.

## The Moat

The protocol itself is simple (by design). The moat is:

1. **The registry.** A curated, maintained, versioned collection of pre-compiled API contracts for popular APIs. Writing a good LAP spec for Stripe takes expertise — understanding which fields matter, what the edge cases are, how errors actually behave. This is a data asset that compounds.

2. **Framework integrations.** Native adapters for LangChain, CrewAI, AutoGen, and other agent frameworks. Once agents consume LAP natively, the switching cost is real.

3. **Versioning and compatibility tooling.** Schema diffing, breaking change detection, compatibility matrices. This tooling only works because LAP is structured — you can't build it on top of prose docs.

4. **Network effects.** As more APIs publish LAP specs and more frameworks consume them, the format becomes the lingua franca for agent-API interaction. The first structured format with broad adoption wins.

## The Pitch (One Sentence)

**LAP gives AI agents typed API contracts instead of prose documentation — eliminating ambiguity, enabling deterministic parsing, and making API consumption reliable at scale.**
