# Blind Agent Benchmark Plan

> Goal: Prove that agents perform **equally well or better** with LAP-compiled specs vs raw OpenAPI, across multiple models and APIs.

## Baseline Comparison: LAP vs Simple Alternatives

Before running the blind test, we established that LAP isn't just beating raw YAML — it beats every simple minification approach:

| API | Raw YAML | JSON Minified | YAML No-Desc | LAP Lean | LAP vs JSON | LAP vs No-Desc |
|-----|----------|--------------|-------------|----------|------------|---------------|
| petstore | 4,656 | 3,923 | 2,936 | 1,216 | **3.2x** | **2.4x** |
| github-core | 2,190 | 1,870 | 1,352 | 530 | **3.5x** | **2.6x** |
| snyk | 201,205 | 187,505 | 35,399 | 5,192 | **36.1x** | **6.8x** |
| notion | 68,587 | 64,302 | 10,170 | 1,732 | **37.1x** | **5.9x** |
| hetzner | 167,308 | 142,811 | 56,485 | 14,241 | **10.0x** | **4.0x** |
| discord | 909 | 789 | 642 | 307 | **2.6x** | **2.1x** |
| slack | 762 | 655 | 564 | 315 | **2.1x** | **1.8x** |
| vonage | 1,889 | 1,638 | 1,199 | 411 | **4.0x** | **2.9x** |
| circleci | 5,725 | 4,934 | 4,142 | 1,463 | **3.4x** | **2.8x** |
| resend | 21,890 | 18,951 | 11,403 | 3,775 | **5.0x** | **3.0x** |

**Key takeaway:** Even against the best simple alternative (YAML with descriptions stripped), LAP Lean is still **1.8-6.8x better**. The compression comes from structural transformation, not just stripping text.

Baselines tested:
- **JSON Minified**: `json.dumps(spec, separators=(',',':'))` — no whitespace
- **YAML No-Desc**: Strip all `description`, `summary`, `example` fields, then compact YAML
- **LAP Lean**: Full DocLean compilation with description stripping

## Why This Matters

Token compression means nothing if agents produce worse results. This benchmark answers the question: **"Does DocLean actually work in practice?"**

## Test Design

### Variables
- **Input format**: Raw YAML/JSON vs JSON Minified vs YAML No-Desc vs LAP Standard vs LAP Lean
- **Model**: Claude Sonnet 4, GPT-4o, Gemini 2.0 Flash (minimum 3 models)
- **API**: 5 real-world APIs of varying complexity

### APIs to Test

#### OpenAPI / REST (7 APIs)

| API | Complexity | Why |
|-----|-----------|-----|
| Stripe (Charges) | Simple | Well-known, clean REST, good baseline |
| GitHub (Repos+Issues) | Medium | Multiple related endpoints, pagination |
| Plaid (Transactions) | Medium-High | Financial API, strict params, auth complexity |
| Hetzner (Servers) | High | Infrastructure API, nested objects, multi-step workflows |
| Notion (Pages+Databases) | High | Complex nested schemas, unusual patterns |
| Snyk (Projects) | High | Highest compression ratio — stress test for lean mode |
| Twilio (SMS) | Simple | Short spec, tests whether LAP helps on small APIs too |

#### Non-OpenAPI Formats (3 APIs)

| API | Format | Why |
|-----|--------|-----|
| GitHub GraphQL | GraphQL | Test where LAP compression is weakest (1.3x) |
| Stripe Webhooks | AsyncAPI | Event-driven pattern, different from REST |
| gRPC Health Check | Protobuf | Compact source format, tests format unification value |

### Tasks Per API (3 tasks each = 15 total)

Each task is a realistic developer request:

**Stripe:**
1. "Write a Python function to create a charge for $50 USD, capture it, then retrieve the charge details"
2. "List all charges for customer cus_ABC, handling pagination to get all results"
3. "Create a charge with metadata, handle the error if the card is declined"

**GitHub:**
1. "Create an issue with labels, then list all open issues sorted by creation date"
2. "Create a pull request from feature branch to main, then merge it with squash"
3. "List all issues with the 'bug' label, paginate through all pages"

**Plaid:**
1. "Exchange a public token for an access token, then fetch recent transactions"
2. "Get account balances and format them by account type"
3. "Set up a webhook for transaction updates and handle the verification"

**Hetzner:**
1. "Create a server with Ubuntu, attach a floating IP, and create a firewall rule allowing SSH"
2. "List all servers, find those running CentOS, and resize them to cx21"
3. "Create a load balancer, add two servers as targets, configure health checks"

**Notion:**
1. "Create a new database with Name, Status, and Date columns"
2. "Query a database filtering by status='Active', sorted by date descending"
3. "Create a page in a database with rich text content and a checkbox property"

### Evaluation Criteria (per task)

Score each output 0-3 on each dimension:

| Criterion | 0 | 1 | 2 | 3 |
|-----------|---|---|---|---|
| **Correctness** | Won't run | Runs but wrong result | Works with minor issues | Fully correct |
| **Completeness** | Missing key parts | Partial implementation | Mostly complete | All requirements met |
| **API Usage** | Wrong endpoints/params | Right endpoints, wrong params | Correct with minor param issues | Perfect API usage |
| **Error Handling** | None | Basic try/catch | Handles common errors | Handles API-specific errors |
| **Auth** | Missing/wrong | Placeholder only | Correct pattern | Correct with best practices |

### Metrics to Capture

Per task:
- Score (0-15 across 5 criteria)
- Input tokens consumed
- Output tokens generated
- Latency (time to first token, total)
- Did the agent hallucinate any endpoints?
- Did the agent hallucinate any parameters?
- Did the agent miss any required parameters?

Aggregated:
- Average score by format (OpenAPI vs Standard vs Lean)
- Average score by model
- Token savings (confirmed)
- Hallucination rate by format
- Statistical significance (paired t-test across tasks)

## Implementation

### Step 1: Prepare Inputs

For each API, create 3 files:
```
test_inputs/
├── stripe/
│   ├── raw.yaml          # Original OpenAPI spec
│   ├── standard.lap      # LAP Standard output
│   └── lean.lap          # LAP Lean output
├── github/
│   └── ...
└── ...
```

### Step 2: Run Tests

```python
# Pseudocode
for api in APIs:
    for task in api.tasks:
        for format in [raw, standard, lean]:
            for model in [claude, gpt4o, gemini]:
                prompt = f"""Given this API specification:
                
{load_spec(api, format)}

Task: {task.description}

Write a complete Python implementation."""
                
                result = call_model(model, prompt)
                score = evaluate(result, task.expected)
                log(api, task, format, model, result, score)
```

### Step 3: Evaluate

- Automated: syntax check, import check, endpoint/param validation
- Manual review: 2 reviewers score each output independently
- Resolve disagreements by discussion

### Step 4: Report

Produce:
- Summary table: format × model with average scores
- Token usage comparison
- Hallucination rates
- Statistical significance
- Individual task breakdowns
- Cherry-picked examples (best/worst cases for each format)

## Expected Outcomes

**If LAP works**: Similar or higher scores with 3-10x fewer input tokens.
**If LAP fails**: Lower scores, more hallucinations, missed required params.
**Either result is publishable** — honest findings build credibility.

## Timeline

- Day 1: Prepare all spec files and task prompts
- Day 2: Run all tests (10 APIs × 3 tasks × 5 formats × 3 models = 450 tests)
- Day 3: Score and analyze results
- Day 4: Write report

## Cost Estimate

~450 API calls across 3 models
- Average ~5K input tokens (raw), ~2K (LAP) per call
- Average ~1K output tokens per call
- Estimated total: ~$50-80 in API costs
