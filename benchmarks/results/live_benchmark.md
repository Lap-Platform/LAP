# LAP Live Benchmark Report

**Generated:** 2026-02-08T01:52:31.968250Z
**Mode:** simulated
**Tokenizer:** cl100k_base (tiktoken)

---

## Summary

| Metric | Without LAP | With LAP | Savings |
|--------|------------|----------|---------|
| Doc Lookup | 5,021 tokens | 1,377 tokens | **72.6%** (3,644 saved) |

---

## Test 1: API Documentation Lookup — WITH vs WITHOUT LAP

Simulates an agent looking up API documentation to construct a call.

### Create Stripe Payment Intent
**Question:** How do I create a payment intent with Stripe?

| Metric | Full Docs | LAP (LAP) |
|--------|-----------|---------------|
| Doc size (bytes) | 5,864 | 1,243 |
| Doc tokens | 1,349 | 384 |
| Prompt tokens | 1,386 | 421 |
| Response tokens | 219 | 65 |
| **Total tokens** | **1,605** | **486** |
| Correct | ✅ | ✅ |
| **Doc reduction** | | **71.5%** |
| **Total reduction** | | **69.7%** (1,119 tokens) |

### Create GitHub Pull Request
**Question:** How do I create a GitHub pull request?

| Metric | Full Docs | LAP (LAP) |
|--------|-----------|---------------|
| Doc size (bytes) | 5,858 | 1,330 |
| Doc tokens | 1,541 | 429 |
| Prompt tokens | 1,577 | 465 |
| Response tokens | 249 | 79 |
| **Total tokens** | **1,826** | **544** |
| Correct | ✅ | ✅ |
| **Doc reduction** | | **72.2%** |
| **Total reduction** | | **70.2%** (1,282 tokens) |

### Send Twilio Message
**Question:** How do I send a message with Twilio?

| Metric | Full Docs | LAP (LAP) |
|--------|-----------|---------------|
| Doc size (bytes) | 4,664 | 746 |
| Doc tokens | 1,211 | 245 |
| Prompt tokens | 1,248 | 282 |
| Response tokens | 342 | 65 |
| **Total tokens** | **1,590** | **347** |
| Correct | ✅ | ✅ |
| **Doc reduction** | | **79.8%** |
| **Total reduction** | | **78.2%** (1,243 tokens) |

---

## Methodology

- **Tokenizer:** OpenAI cl100k_base (tiktoken) — same tokenizer used by GPT-4, Claude counts are similar
- **Without LAP:** Agents exchange full natural language with complete API documentation inline
- **With LAP:** Agents use LAP compressed specs
- **Token counts are exact** — measured from the actual conversation content
- Conversations are realistic simulations of what agents would exchange
- Both versions produce correct, actionable API call structures

## Key Findings

1. **Doc Lookup:** LAP specs reduce tokens by **72.6%** vs full documentation
2. Both approaches produce correct API calls — LAP maintains correctness while dramatically reducing context size
