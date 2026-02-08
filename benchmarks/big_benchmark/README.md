# LAP Big Benchmark

This directory contains the complete LAP benchmark harness for evaluating DocLean compression effectiveness.

## Quick Start

```bash
# View the configuration
cat ../big_benchmark_config.json | jq

# Run a sample evaluation (verbose)
cat verbose_stripe-charges.txt | your-llm-tool

# Run a sample evaluation (DocLean)
cat doclean_stripe-charges.txt | your-llm-tool

# Compare results
diff <(your-llm verbose_stripe-charges.txt) <(your-llm doclean_stripe-charges.txt)
```

## File Naming Convention

- `verbose_{spec}.txt` - Full OpenAPI YAML specification + tasks
- `doclean_{spec}.txt` - Compiled DocLean format + tasks

## Specs Included

### Small (3)
- stripe-charges (5 endpoints, 2.60x compression)
- github-core (6 endpoints, 3.24x compression)
- discord (4 endpoints, 3.38x compression)

### Medium (4)
- twitter (80 endpoints, 4.57x compression)
- resend (70 endpoints, 5.07x compression)
- launchdarkly (105 endpoints, 2.55x compression)
- petstore (19 endpoints, 3.90x compression)

### Large (3)
- snyk (103 endpoints, 26.34x compression)
- hetzner (144 endpoints, 14.32x compression)
- plaid (198 endpoints, 7.05x compression)

## Evaluation Criteria

Each prompt contains 5 tasks. Evaluate the LLM's ability to:

1. **Parse** the documentation correctly
2. **Identify** the correct endpoint for each task
3. **Generate** valid curl commands with proper:
   - HTTP method
   - Endpoint path
   - Required parameters
   - Authentication headers
   - Request body format

## Expected Output Format

```
TASK 1: <curl command>
TASK 2: <curl command>
TASK 3: <curl command>
TASK 4: <curl command>
TASK 5: <curl command>
```

## Metrics to Track

- **Accuracy:** Percentage of correct endpoints identified
- **Token Count:** Input tokens (verbose vs DocLean)
- **Latency:** Time to first response
- **Cost:** API cost per evaluation
- **Completeness:** Percentage of required parameters included

## See Also

- `../big_benchmark_config.json` - Full configuration and task details
- `../BENCHMARK_REPORT.md` - Detailed build report and analysis
- `../build_benchmark.py` - Builder script (reproducible)
