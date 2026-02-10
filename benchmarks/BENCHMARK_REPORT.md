# LAP Benchmark Harness - Build Report

**Generated:** 2026-02-08  
**Location:** `/data/workspace/lap-poc/benchmarks/big_benchmark/`

## Overview

Successfully built a comprehensive benchmark harness for evaluating LAP (Lean API Protocol) compression across 10 OpenAPI specifications spanning 3 size tiers.

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Specs** | 10 |
| **Total Endpoints** | 734 |
| **Total Tasks** | 50 (5 per spec) |
| **Task Validation** | 50/50 (100%) ✅ |
| **Output Files** | 21 |

## Specs by Tier

### Small Tier (3 specs)
- **stripe-charges.yaml** - 5 endpoints
- **github-core.yaml** - 6 endpoints  
- **discord.yaml** - 4 endpoints

### Medium Tier (4 specs)
- **twitter.yaml** - 80 endpoints
- **resend.yaml** - 70 endpoints
- **launchdarkly.yaml** - 105 endpoints
- **petstore.yaml** - 19 endpoints

### Large Tier (3 specs)
- **snyk.yaml** - 103 endpoints
- **hetzner.yaml** - 144 endpoints
- **plaid.yaml** - 198 endpoints

## Compression Results

| Spec | Tier | Endpoints | Verbose Size | LAP Size | Compression Ratio |
|------|------|-----------|--------------|--------------|-------------------|
| stripe-charges | small | 5 | 11,160 chars | 4,291 chars | **2.60x** |
| github-core | small | 6 | 12,002 chars | 3,703 chars | **3.24x** |
| discord | small | 4 | 4,854 chars | 1,437 chars | **3.38x** |
| twitter | medium | 80 | 286,307 chars | 62,661 chars | **4.57x** |
| resend | medium | 70 | 107,738 chars | 21,262 chars | **5.07x** |
| launchdarkly | medium | 105 | 136,748 chars | 53,595 chars | **2.55x** |
| petstore | medium | 19 | 22,105 chars | 5,670 chars | **3.90x** |
| snyk | large | 103 | 1,014,341 chars | 38,506 chars | **26.34x** ⭐ |
| hetzner | large | 144 | 1,127,652 chars | 78,736 chars | **14.32x** |
| plaid | large | 198 | 1,490,463 chars | 211,342 chars | **7.05x** |

### Compression Analysis

- **Average Compression:** 7.30x
- **Median Compression:** 4.24x  
- **Best Compression:** 26.34x (snyk)
- **Worst Compression:** 2.55x (launchdarkly)

**Key Insight:** Large specs with verbose descriptions (like Snyk) see the most dramatic compression, while specs with lean descriptions already see less benefit.

## Generated Files

### Configuration
- `big_benchmark_config.json` - Master configuration with all specs, tasks, and metadata

### Prompt Files (20 total)
For each of the 10 specs, two prompt files were generated:

1. **verbose_{spec}.txt** - Full raw OpenAPI YAML specification + tasks
2. **lap_{spec}.txt** - Compiled LAP format + tasks

Each file contains:
- Prompt template for API integration assistant
- Complete API documentation (verbose or LAP)
- 5 task descriptions with expected endpoints

## Task Validation

All 50 tasks (5 per spec) were validated against actual endpoints in the specifications:

✅ **stripe-charges:** 5/5 valid  
✅ **github-core:** 5/5 valid  
✅ **discord:** 5/5 valid  
✅ **twitter:** 5/5 valid  
✅ **resend:** 5/5 valid  
✅ **launchdarkly:** 5/5 valid  
✅ **petstore:** 5/5 valid  
✅ **snyk:** 5/5 valid  
✅ **hetzner:** 5/5 valid  
✅ **plaid:** 5/5 valid  

## Sample Tasks by Spec

### stripe-charges
1. Create a new charge for $50 USD for customer cus_123 → `POST /v1/charges`
2. Retrieve the details of charge ch_abc123 → `GET /v1/charges/{charge}`
3. Update the description of charge ch_xyz789 → `POST /v1/charges/{charge}`
4. Capture an authorized charge → `POST /v1/charges/{charge}/capture`
5. List all charges with a limit of 10 → `GET /v1/charges`

### github-core
1. Get details of repository 'octocat/Hello-World' → `GET /repos/{owner}/{repo}`
2. List issues for repository 'owner/repo' → `GET /repos/{owner}/{repo}/issues`
3. Create a new issue with title 'Bug report' → `POST /repos/{owner}/{repo}/issues`
4. List pull requests for repository → `GET /repos/{owner}/{repo}/pulls`
5. Create a new pull request → `POST /repos/{owner}/{repo}/pulls`

### twitter
1. Post a new tweet with text 'Hello Twitter' → `POST /2/tweets`
2. Get details of tweet with ID 123456789 → `GET /2/tweets/{id}`
3. Delete tweet with ID 987654321 → `DELETE /2/tweets/{id}`
4. Get the authenticated user's profile → `GET /2/users/me`
5. Search recent tweets for keyword 'AI' → `GET /2/tweets/search/recent`

### plaid
1. Create a link token for initializing Plaid Link → `POST /link/token/create`
2. Exchange a public token for an access token → `POST /item/public_token/exchange`
3. Get account balances → `POST /accounts/balance/get`
4. Get auth data for account → `POST /auth/get`
5. Get transactions for an item → `POST /transactions/get`

## Usage

### Running Benchmark Evaluations

Each prompt file can be used to evaluate LLM performance on API integration tasks:

```bash
# Example: Evaluate with verbose documentation
cat benchmarks/big_benchmark/verbose_stripe-charges.txt | llm-eval

# Example: Evaluate with LAP documentation  
cat benchmarks/big_benchmark/lap_stripe-charges.txt | llm-eval
```

### Expected Output Format

The LLM should respond with curl commands for each task:

```
TASK 1: curl -X POST https://api.stripe.com/v1/charges \
  -u sk_test_xxx: \
  -d amount=5000 \
  -d currency=usd \
  -d customer=cus_123

TASK 2: curl https://api.stripe.com/v1/charges/ch_abc123 \
  -u sk_test_xxx:
...
```

### Evaluation Metrics

Compare performance between verbose and LAP prompts:

- **Accuracy:** Does the curl command match the expected endpoint?
- **Completeness:** Are all required parameters included?
- **Token Usage:** How many tokens for verbose vs. LAP?
- **Latency:** Response time comparison
- **Cost:** API cost per evaluation

## Files Structure

```
/data/workspace/lap-poc/benchmarks/
├── big_benchmark_config.json          # Master config
├── build_benchmark.py                 # Builder script
├── BENCHMARK_REPORT.md               # This file
└── big_benchmark/
    ├── verbose_stripe-charges.txt
    ├── lap_stripe-charges.txt
    ├── verbose_github-core.txt
    ├── lap_github-core.txt
    ├── verbose_discord.txt
    ├── lap_discord.txt
    ├── verbose_twitter.txt
    ├── lap_twitter.txt
    ├── verbose_resend.txt
    ├── lap_resend.txt
    ├── verbose_launchdarkly.txt
    ├── lap_launchdarkly.txt
    ├── verbose_petstore.txt
    ├── lap_petstore.txt
    ├── verbose_snyk.txt
    ├── lap_snyk.txt
    ├── verbose_hetzner.txt
    ├── lap_hetzner.txt
    ├── verbose_plaid.txt
    └── lap_plaid.txt
```

## Next Steps

1. **Run Evaluations:** Test LLM performance across all 20 prompt files
2. **Collect Metrics:** Track accuracy, token usage, latency, cost
3. **Analyze Results:** Compare verbose vs. LAP effectiveness
4. **Iterate:** Refine LAP format based on findings
5. **Scale:** Add more specs or vary task complexity

## Build Details

- **Build Tool:** Python 3 with LAP core compiler
- **Validation:** All tasks verified against actual OpenAPI endpoints
- **Compression:** LAP compiled with `lean=False` for maximum readability
- **Format:** All prompts use standardized template for consistency

---

**Status:** ✅ Complete - All 50 tasks validated, 20 prompt files generated, ready for evaluation
