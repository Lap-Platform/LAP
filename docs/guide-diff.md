# Schema Diffing Guide

LAP can diff two LAP files to detect API changes — added/removed endpoints, parameter changes, and breaking changes.

## Schema Diffing Basics

```bash
lapsh diff old-api.lap new-api.lap
```

Compare any two LAP files to see what changed:

```bash
# Compile two versions
lapsh compile examples/verbose/openapi/stripe-charges-v1.yaml -o v1.lap
lapsh compile examples/verbose/openapi/stripe-charges-v2.yaml -o v2.lap

# Diff them
lapsh diff v1.lap v2.lap
```

The diff detects:
- **Added endpoints** — new `@endpoint` directives
- **Removed endpoints** — endpoints present in old but not new
- **Parameter changes** — added/removed required/optional params
- **Type changes** — parameter type modifications
- **Response schema changes** — new/removed response fields
- **Error code changes** — added/removed error codes

## Breaking Change Detection

A breaking change is anything that could cause existing agent integrations to fail:

| Change | Breaking? | Why |
|--------|-----------|-----|
| Removed endpoint | ✅ Yes | Agent calls will 404 |
| New required parameter | ✅ Yes | Existing calls will fail validation |
| Removed response field | ✅ Yes | Agent may depend on it |
| Changed parameter type | ✅ Yes | Agent sends wrong type |
| New optional parameter | ❌ No | Existing calls still work |
| New endpoint | ❌ No | Doesn't affect existing calls |
| New response field | ❌ No | Extra data is fine |
| New error code | ⚠️ Maybe | Agent may not handle it |

## Generating Changelogs

Use the `--format changelog` flag for a structured changelog:

```bash
lapsh diff v1.lap v2.lap --format changelog --version "2.0.0"
```

Output:
```
## API Changelog — v2.0.0

### Breaking Changes
- REMOVED endpoint: DELETE /v1/charges/{charge}
- REMOVED required param `source` from POST /v1/charges
- CHANGED type of `amount` from `int` to `num` in POST /v1/charges

### New Features
- ADDED endpoint: POST /v1/charges/{charge}/refund
- ADDED optional param `idempotency_key` to POST /v1/charges

### Other Changes
- ADDED error code 503 to POST /v1/charges
```

## CI/CD Integration for API Monitoring

### GitHub Actions

Add API diff checks to your CI pipeline:

```yaml
name: API Diff Check
on:
  pull_request:
    paths: ['examples/verbose/**']

jobs:
  api-diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install LAP
        run: pip install pyyaml tiktoken rich

      - name: Compile current and previous specs
        run: |
          # Current version
          lapsh compile examples/verbose/openapi/my-api.yaml -o new.lap
          # Previous version (from main branch)
          git show main:examples/verbose/openapi/my-api.yaml > /tmp/old-spec.yaml
          lapsh compile /tmp/old-spec.yaml -o old.lap

      - name: Check for breaking changes
        run: |
          output=$(lapsh diff old.lap new.lap --format changelog)
          if echo "$output" | grep -q "Breaking Changes"; then
            echo "⚠️ Breaking API changes detected!"
            echo "$output"
            exit 1
          fi
          echo "✅ No breaking changes"
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

for spec in examples/verbose/openapi/*.yaml; do
  name=$(basename "$spec" .yaml)
  if [ -f "examples/lap/openapi/${name}.lap" ]; then
    lapsh compile "$spec" -o "/tmp/${name}-new.lap"
    diff_output=$(lapsh diff "examples/lap/openapi/${name}.lap" "/tmp/${name}-new.lap" 2>&1)
    if echo "$diff_output" | grep -q "REMOVED"; then
      echo "⚠️  Breaking change in ${name}:"
      echo "$diff_output"
      exit 1
    fi
  fi
done
```

### Scheduled Monitoring

Monitor third-party APIs for changes by periodically recompiling and diffing:

```bash
#!/bin/bash
# Run daily via cron

for spec in examples/verbose/openapi/*.yaml; do
  name=$(basename "$spec" .yaml)
  cp "examples/lap/openapi/${name}.lap" "/tmp/${name}-prev.lap" 2>/dev/null

  # Recompile
  lapsh compile "$spec" -o "examples/lap/openapi/${name}.lap"

  # Diff against previous
  if [ -f "/tmp/${name}-prev.lap" ]; then
    changes=$(lapsh diff "/tmp/${name}-prev.lap" "examples/lap/openapi/${name}.lap" --format summary)
    if [ -n "$changes" ]; then
      echo "Changes detected in ${name}:"
      echo "$changes"
      # Send notification (Slack, email, etc.)
    fi
  fi
done
```
