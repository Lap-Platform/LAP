# Blind Agent Benchmark Plan

> Goal: Prove that agents perform **equally well or better** with LAP-compiled specs vs raw OpenAPI, across multiple models and APIs.

## Why This Matters

Token compression means nothing if agents produce worse results. This benchmark answers the question: **"Does DocLean actually work in practice?"**

## Test Design

### Variables
- **Input format**: Raw OpenAPI YAML vs LAP Standard vs LAP Lean
- **Model**: Claude Sonnet 4, GPT-4o, Gemini 2.0 Flash (minimum 3 models)
- **API**: 5 real-world APIs of varying complexity

### APIs to Test

| API | Complexity | Why |
|-----|-----------|-----|
| Stripe (Charges) | Simple | Well-known, clean REST, good baseline |
| GitHub (Repos+Issues) | Medium | Multiple related endpoints, pagination |
| Plaid (Transactions) | Medium-High | Financial API, strict params, auth complexity |
| Hetzner (Servers) | High | Infrastructure API, nested objects, multi-step workflows |
| Notion (Pages+Databases) | High | Complex nested schemas, unusual patterns |

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
- Day 2: Run all 135 tests (5 APIs × 3 tasks × 3 formats × 3 models)
- Day 3: Score and analyze results
- Day 4: Write report

## Cost Estimate

~135 API calls across 3 models
- Average ~5K input tokens (raw), ~2K (LAP) per call
- Average ~1K output tokens per call
- Estimated total: ~$15-25 in API costs
