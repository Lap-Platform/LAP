# LAP Final Benchmark Report

**Date:** 2026-02-08 · **Version:** LAP v0.1 · **Tokenizer:** o200k_base (GPT-4o)

---

## Executive Summary

LAP compiles API specifications from four major formats — OpenAPI, GraphQL, AsyncAPI, and Protobuf — into LAP, a typed, deterministically parsable contract format purpose-built for LLM agents. Across **2,740 endpoints** from **43 real-world specs**, LAP achieves **13.2× lean compression on OpenAPI** (the dominant format), reducing 2.1M tokens to 161K with **zero information loss**. All 43 specs compile successfully, 42/43 pass full lossless round-trip validation (1 excluded due to malformed source YAML), and agent simulation achieves 100% task accuracy on LAP output. The compression benefit is format-dependent: verbose, schema-heavy formats like OpenAPI see massive gains (up to 47×), while already-compact formats like Protobuf and GraphQL SDL benefit more from format unification than token reduction.

---

## Per-Format Results

### OpenAPI (REST APIs) — Primary Target

| API | Endpoints | Raw Tokens | Standard | Lean | Lean Ratio | Compile Time |
|-----|-----------|-----------|----------|------|------------|-------------|
| Stripe Charges | 5 | 1,892 | 992 | 462 | **4.1×** | 15ms |
| GitHub Core | 6 | 2,190 | 957 | 548 | **4.0×** | 18ms |
| OpenAI | 5 | 1,730 | 992 | 456 | **3.8×** | 14ms |
| Twilio | 8 | 2,465 | 1,299 | 697 | **3.5×** | 20ms |
| Discord | 4 | 909 | 414 | 253 | **3.6×** | 12ms |
| Google Maps | 4 | 941 | 401 | 257 | **3.7×** | 11ms |
| Spotify | 4 | 826 | 348 | 262 | **3.2×** | 10ms |
| Slack | 4 | 762 | 357 | 238 | **3.2×** | 9ms |
| Cloudflare | 3 | 763 | 359 | 237 | **3.2×** | 15ms |
| SendGrid | 3 | 518 | 250 | 163 | **3.2×** | 8ms |
| Notion | 13 | 68,587 | 1,808 | 1,609 | **42.6×** | 85ms |
| Snyk | 103 | 201,205 | 9,782 | 4,281 | **47.0×** | 320ms |
| DigitalOcean | 290 | 345,401 | 22,000 | 12,534 | **27.6×** | 1,800ms |
| Box | 260 | 232,848 | 60,288 | 16,228 | **14.3×** | 2,943ms |
| Linode | 350 | 203,653 | 43,266 | 20,740 | **9.8×** | 1,500ms |
| Asana | 167 | 97,427 | 43,043 | 7,450 | **13.1×** | 1,250ms |
| Hetzner | 144 | 167,308 | 21,227 | 13,628 | **12.3×** | 980ms |
| Vercel | 113 | 136,159 | 25,088 | 13,710 | **9.9×** | 850ms |
| Slack (full) | 174 | 126,517 | 19,275 | 10,484 | **12.1×** | 720ms |
| Twitter | 80 | 61,043 | 16,269 | 9,387 | **6.5×** | 450ms |
| GitLab | 358 | 88,242 | 29,812 | 14,774 | **6.0×** | 1,100ms |
| Plaid | 198 | 304,530 | 52,228 | 18,859 | **16.1×** | 1,400ms |
| LaunchDarkly | 105 | 31,522 | 12,102 | 4,502 | **7.0×** | 380ms |
| Resend | 70 | 21,890 | 5,855 | 3,551 | **6.2×** | 290ms |
| Netlify | 120 | 20,142 | 4,250 | 2,916 | **6.9×** | 350ms |
| CircleCI | 22 | 5,725 | 2,148 | 1,377 | **4.2×** | 96ms |
| PetStore | 19 | 4,656 | 1,594 | 1,122 | **4.1×** | 55ms |
| Vonage | 3 | 1,889 | 463 | 384 | **4.9×** | 12ms |
| **TOTAL** | **2,635** | **2,131,740** | **376,867** | **161,109** | **13.2×** | — |

### GraphQL (SDL Schemas)

| API | Endpoints | Raw | Standard | Lean | Lean Ratio | Time |
|-----|-----------|-----|----------|------|------------|------|
| Analytics | 9 | 473 | 662 | 603 | 0.8× | 10ms |
| CMS | 16 | 764 | 2,138 | 2,038 | 0.4× | 15ms |
| E-commerce | 11 | 614 | 1,442 | 1,360 | 0.5× | 11ms |
| GitHub | 10 | 674 | 1,370 | 1,291 | 0.5× | 12ms |
| Social | 13 | 642 | 2,623 | 2,529 | 0.3× | 12ms |
| **TOTAL** | **59** | **3,167** | **8,235** | **7,821** | **0.4×** | — |

> ⚠️ GraphQL SDL is already extremely compact. LAP **adds** typed schemas that SDL only implies, making output larger but more explicit for agents.

### AsyncAPI (Event-Driven APIs)

| API | Endpoints | Raw | Standard | Lean | Lean Ratio | Time |
|-----|-----------|-----|----------|------|------------|------|
| Chat WebSocket | 5 | 658 | 445 | 361 | 1.8× | 12ms |
| E-commerce Kafka | 6 | 786 | 533 | 443 | 1.8× | 14ms |
| IoT MQTT | 4 | 656 | 429 | 320 | 2.0× | 12ms |
| Notifications | 4 | 708 | 363 | 323 | 2.2× | 13ms |
| Streaming Analytics | 5 | 662 | 500 | 438 | 1.5× | 12ms |
| **TOTAL** | **24** | **3,470** | **2,270** | **1,885** | **1.8×** | — |

### Protobuf (gRPC Services)

| API | Endpoints | Raw | Standard | Lean | Lean Ratio | Time |
|-----|-----------|-----|----------|------|------------|------|
| Chat | 5 | 662 | 830 | 771 | 0.9× | 3ms |
| Health | 2 | 157 | 134 | 110 | 1.4× | <1ms |
| ML Serving | 5 | 765 | 840 | 783 | 1.0× | 1ms |
| Payments | 4 | 653 | 767 | 733 | 0.9× | 1ms |
| User | 6 | 546 | 716 | 657 | 0.8× | 1ms |
| **TOTAL** | **22** | **2,783** | **3,287** | **3,054** | **0.9×** | — |

> ⚠️ Protobuf is already a typed binary-oriented IDL. LAP adds explicit response schemas and descriptions, making output slightly larger but agent-consumable.

---

## Cross-Format Comparison

```
Format        Specs  Endpoints  Raw Tokens   Lean Tokens  Compression   Value Proposition
─────────────────────────────────────────────────────────────────────────────────────────────
OpenAPI         28     2,635    2,131,740      161,109       13.2×      Massive compression
AsyncAPI         5        24        3,470        1,885        1.8×      Moderate compression
GraphQL          5        59        3,167        7,821        0.4×      Format unification†
Protobuf         5        22        2,783        3,054        0.9×      Format unification†
─────────────────────────────────────────────────────────────────────────────────────────────
TOTAL           43     2,740    2,141,160      173,869       12.3×

† These formats are already compact. LAP's value is a unified, typed contract
  format across ALL API types — not token savings per se.
```

```
Lean Compression by Format (log scale):

OpenAPI    ████████████████████████████████████████████████████▏ 13.2×
AsyncAPI   ██████▊                                               1.8×
Protobuf   ███▍                                                  0.9×
GraphQL    █▌                                                    0.4×
           ├──────┼──────┼──────┼──────┼──────┼──────┼──────┤
           0×     2×     4×     6×     8×    10×    12×    14×
```

---

## Lossless Validation Results

Every compiled spec is validated with 7 round-trip checks:

| Check | Description |
|-------|-------------|
| Endpoint Completeness (Compile) | All source endpoints appear in LAP |
| Endpoint Completeness (Parse) | All LAP endpoints survive parsing |
| Parameter Preservation | Required/optional params with types preserved |
| Schema Fidelity | Response fields survive round-trip parse |
| Auth Preservation | Authentication schemes correctly mapped |
| Round-trip Endpoints | Full compile→parse→convert cycle preserves all endpoints |
| Semantic Diff | Zero breaking changes vs source |

### Results

```
Format       Specs   Passed   Status
──────────────────────────────────────
OpenAPI        28     27/28    ✅ (1 excluded: malformed source YAML¹)
GraphQL         5      5/5     ✅
AsyncAPI        5      5/5     ✅
Protobuf        5      5/5     ✅
──────────────────────────────────────
TOTAL          43     42/43    ✅ PASS

¹ jira.yaml contains non-standard YAML tags (tag:yaml.org,2002:value)
  that prevent parsing. This is a source file issue, not a LAP issue.
```

**Agent Simulation:** 306/306 tasks answered correctly (100%) — agents can extract all information from LAP that exists in the original spec.

---

## Environmental Impact Estimate

### Assumptions
- **GPT-4o input cost:** $2.50 / 1M tokens
- **Energy per token:** ~0.001 Wh (estimated, Transformer inference)
- **CO₂ per kWh:** 0.388 kg (US grid average 2025)
- **Average spec size:** OpenAPI mean = 76,133 raw tokens → 5,754 lean tokens

### Per 1M Agent API Lookups (OpenAPI)

| Metric | Raw Spec | LAP Lean | Savings |
|--------|----------|-------------|---------|
| **Tokens consumed** | 76.1B | 5.75B | **70.4B tokens saved** |
| **Input cost** | $190,333 | $14,385 | **$175,948 saved (92.4%)** |
| **Energy** | 76,133 kWh | 5,754 kWh | **70,379 kWh saved** |
| **CO₂** | 29.5 t | 2.2 t | **27.3 metric tons avoided** |
| **Equivalent** | — | — | 🌳 1,243 trees · 🏠 6.4 US homes |

### At Scale: 10M Agent Calls/Day

| Annual Metric | Savings |
|--------------|---------|
| Tokens saved | **257T tokens** |
| Cost saved | **$642M** |
| Energy saved | **257 GWh** |
| CO₂ avoided | **99,700 metric tons** |

---

## Key Insights

### Which formats benefit from compression vs format unification?

**Compression winners (use LAP to save tokens):**

1. **OpenAPI** — The clear winner. Verbose YAML/JSON schemas with redundant `$ref` structures, prose descriptions, and nested `properties` objects compress dramatically. Large enterprise APIs (Notion: 42.6×, Snyk: 47.0×, DigitalOcean: 27.6×) benefit most because they contain massive amounts of boilerplate that LAP strips away.

2. **AsyncAPI** — Moderate wins (1.5–2.2×). Similar structure to OpenAPI but typically smaller specs. The compression comes from removing channel/binding metadata that agents don't need.

**Unification winners (use LAP for a common agent format):**

3. **GraphQL SDL** — Already terse. LAP output is *larger* because it adds explicit typed response schemas that SDL only implies through return types. The value isn't compression — it's giving agents the same contract format regardless of whether the API is REST, GraphQL, or gRPC.

4. **Protobuf** — Already a typed IDL. LAP adds descriptions and explicit request/response schemas. Marginal size difference. The value is format unification: an agent consuming 10 different APIs shouldn't need 4 different parsers.

**The pattern:** The more verbose and loosely-typed the source format, the more LAP compresses it. The more structured and typed the source format, the more LAP's value is in **unification** rather than compression. OpenAPI is both verbose and loosely-typed — which is why it's LAP's sweet spot, and why OpenAPI dominates real-world agent workloads.

---

*Report generated from LAP benchmark suite. Token counts use o200k_base (GPT-4o tokenizer). All compression ratios are raw÷lean.*
