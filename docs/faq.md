# Frequently Asked Questions

## How is this different from OpenAPI?

**OpenAPI describes APIs for humans and tools. LAP describes APIs for LLM agents.**

OpenAPI is the source of truth — it powers code generators, API gateways, documentation sites, mock servers, and SDK generators. LAP doesn't replace any of that. LAP *compiles* OpenAPI into a format optimized for LLM consumption.

Think of it like the relationship between TypeScript and JavaScript: TypeScript is the source, JavaScript is the compiled output for a specific runtime. OpenAPI is the source, LAP is the compiled output for the LLM runtime.

You keep your OpenAPI specs. You keep all your OpenAPI tooling. LAP just adds a compilation step for agent use cases.

## How is this different from MCP?

**MCP and LAP solve different problems and work together.**

- **MCP** (Model Context Protocol) defines how agents discover and invoke tools — it's the *plumbing* for tool use
- **LAP** compresses the *documentation* that those tools expose

An MCP tool has an `inputSchema` (JSON Schema) and a description. LAP makes those descriptions more compact and typed. The MCP integration (`integrations/mcp/`) shows this: LAP endpoints become MCP tools with compressed schemas.

They're complementary, not competing.

## What about prompt caching?

**Prompt caching reduces cost on repeated calls. LAP reduces cost on every call.**

Anthropic's prompt caching gives ~90% discount on cached prefixes. This is great for repeated identical prompts. But:

1. **First call is still full price** — LAP reduces that first-call cost
2. **Cache invalidation** — any change to the prefix invalidates the cache. Shorter prefixes = more cache hits
3. **Different APIs per call** — if your agent queries different APIs each time, caching doesn't help. LAP does.
4. **Context window pressure** — even with caching, a 50K-token API spec takes up context space. Compression frees that space for actual conversation

In practice, use both: compress with LAP, then cache the compressed version. They stack.

## Will LLMs understand LAP format?

**Yes. Extensively tested.**

LAP is deliberately designed to be LLM-readable. The format uses conventions LLMs already understand:

- `@directive` syntax (familiar from many DSLs)
- `{name: type}` parameter notation (JSON-like)
- `# inline comments` (universal)
- HTTP methods and paths (every LLM knows REST)

From our benchmarks with GPT-4o and Claude: agents correctly parse LAP and make valid API calls with the same or higher accuracy as when given verbose documentation. The typed contracts actually *reduce* errors — an agent seeing `amount: int` is less likely to pass a string than one reading a paragraph of prose.

## What if token costs keep dropping?

**The cost argument is the least important argument for LAP.**

Yes, GPT-4o is $2.50/M input tokens and dropping. Yes, Gemini offers 1M+ context windows. The cost savings headline ($1.3M/year at scale) will shrink as prices drop.

But LAP's core value isn't cost savings — it's **typed contracts**:

1. **Correctness** — `status: enum(succeeded|pending|failed)` prevents hallucinated values. No amount of cheaper tokens fixes hallucination.
2. **Deterministic parsing** — LAP has a formal grammar. You can parse it into an AST with code, not with an LLM. Try parsing a Stripe docs page deterministically.
3. **Schema diffing** — structured specs enable breaking change detection, changelogs, compatibility checking. You can't diff two markdown pages meaningfully.
4. **Speed** — fewer input tokens = faster time-to-first-token. Latency matters in agentic workflows regardless of cost.

Even if tokens were free, you'd still want typed, parseable API contracts over prose documentation.

## Can't I just minify OpenAPI?

**You can, and for simple cases that's fine.**

An OpenAPI minifier (strip descriptions, remove examples, dereference `$ref`) gets you maybe 1.5-2× compression while staying in the OpenAPI ecosystem. If that's enough, do it.

LAP goes further because it changes the *format*, not just strips content:

- Parameter lists become `{amount: int, currency: str}` instead of nested YAML
- Types become compact tokens (`str`, `int`, `bool`) instead of `{"type": "string"}`
- Enums become `enum(a|b|c)` instead of `{"enum": ["a", "b", "c"]}`
- The format is line-oriented and grep-able

The result is a format that's both more compact AND more readable for both humans and LLMs.

## What about the missing features vs JSON Schema?

*This is a fair criticism from [the Reddit review](../reviews/reddit-roast.md).*

LAP's type system is intentionally minimal. It doesn't support:
- `oneOf`/`anyOf`/`allOf` polymorphism
- `pattern` regex validation
- `minimum`/`maximum` constraints
- `$ref` for schema reuse
- `additionalProperties` control

**This is by design, not by accident.** These features exist in JSON Schema because *code validators* need them. LLM agents don't validate schemas — they need to know what to send and what to expect back. For that purpose, `amount: int` is sufficient; `{"type": "integer", "minimum": 1, "maximum": 999999}` is noise.

That said, format hints like `str(email)` and `int(unix-timestamp)` do convey *semantic* constraints that agents benefit from. We may add more constraint syntax in future versions where it demonstrably improves agent accuracy.

## What about the benchmarks?

*Being honest about the [Reddit critique](../reviews/reddit-roast.md):*

The early benchmarks compared against a "verbose" baseline that was generated, not real human documentation. The 3.6× headline number was against this synthetic baseline.

Current benchmarks compare LAP against the raw OpenAPI YAML spec, which is a fairer comparison. Compression ratios vary by API — simple APIs see less benefit, complex APIs with long descriptions see more.

The validation numbers are real: 100% endpoint, parameter, and error code preservation is checked automatically on every compilation.

## Who should use this today?

LAP is most valuable if you:

1. **Run agents at scale** — thousands of API calls/day where token costs and latency compound
2. **Build multi-API agents** — agents that need to know many APIs, filling context windows
3. **Need API change detection** — monitoring third-party APIs for breaking changes
4. **Want typed contracts** — reducing hallucination in agent API calls

If you're making 10 API calls a day with a single LLM, you probably don't need this. OpenAPI or raw docs is fine.

## Will API providers adopt this?

**They don't have to.** That's the key design decision.

LAP compiles *from* OpenAPI. API providers don't need to change anything. If an API publishes an OpenAPI spec (and most do), you can compile it to LAP yourself.

The registry and pre-compiled specs are a convenience, not a requirement. The compiler is the product.
