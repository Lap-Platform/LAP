# LAP (LeanAgent Protocol): A Brutal Takedown

*Posted to r/programming by u/seen_it_all_before · 2026-02-08*

---

Oh good, another "revolutionary protocol" that's going to change everything. Let me just add it to my graveyard spreadsheet between SOAP and GraphQL subscriptions. Let's do this.

---

## 1. "This Already Exists"

Congratulations, you invented **minified OpenAPI**. Truly groundbreaking work.

Let's count the prior art:

- **OpenAPI itself** already has tooling to strip descriptions and produce minimal specs. `openapi-filter`, `swagger-cli bundle --dereference`. Done. Took 30 seconds.
- **Protocol Buffers / gRPC** — Google solved the "compact API description" problem in 2008. It's called `.proto` files. They're already compact, typed, and have actual adoption.
- **JSON Schema** with `additionalProperties: false` and no `description` fields — wow, that's basically your "Lean mode" but it works with every tool ever made.
- **API Blueprint**, **RAML**, **API.json** — remember these? No? Exactly. They all tried to be "better than OpenAPI" and they're all dead. But sure, yours will be different.
- **Anthropic's own Model Context Protocol (MCP)** already has tool schemas that are compact JSON. Your employer literally ships a competing approach.
- **LLM function calling schemas** (OpenAI, Claude, Gemini) — these are already stripped-down JSON schemas. The "compression" you're benchmarking against is the *input format nobody actually feeds to models*.
- Just... **gzip**. Have you tried gzip? OpenAPI YAML gzips beautifully. And the model doesn't care about token count if you're doing retrieval-augmented generation.

The entire value proposition is "we made a DSL that's shorter than YAML." That's not a protocol. That's a text editor macro.

## 2. "The Benchmarks Are Misleading"

Oh boy, where to start.

**The "Human Docs" baseline is fabricated.** From BENCHMARKS.md: *"Human docs tokens estimated at ~1.8x verbose generated text."* ESTIMATED. You didn't actually measure human documentation. You took your OpenAPI specs and applied a *multiplier*. That's not a benchmark, that's creative writing. 

**You're comparing against bloated OpenAPI, not realistic OpenAPI.** Real production specs aren't what `swagger-codegen` barfs out. Competent API teams already strip redundant descriptions, use `$ref` heavily, and keep specs lean. Your 3.6× compression is against a strawman.

**The test suite is 4 APIs (24 endpoints).** Sorry, 10 APIs if we count the README numbers that don't match the BENCHMARKS.md numbers (README says 46 endpoints across 10 APIs, BENCHMARKS.md says 24 endpoints across 4 APIs — pick a number, any number). Either way, this is a toy benchmark. Show me 500 APIs. Show me the gnarly ones — APIs with polymorphic responses, oneOf/anyOf schemas, deeply nested objects, XML content types, multipart uploads. You know, the stuff that actually makes API docs complicated.

**"Zero information loss" is doing heavy lifting.** You preserved endpoint names, parameter names, types, and error codes. Congratulations. You lost:
- Detailed parameter descriptions ("amount in cents" vs just `int` — hope your agent knows Stripe uses cents!)
- Example values
- Deprecation warnings  
- Rate limit documentation
- Pagination semantics
- Webhook payload schemas
- Authentication flow details (OAuth2 scopes, token refresh)
- Content negotiation details

"Zero information loss" means "we defined information as only the things we kept." That's like saying "I lost zero weight" after amputating the parts you didn't weigh.

**3.6× against GPT-4o tokenizer specifically.** What about Claude's tokenizer? Gemini's? Different tokenizers produce different ratios. But that wouldn't look as good on the README, would it?

## 3. "Nobody Will Adopt This"

Let me paint you a picture:

You're a developer. You have 500 OpenAPI specs in your organization. You have tooling built on OpenAPI — code generators, mock servers, API gateways, documentation sites, Postman collections, SDK generators. Your entire API lifecycle is OpenAPI.

Now some rando on GitHub says "hey, convert all that to my custom DSL that only LLMs read." 

Your response: *closes tab*

**The chicken-and-egg problem is fatal.** For LAP to be useful:
1. API providers need to publish `.lap` files
2. Agent frameworks need to consume `.lap` files  
3. Neither will move first

OpenAPI won by having Swagger UI. What's LAP's killer app? A CLI that saves tokens? My CFO doesn't know what a token is.

**The switching cost is real, the benefit is marginal.** Even by your own numbers, we're talking about saving ~$3,600/day on 1M API calls at GPT-4o pricing. Companies spending that much on API calls already have way bigger optimization targets (caching, batching, not calling GPT-4o for everything). This is optimizing the last 2% of your LLM bill.

**Your roadmap is telling.** "Agent framework adapters (LangChain, CrewAI, AutoGen)" — you need to build adapters for every framework. Meanwhile, OpenAPI just... works. Because everything already supports it.

## 4. "The Business Model Is Fantasy"

From the README: "CDN-hosted registry of pre-compiled popular APIs."

So your business model is... hosting text files. Riveting. Let me check — yep, GitHub already hosts text files for free.

The Cloudflare analogy (I'm guessing from the pitch deck that inevitably exists): Cloudflare works because DNS/CDN provides *latency* benefits that compound on every request. Your registry provides... what? A cached SHA-256 hash so you don't send 500 tokens? The L3 compression level saves maybe $0.0001 per call. Your CDN bill will exceed the savings.

**Who is the customer?**
- API providers? They already publish OpenAPI specs for free. Why would they pay to also publish `.lap`?
- Agent developers? They can run your open-source compiler themselves.
- Enterprises? They have private APIs that won't go in any public registry.

The answer is "nobody" and the funding round is "friends and family."

## 5. "LLMs Don't Need This"

Let's talk about the elephant in the room: **the problem is evaporating faster than you can solve it.**

- **GPT-4o**: 128K context, $2.50/1M input tokens (and dropping)
- **Gemini 2.0**: 1M context window, basically free
- **Claude 3.5**: $3/1M input tokens with prompt caching ($0.30 for cached)

Wait. **Prompt caching.** You know, that thing Anthropic already ships, where repeated prefixes are cached at 90% discount? Your entire Stripe API spec, cached: costs basically nothing after the first call. No new protocol needed.

By the time LAP achieves any adoption (optimistically: 2027), context windows will be 10M+ tokens and input pricing will be <$0.50/1M. Your "saving $1.3M/year" headline becomes "saving $50K/year" — not enough to justify learning a new format.

**Also:** The trend is toward models that can *read documentation directly*. Claude can already parse a 200-page PDF and extract the API semantics. Why would I pre-compile docs when the model can just... read?

## 6. "The Protocol Is Over-Engineered"

Four compression levels. FOUR.

- L0: Markdown (just... docs)
- L1: LAP Standard (with descriptions)
- L2: LAP Lean (without descriptions)  
- L3: SHA-256 hash reference

You built a content negotiation system with MIME types and quality values for what is *fundamentally a text preprocessing step*. There are HTTP `Accept` headers in your spec. For a format that... replaces HTTP API documentation. The irony is physically painful.

The EBNF grammar in Section 9 is a nice touch. Really sells the "we're serious computer scientists" vibe. It's also completely unnecessary because the format is so simple you could parse it with 15 lines of regex (which, looking at parser.py, is probably what you did).

`@required {amount: int, currency: str}` — my brother in Christ, this is just JSON Schema with `@` signs and curly braces. You reinvented JSON Schema but worse, because:
- No `$ref` for schema reuse
- No `oneOf`/`anyOf`/`allOf` for polymorphism
- No `pattern` for regex validation
- No `minimum`/`maximum` constraints
- No `additionalProperties` control

Your "type system" (Section 4) has 6 primitive types and format hints. JSON Schema has all of this AND is supported by every language, every tool, every validator on Earth. But sure, `str(email)` is much more compact than `{"type": "string", "format": "email"}`. You saved 30 characters. Alert the press.

## 7. "Here's What Would Actually Kill This"

1. **OpenAI/Anthropic add native OpenAPI compression.** One flag: `tools: [{type: "openapi", spec: "...", compress: true}]`. Done. LAP is instantly irrelevant because the model provider handles it internally.

2. **Prompt caching becomes universal.** Already happening. Cached API specs cost near-zero on repeated calls. The entire cost argument collapses.

3. **Agent frameworks standardize on function schemas.** LangChain, CrewAI, etc. already have their own tool description formats. They don't need a new protocol; they need their existing formats to be slightly smaller, which they'll do themselves.

4. **Someone just makes an OpenAPI minifier.** A 50-line script that strips descriptions, examples, and redundant fields from OpenAPI YAML. Gets 2-3× compression. Stays in the OpenAPI ecosystem. No new format to learn. This probably already exists on npm.

5. **Google ships 100M token context.** The entire OpenAPI spec for *every API on the internet* fits in one context window. Compression becomes as relevant as optimizing floppy disk storage.

6. **Nobody builds the registry.** L3 (cached reference) requires a shared cache that both parties trust. Without infrastructure, the highest compression level is unusable. It's vaporware within vaporware.

---

## OK Fine, Here's What's Actually Good

*[cracks knuckles, sighs deeply]*

Look. I'm not a monster. Here's what I'll grudgingly concede:

**The core insight is correct.** API documentation IS ridiculously bloated for machine consumption. An LLM doesn't need "The `amount` parameter specifies the charge amount in the smallest currency unit (e.g., cents for USD)." It needs `amount: int`. This is a real observation and the project demonstrates it clearly.

**The compression is real.** Even if the benchmarks are inflated, 2-3× compression on structured API docs is achievable and the LAP format does achieve it. For high-volume agent systems TODAY (not 2027), this saves real money.

**The format is actually pretty clean.** I trash-talked the over-engineering, but honestly? `@endpoint POST /v1/charges` / `@required {amount: int, currency: str}` is *extremely* readable. If I had to debug an agent's API understanding, I'd rather read LAP than raw OpenAPI YAML. It's a genuinely nice notation.

**The validation story is solid.** Round-trip compilation with 100% endpoint/parameter/error preservation is the right thing to care about. Most "compression" approaches are lossy and nobody checks. These folks check.

**The L3 cached reference is clever.** Content-addressable API specs with SHA-256 hashes is actually a good idea for agent-to-agent communication. If two agents have previously shared a spec, reducing it to a hash is elegant. It won't get built, but it's elegant.

**The timing might be early, not wrong.** Agent-to-agent API consumption IS going to be a thing. The volume WILL matter. Someone WILL need to solve the "agents reading docs" problem. It might not be LAP, but the problem space is real and this is a thoughtful exploration of it.

**It's well-executed for a POC.** Parser, compiler, converter, CLI, benchmarks, SDK, tests — this is more complete than 95% of "revolutionary" protocol repos on GitHub. Someone actually did the work instead of just writing a manifesto.

So yeah. It probably won't survive contact with the market. But it's a well-built thing that solves a problem that exists today, even if the problem might not exist tomorrow. Which puts it ahead of most things I review on here.

3/10. Would grudgingly star on GitHub.

---

*Edit: RIP my inbox. Yes I know about protobuf. Yes I know about gzip. No, I don't work for OpenAI. Stop DMing me your "better version" of this. I've seen 47 "better versions" since I posted this comment and they're all worse.*
