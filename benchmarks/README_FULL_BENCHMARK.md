# Full Multi-Protocol Agent Benchmark

Comprehensive benchmark suite testing LLM agent performance with verbose API documentation vs. DocLean across 5 protocol types.

## Overview

- **500+ tasks** across OpenAPI, GraphQL, AsyncAPI, Postman, and Protobuf
- **10 docs per protocol**, 10 tasks per doc
- Tests **correctness**, **token usage**, and **response time**
- Compares verbose documentation vs. DocLean output

## Quick Start

### Dry Run (no API calls)

```bash
# Test all OpenAPI tasks
python3 benchmarks/full_agent_benchmark.py --dry-run --protocol openapi

# Test first 10 tasks across all protocols
python3 benchmarks/full_agent_benchmark.py --dry-run --limit 10

# Test specific protocol with limit
python3 benchmarks/full_agent_benchmark.py --dry-run --protocol graphql --limit 5
```

### Live Benchmark

```bash
# With OpenAI
export OPENAI_API_KEY=sk-...
python3 benchmarks/full_agent_benchmark.py --protocol openapi --limit 10

# With Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 benchmarks/full_agent_benchmark.py --anthropic --protocol openapi --limit 10

# Custom model
python3 benchmarks/full_agent_benchmark.py --model gpt-4o-mini --limit 20
```

## Task Structure

Tasks are defined in `full_test_tasks.yaml`:

```yaml
protocols:
  openapi:
    docs:
      - spec: specs/stripe-charges.yaml
        api: Stripe Charges
        tasks:
          - task: "Create a charge for $50 USD with token tok_visa"
            expect_endpoint: "POST /v1/charges"
            expect_params: ["amount", "currency", "source"]
```

Each task includes:
- **task**: Natural language description of what to accomplish
- **expect_endpoint**: Expected API endpoint (for validation)
- **expect_params**: Expected parameters (for validation)

## Protocols Covered

### OpenAPI (100 tasks)
- Stripe Charges, GitHub Core, OpenAI, Twilio, Slack, Discord, Spotify, Cloudflare DNS, SendGrid, Snyk

### GraphQL (100 tasks)
- GitHub, Stripe, Shopify, Slack, Twitter, Spotify, GitLab, Notion, Linear, E-commerce, Contentful

### AsyncAPI (100 tasks)
- Stripe Webhooks, Slack Events, Kafka E-commerce, GitHub Webhooks, Slack RTM, Chat WebSocket, AWS SNS/SQS, IoT MQTT, Notifications, Stock Market Feed

### Postman Collections (100 tasks)
- Stripe Payments, GitHub Repos, Slack API, Twilio Messaging, SendGrid Email, Discord Bot, Notion, Jira, Shopify, HubSpot CRM, Zoom

### Protobuf/gRPC (100 tasks)
- User Service, Chat Service, Payments, Health Check, Google Pub/Sub, Google Firestore, Google Storage, Auth Service, Search Service, Notifications

## Output

### JSON Report
Saved to `benchmarks/results/full_benchmark_report.json`:

```json
[
  {
    "protocol": "openapi",
    "spec": "specs/stripe-charges.yaml",
    "task": "Create a charge for $50 USD",
    "tokens": {
      "verbose_input": 911,
      "lean_input": 521,
      "reduction_pct": 42.8,
      "verbose_total": 950,
      "lean_total": 560
    },
    "correctness": {
      "verbose": true,
      "lean": true
    },
    "timing": {
      "verbose_seconds": 1.2,
      "lean_seconds": 0.8
    }
  }
]
```

### Markdown Summary
Saved to `benchmarks/results/full_benchmark_report.md`:

```markdown
# Full Multi-Protocol Agent Benchmark Results

**Total Tasks:** 100
**Verbose Correctness:** 95/100 (95.0%)
**Lean Correctness:** 94/100 (94.0%)
**Total Tokens (Verbose):** 95,000
**Total Tokens (Lean):** 55,000
**Overall Token Reduction:** 42.1%

## By Protocol

### OPENAPI
- Tasks: 100
- Verbose Correctness: 98/100
- Lean Correctness: 97/100
- Token Reduction: 95,000 → 55,000 (42.1%)
```

## Command-Line Options

```
--tasks-file PATH        Path to tasks YAML (default: full_test_tasks.yaml)
--protocol PROTOCOL      Filter to specific protocol (openapi/graphql/asyncapi/postman/protobuf)
--limit N                Limit number of tasks to run
--dry-run                Show token counts without calling LLM
--anthropic              Use Anthropic API instead of OpenAI
--model MODEL            Model name (default: gpt-4o or claude-3-5-sonnet)
--api-key KEY            API key (or use env var)
--output PATH            Output JSON report path
```

## Metrics Tracked

1. **Token Usage**
   - Verbose input tokens
   - Lean input tokens
   - Output tokens (both versions)
   - Token reduction percentage

2. **Correctness**
   - Endpoint matching (does the call target the right API?)
   - Parameter coverage (are all required params included?)
   - Issues/differences between verbose and lean

3. **Timing**
   - Response time for verbose version
   - Response time for lean version

## Adding New Tasks

1. Choose a protocol and find/add a spec file
2. Add doc entry to `full_test_tasks.yaml`
3. Create 10 realistic tasks:
   - CRUD operations (Create, Read, Update, Delete)
   - Listing/pagination
   - Filtering/searching
   - Edge cases (empty results, errors, etc.)
4. Specify expected endpoint and params for validation

Example:

```yaml
- spec: specs/your-api.yaml
  api: Your API
  tasks:
    - task: "Create a new user with email user@example.com"
      expect_endpoint: "POST /v1/users"
      expect_params: ["email"]
    - task: "List all users with limit 10"
      expect_endpoint: "GET /v1/users"
      expect_params: ["limit"]
```

## Current Status

- ✅ OpenAPI compiler implemented (100 tasks working)
- ⏳ GraphQL compiler in progress
- ⏳ AsyncAPI compiler in progress
- ⏳ Postman compiler in progress
- ⏳ Protobuf compiler in progress

Tasks for protocols without compilers will show "COMPILATION FAILED" in dry-run mode.

## Example Results

From dry-run with 30 OpenAPI tasks:

```
Average Token Reduction: 39.6%

Stripe Charges:   911 → 521 tokens (42.8% reduction)
GitHub Core:      911 → 603 tokens (33.8% reduction)
OpenAI Core:      893 → 516 tokens (42.2% reduction)
```

This demonstrates DocLean's ability to reduce token usage by ~40% on average while maintaining the information needed for LLM agents to make correct API calls.
