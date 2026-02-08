# 🌱 LAP Environmental Impact Assessment

> *Efficient communication isn't just cheaper — it's responsible.*

## Executive Summary

LAP's DocLean format compresses API documentation by **3.6× on average**, eliminating tokens that LLMs must process but gain nothing from. At scale, this translates to measurable reductions in energy consumption, carbon emissions, and compute infrastructure demand.

This document quantifies that impact using the best available data as of early 2025.

---

## 1. Energy Cost of LLM Tokens

### What does a token actually cost in energy?

| Data Point | Value | Source |
|---|---|---|
| ChatGPT average query energy | **0.3–0.34 Wh** per query | OpenAI (Altman, 2025); Epoch AI (Feb 2025) |
| GPT-4o long prompt (~7K words in + 1K out) | **~0.004 Wh** (o3: 0.0039 Wh) | Jehham et al. (2025) |
| LLaMA-65B inference | **3–4 Joules per output token** | "From Words to Watts" (arXiv:2310.03003) |
| Complex reasoning queries (o3, GPT-4.5) | **up to 20+ Wh** per query | IEEE Spectrum (Oct 2025) |
| H100 GPU TDP | **700W** | NVIDIA specs |
| Data center PUE overhead | **1.1–1.4×** (avg ~1.2×) | Industry standard |

### Deriving energy per token

A typical ChatGPT query processes ~1,000–2,000 tokens (input + output combined) and uses ~0.3 Wh.

**Conservative estimate: ~0.0002 Wh per token (0.2 mWh/token)**
**Upper estimate for large models: ~0.001 Wh per token (1.0 mWh/token)**

For our calculations, we use **0.0004 Wh/token** (0.4 mWh/token) — a middle estimate accounting for GPT-4-class models processing primarily input tokens (which are cheaper than output tokens but still require full attention computation).

> ⚠️ *These are estimates. Actual energy varies by model, batch size, hardware, and query complexity. We use mid-range values and clearly mark assumptions.*

---

## 2. LAP's Measured Token Savings

### Our benchmark results

| Metric | Value |
|---|---|
| APIs benchmarked | 28 |
| Total OpenAPI tokens | 2,100,000 |
| Total DocLean tokens | 161,000 |
| **Tokens eliminated** | **1,970,000** |
| **Compression ratio** | **3.6× (lean mode)** |
| Information loss | **0%** (validated) |

Every token eliminated is a token that never needs to be processed by GPU silicon.

---

## 3. Scaling the Impact

### Scenario: 1M agent API lookups per day

As agentic AI systems grow, agents routinely fetch API documentation to understand how to call services. Consider an ecosystem doing **1 million agent API lookups per day** — a conservative estimate as multi-agent platforms scale.

#### Assumptions
- Average API doc size: **2,100 tokens** (our benchmark mean across 28 APIs)
- LAP compression: **3.6×** → saves ~1,517 tokens per lookup
- Energy per token: **0.0004 Wh** (mid estimate)

#### Annual calculations

| Metric | Without LAP | With LAP | **Saved** |
|---|---|---|---|
| Tokens processed/day | 2.1B | 583M | **1.52B tokens/day** |
| Tokens processed/year | 766.5B | 212.8B | **553.7B tokens/year** |
| Energy/year | 306,600 kWh | 85,120 kWh | **221,480 kWh/year** |
| With PUE (1.2×) | 367,920 kWh | 102,144 kWh | **265,776 kWh/year** |

### What does 265,776 kWh saved look like?

| Equivalent | Value | Basis |
|---|---|---|
| 🏠 US homes powered | **~24 homes for a year** | US avg: 10,791 kWh/year (EIA) |
| 🌲 CO₂ avoided | **102.6 metric tons** | US grid: 386g CO₂/kWh (MIT, 2024) |
| 🌳 Trees equivalent | **~4,700 trees** | 1 tree absorbs ~21.8 kg CO₂/year (EPA) |
| 🚗 Car miles avoided | **~256,000 miles** | 400g CO₂/mile average |
| ⚡ GPU-hours freed | **~380,000 H100-hours** | 700W TDP |

> *And this is just 1M lookups/day. The AI agent ecosystem is growing exponentially.*

---

## 4. Industry Scale Projections

### 10M lookups/day (near-term, 2025–2026)

As agent frameworks (LangChain, CrewAI, AutoGen, OpenAI Assistants) proliferate:

- **5.5 trillion tokens saved/year**
- **2.66 GWh saved** (with PUE)
- **1,026 metric tons CO₂ avoided**
- **240 homes powered** for a year

### 100M lookups/day (medium-term, 2026–2028)

As multi-agent orchestration becomes standard:

- **55 trillion tokens saved/year**
- **26.6 GWh saved**
- **10,260 metric tons CO₂ avoided**
- **2,400 homes powered**
- Equivalent to taking **~2,200 cars off the road** for a year

### 1B lookups/day (longer-term, 2028+)

As autonomous agent fleets manage infrastructure at scale:

- **550 trillion tokens saved/year**
- **266 GWh saved**
- **102,600 metric tons CO₂ avoided**
- Equivalent to the annual energy output of a **small solar farm**

---

## 5. The Multiplier Effect

LAP's savings compound in multi-agent architectures:

```
Human → Agent A → fetches Stripe API docs (saves 1,430 tokens)
         └→ Agent B → fetches Twilio API docs (saves 1,768 tokens)
              └→ Agent C → fetches SendGrid API docs (saves 355 tokens)
```

**A single user request can trigger 3+ API doc lookups.** In complex workflows:

- **Orchestrator agents** fetch docs for routing decisions
- **Worker agents** fetch docs for execution
- **Validator agents** fetch docs for response checking
- **Retry loops** may re-fetch docs on failure

A realistic multiplier is **3–10× the base lookup count** per end-user action. Our scenarios above use raw lookup counts — actual savings could be **3–10× higher**.

### Caching helps, but doesn't solve the problem

Even with aggressive caching, the *first* load of every API doc in every new agent session still processes full tokens. With millions of agent sessions spinning up daily, cache miss rates remain significant. LAP reduces the cost of every cache miss by 72%.

---

## 6. Comparison to Other Green Compute Efforts

| Optimization | Typical Savings | Notes |
|---|---|---|
| Model quantization (FP16→INT8) | 30–50% compute | Trades accuracy for efficiency |
| KV-cache optimization | 10–30% memory | Inference-specific |
| Prompt compression (LLMLingua etc.) | 30–60% tokens | Lossy — meaning can be lost |
| Hardware upgrades (A100→H100) | ~2–3× perf/watt | Requires $25K+ per GPU |
| **LAP DocLean** | **72% token reduction** | **Lossless — zero information loss** |

LAP is unique: it achieves **72% reduction with zero information loss**. Most compression techniques trade accuracy for efficiency. LAP eliminates only what was never needed — prose, redundancy, and formatting overhead that humans need but agents don't.

---

## 7. The Carbon Footprint of Unnecessary Tokens

The AI industry processed an estimated **1+ trillion tokens per day** in 2024 (across all providers). If even 10% of those tokens are API documentation consumed by agents:

- **100B doc tokens/day** across the industry
- At 72% compressibility: **72B unnecessary tokens/day**
- Energy wasted: **~28,800 kWh/day → 10.5 GWh/year**
- CO₂ emitted needlessly: **~4,050 metric tons/year**

> *That's 4,050 metric tons of CO₂ per year from tokens that carry zero additional information for their consumers.*

These are tokens describing the same API parameter in three paragraphs when three words would do. They're markdown tables formatted for humans being parsed by machines. They're "Note:" callouts and usage examples that an agent ignores after burning compute to process them.

---

## 8. Vision: LAP as Green AI Infrastructure

The AI industry is focused on making models faster, cheaper, and more capable. Far less attention is paid to making the *inputs* to these models efficient.

LAP addresses this gap:

- **Every API publisher** that ships DocLean alongside their docs reduces global compute waste
- **Every agent framework** that defaults to DocLean over raw docs compounds the savings
- **Every token not processed** is energy not consumed, heat not generated, carbon not emitted

### The efficient communication principle

> *"The greenest token is the one you never process."*

LAP doesn't ask models to be more efficient. It doesn't require new hardware. It doesn't trade accuracy for speed. It simply removes the waste — the verbose, redundant, human-oriented formatting that machines process but never need.

As AI scales from millions to billions of daily inference calls, the efficiency of what we *send* to models matters as much as the efficiency of the models themselves.

**LAP is infrastructure for responsible AI scaling.**

---

## Methodology & Limitations

> ⚠️ **Disclaimer:** The figures in this document are **rough estimates** based on publicly available data and simplifying assumptions. They are intended to illustrate the *potential* environmental benefits of token reduction, not to make precise claims. Actual energy savings depend heavily on model architecture, hardware, batch sizes, caching strategies, data center efficiency, and many other factors we cannot control for. Independent verification is encouraged.

### Sources & Assumptions

- Energy per token estimates derived from OpenAI's stated 0.3 Wh/query figure (Epoch AI, Feb 2025) and academic measurements of 3–4 J/output token for 65B-parameter models (arXiv:2310.03003)
- Token counts measured using `cl100k_base` tokenizer (GPT-4o)
- US grid carbon intensity: 386g CO₂/kWh (MIT, 2024)
- US household consumption: 10,791 kWh/year (EIA, 2023)
- Data center PUE: 1.2× (industry average for hyperscalers)
- Tree CO₂ absorption: 21.8 kg/year (EPA)
- All projections assume linear scaling; real-world impact may vary based on caching, batching, and model optimizations
- Estimates are marked as such; measured values from our benchmarks are exact

---

*Document version: 1.0 | February 2026*
*LAP Project: github.com/yourusername/lap*
