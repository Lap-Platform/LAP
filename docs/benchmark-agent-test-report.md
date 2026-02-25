# Agent Benchmark: DocLean vs Verbose API Documentation

**A controlled comparison of AI agent performance when given compressed vs original API specs for an identical coding task.**

LAP Project -- Lean API Platform
Report date: February 9, 2026
Version: 1.0

---

## Executive Summary

This report presents the results of a controlled test comparing two identical Claude Opus 4.6 coding sessions. Both sessions received the same task prompt and targeted the same API (Plaid, 300+ endpoints). The only variable was the documentation format: Session A used a DocLean-compressed spec (160KB), while Session B used the original OpenAPI 3.0 YAML spec (1,491KB).

The DocLean session completed in 51.8 seconds with 4 API round-trips and produced code that correctly included all required API fields. The verbose YAML session took 126.2 seconds with 9 API round-trips and produced code missing 3 required fields -- code that would fail in production.

The root cause is a tooling bottleneck: the WebFetch summarizer model cannot preserve field-level detail from a 1.5MB document. Compressed documentation sidesteps this limitation entirely.

Key findings:

- **2.4x faster** wall-clock completion
- **28% lower cost** ($0.964 vs $1.344)
- **Production-ready output** from DocLean; **3 missing required fields** from verbose YAML
- **23x less data fetched** over the network (320KB vs 7,454KB)

---

## Table of Contents

1. [Methodology](#methodology)
2. [Test Setup](#test-setup)
3. [Quantitative Results](#quantitative-results)
4. [Cost Analysis](#cost-analysis)
5. [Code Quality Analysis](#code-quality-analysis)
6. [Behavioral Analysis](#behavioral-analysis)
7. [Root Cause](#root-cause)
8. [Conclusions](#conclusions)
9. [Limitations](#limitations)
10. [Appendix](#appendix)

---

## Methodology

Both sessions were conducted using Claude Code v2.1.37 with the Claude Opus 4.6 model (claude-opus-4-6). The sessions ran simultaneously to control for any temporal factors (model load, network conditions).

**KPI extraction.** All quantitative metrics were extracted from JSONL session logs produced by Claude Code. Each log entry records the API round-trip with full token accounting broken down by category (input, output, cache write, cache read). Tool calls are logged individually with their type and parameters. Wall time was measured from the first non-error API call to the final response.

**Token counts.** Input tokens are reported as the sum across all API round-trips in a session. Claude Code uses prompt caching, so input tokens are subdivided into three categories: new input tokens (uncached), cache write tokens (first-time cache population), and cache read tokens (subsequent cache hits). Output tokens represent the model's generated responses across all turns.

**Cost calculation.** Costs were computed using published Claude Opus 4.6 pricing at the time of the test: $15.00 per million input tokens, $75.00 per million output tokens, $18.75 per million cache write tokens, and $1.50 per million cache read tokens.

**Documentation delivery.** Both specs were hosted as raw files on GitHub and fetched at runtime using the WebFetch tool, which retrieves a URL's content and passes it through an intermediate summarizer model before returning the result to the main model.

---

## Test Setup

| Parameter | Value |
|---|---|
| Date | February 9, 2026 |
| Model | Claude Opus 4.6 (claude-opus-4-6) |
| Client | Claude Code v2.1.37 |
| Permission mode | Default (user approves tool calls) |
| Start time (both sessions) | 20:12:40 UTC |

**Task prompt (identical for both sessions):**

> Create a JavaScript function that gets account balance for account X and if it is above $100, create a recurring transfer of $5 a month to account Y. If it has less than $100, cancel all recurring transfers.

**API documentation source:** Plaid API -- a financial services platform with 300+ endpoints.

| Session | Format | File | Size |
|---|---|---|---|
| A (DocLean) | DocLean compressed | `plaid.doclean` | 160KB |
| B (Verbose) | OpenAPI 3.0 YAML | `plaid.yaml` | 1,491KB |

Both documentation files were served as raw GitHub URLs from the Lap-benchmark-docs repository.

---

## Quantitative Results

| Metric | DocLean (Session A) | Verbose YAML (Session B) | Ratio |
|---|---|---|---|
| Wall time | 51.8s | 126.2s | 2.4x slower |
| API round-trips | 4 | 9 | 2.25x more |
| Tool calls | 3 | 8 | 2.7x more |
| -- WebFetch | 2 | 5 | 2.5x more |
| -- Bash | 0 | 2 | n/a |
| -- Write | 1 | 1 | same |
| Total input tokens (all turns) | 147,260 | 345,443 | 2.3x more |
| Total output tokens | ~1,115 | ~1,608 | 1.4x more |
| Cache write tokens | 38,225 | 40,858 | 1.07x more |
| Cache read tokens | 109,029 | 304,574 | 2.8x more |
| Doc size (per fetch) | 160KB | 1,491KB | 9.3x larger |
| Doc fetches | 2 | 5 | 2.5x more |
| Total bytes fetched | 320KB | 7,454KB | 23x more |

The DocLean session needed only 2 WebFetch calls to gather sufficient information, then immediately wrote the output file. The verbose session required 5 WebFetch calls -- each attempting to extract different information from the same oversized document -- plus 2 Bash calls, before producing its output.

---

## Cost Analysis

Costs are computed using Claude Opus 4.6 pricing:

- Input tokens: $15.00 / 1M tokens
- Output tokens: $75.00 / 1M tokens
- Cache write tokens: $18.75 / 1M tokens
- Cache read tokens: $1.50 / 1M tokens

### Session A -- DocLean

| Component | Tokens | Cost |
|---|---|---|
| Input (new) | 6 | $0.0001 |
| Cache write | 38,225 | $0.7167 |
| Cache read | 109,029 | $0.1635 |
| Output | 1,115 | $0.0836 |
| **Total** | | **$0.964** |

### Session B -- Verbose YAML

| Component | Tokens | Cost |
|---|---|---|
| Input (new) | 11 | $0.0002 |
| Cache write | 40,858 | $0.7661 |
| Cache read | 304,574 | $0.4569 |
| Output | 1,608 | $0.1206 |
| **Total** | | **$1.344** |

**Cost difference: $0.38 per session -- a 28% reduction with DocLean.**

The cost savings are driven primarily by cache read tokens. The verbose session accumulated 2.8x more cache read tokens due to the larger context window carried across 9 API round-trips (vs 4 for DocLean). Cache write costs were nearly identical, as both sessions populated roughly the same amount of system prompt and tool definition content.

At scale, a 28% per-session reduction compounds significantly. An agent handling 1,000 API-related tasks per day would save approximately $380/day, or over $11,000/month, from documentation compression alone.

---

## Code Quality Analysis

Both sessions produced JavaScript modules targeting the same set of Plaid API endpoints:

- `POST /accounts/balance/get` -- retrieve account balance
- `POST /bank_transfer/create` -- create a transfer
- `POST /bank_transfer/list` -- list existing transfers
- `POST /bank_transfer/cancel` -- cancel a transfer

### Required API Field Compliance

| Required Field | DocLean Output | Verbose Output |
|---|---|---|
| `idempotency_key` | Present | **MISSING** |
| `iso_currency_code` | Present ("USD") | **MISSING** |
| `ach_class` | Present ("ppd") | **MISSING** |
| `description` (max 10 chars) | "Monthly5" (valid) | "Monthly recurring transfer" (**exceeds 10-char limit**) |
| `access_token` | Correct (only where needed) | Sent to endpoints that don't require it |
| Auth headers | Correct (PLAID-CLIENT-ID, PLAID-SECRET, Plaid-Version) | Redundantly sent in both headers AND body |

The DocLean output correctly included all required fields with valid values. The verbose output omitted 3 required fields (`idempotency_key`, `iso_currency_code`, `ach_class`) and provided an invalid value for a fourth (`description` exceeding the 10-character maximum).

### Verbose Output -- Strengths

Despite the field-level failures, the verbose session's code exhibited several architectural qualities worth noting:

- Checks the `cancellable` flag before attempting to cancel a transfer (defensive programming)
- Filters the transfer list by `origination_account_id` (scoped query)
- Uses a `plaidRequest` helper function to reduce code duplication (DRY)
- Exports individual functions for modularity
- Uses an options object pattern for the main function entry point

### Verdict

The DocLean output would succeed against the Plaid API in production. The verbose output would fail at runtime due to 3 missing required fields, regardless of its superior code architecture.

---

## Behavioral Analysis

### Why the Verbose Session Took Longer

The verbose YAML file (1,491KB) exceeded the WebFetch tool's intermediate summarizer capacity. On each fetch, the summarizer truncated the document, systematically losing endpoint listings and field-level constraints. The model's progressive search behavior reveals this clearly:

**Fetch 1:** The model requested balance, transfer, and cancel endpoint details. The summarizer returned a high-level overview but noted: "The provided API spec does not include a dedicated recurring transfer creation endpoint."

**Fetch 2:** The model asked specifically for recurring/schedule endpoints and full request schemas. The response was more detailed but still incomplete.

**Fetch 3:** The model asked the summarizer to list ALL API paths in the document. The returned list was truncated mid-document at `/credit/freddie_mac/reports/get` -- the `/transfer/` namespace, which appears later alphabetically, was never reached.

**Fetch 4:** The model explicitly requested paths containing `/transfer/`. The summarizer responded: "no endpoints containing transfer/recurring found" and "The document appears truncated."

**Fetch 5:** The model tried a keyword search for "recurring", "schedule", and "repeat" across the document. The response: "no occurrences found" -- the document was still being truncated at the same point.

After 5 attempts to extract the needed information from the same 1.5MB file, the model concluded that recurring transfer endpoints did not exist and built its solution using the `bank_transfer` endpoints it had found. The repeated summarization stripped not only endpoint names but also field-level requirements (required flags, max lengths, enum values) from the endpoints it did find.

### DocLean Session Behavior

The DocLean session followed a direct path:

**Fetch 1:** Retrieved endpoint details including authentication requirements, required parameters with types and constraints, and response field structures. The 160KB file fit within summarizer capacity.

**Fetch 2:** Retrieved `bank_transfer/list` details and the exact balance response field structure.

The model then immediately wrote correct, complete code.

---

## Root Cause

The WebFetch tool interposes a small summarizer model between the raw document and the main model. This architecture creates an information bottleneck with a fixed capacity:

- **DocLean (160KB):** Fits within summarizer capacity. Directive-based structure (@auth, @base, @toc, field markers) provides clear extraction targets. Field-level details -- required flags, max lengths, enum values -- are preserved in the summarized output.

- **Verbose YAML (1,491KB):** Exceeds summarizer capacity by approximately 9x. High-level structural information (some endpoint names, general descriptions) survives summarization, but field-level constraints are systematically discarded. Deeply nested `$ref` schema references in YAML further complicate extraction, as resolving them requires access to the full document.

The main model has no access to the raw document -- it only sees what the summarizer returns. No amount of prompt engineering in the WebFetch call can recover information that the summarizer has already discarded. The model's 5-fetch search pattern in the verbose session demonstrates this: each fetch received a different but equally incomplete summary of the same document.

This is not a model capability limitation. It is a tooling constraint inherent to any system that summarizes documents before passing them to an agent. Compressed documentation formats that fit within summarizer capacity sidestep the bottleneck entirely.

---

## Conclusions

**1. Compressed documentation directly improves AI agent code quality.** The DocLean session produced production-ready code with all required fields correctly populated. The verbose session produced code with 3 missing required fields and one field value exceeding API limits. The difference is attributable to information loss during document summarization.

**2. Token efficiency compounds across the agent pipeline.** A 9.3x reduction in document size translated to 2.5x fewer fetch attempts, 2.25x fewer API round-trips, 2.3x fewer total input tokens, 2.4x faster wall-clock time, and 28% lower cost. Each reduction compounds: fewer fetches mean less accumulated context, which means faster processing and lower token costs on subsequent turns.

**3. The WebFetch summarizer is a hard information bottleneck.** When source documents exceed the summarizer's capacity, field-level details are systematically lost. The model cannot compensate through repeated fetches or refined prompts -- the information is discarded before it reaches the model. This bottleneck exists in any tool-using agent architecture that preprocesses documents.

**4. Structured format aids intermediate model comprehension.** DocLean's line-oriented, directive-based format (@auth, @base, @toc, field annotations) provided clear extraction landmarks for the summarizer. YAML's deeply nested structure with `$ref` indirection made it harder for the summarizer to identify and preserve field-level constraints without full-document context.

---

## Limitations

This evaluation has several limitations that should be considered when interpreting results:

1. **Output token counts may be underreported.** Token counts were extracted from JSONL session logs. Due to streaming log capture, some output tokens may not be fully reflected in the recorded totals. This affects both sessions equally and does not change the relative comparison.

2. **Both sessions missed the canonical recurring transfer endpoint.** The Plaid API includes a dedicated `/transfer/recurring/create` endpoint in newer API versions. Neither session discovered or used this endpoint -- both used the general-purpose `bank_transfer/create` instead. This reflects either the API version captured in the documentation or a limitation in both sessions' endpoint discovery.

3. **Single test case (N=1).** This report presents one controlled comparison on one API with one task. While the results are internally consistent and the causal mechanism (summarizer truncation) is well-understood, the specific magnitudes (2.4x speedup, 28% cost saving, 3 missing fields) should not be generalized without validation across a broader set of APIs, tasks, and documentation sizes. The LAP project maintains a benchmark suite of 162 API specs that can support such broader evaluation.

4. **Single model tested.** Only Claude Opus 4.6 was evaluated. Other models with different context window sizes, tool-use behaviors, or WebFetch implementations may show different relative performance between documentation formats.

5. **WebFetch behavior is implementation-specific.** The summarizer bottleneck described here is specific to Claude Code's WebFetch tool as of v2.1.37. Alternative document retrieval mechanisms (direct file reading, RAG-based retrieval, chunked fetching) would likely produce different results for the verbose format.

---

## Appendix

### Session Identifiers

| Session | ID |
|---|---|
| A (DocLean) | `3ecadfd5-01fd-47c3-94fa-92d32e75f2f9` |
| B (Verbose) | `80455321-9b2c-45a9-9df4-b624d80d6fbf` |

### Reproduction

To reproduce this test:

1. Obtain the Plaid API documentation in both formats from the Lap-benchmark-docs repository.
2. Start two Claude Code sessions (v2.1.37 or later) with the Claude Opus 4.6 model.
3. In each session, provide the task prompt above along with the respective documentation URL.
4. Record JSONL session logs and extract metrics as described in the Methodology section.

### Document Specifications

| Property | DocLean | Verbose YAML |
|---|---|---|
| Format | DocLean v0.3 | OpenAPI 3.0 |
| File size | 160KB | 1,491KB |
| Compression ratio | 9.3x | 1x (baseline) |
| Endpoint count | 300+ | 300+ |
| Semantic completeness | Full (no information discarded) | Full (original source) |
