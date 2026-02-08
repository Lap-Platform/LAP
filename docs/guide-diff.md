# Schema Diffing Guide

LAP can diff two DocLean files to detect API changes — added/removed endpoints, parameter changes, and breaking changes.

## Schema Diffing Basics

```bash
lap diff old-api.doclean new-api.doclean
```

Compare any two DocLean files to see what changed:

```bash
# Compile two versions
lap compile specs/stripe-charges-v1.yaml -o v1.doclean
lap compile specs/stripe-charges-v2.yaml -o v2.doclean

# Diff them
lap diff v1.doclean v2.doclean
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
lap diff v1.doclean v2.doclean --format changelog --version "2.0.0"
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
    paths: ['specs/**']

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
          python3 cli.py compile specs/my-api.yaml -o new.doclean
          # Previous version (from main branch)
          git show main:specs/my-api.yaml > /tmp/old-spec.yaml
          python3 cli.py compile /tmp/old-spec.yaml -o old.doclean

      - name: Check for breaking changes
        run: |
          output=$(python3 cli.py diff old.doclean new.doclean --format changelog)
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

for spec in specs/*.yaml; do
  name=$(basename "$spec" .yaml)
  if [ -f "output/${name}.doclean" ]; then
    python3 cli.py compile "$spec" -o "/tmp/${name}-new.doclean"
    diff_output=$(python3 cli.py diff "output/${name}.doclean" "/tmp/${name}-new.doclean" 2>&1)
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

for spec in specs/*.yaml; do
  name=$(basename "$spec" .yaml)
  cp "output/${name}.doclean" "/tmp/${name}-prev.doclean" 2>/dev/null

  # Recompile
  python3 cli.py compile "$spec" -o "output/${name}.doclean"

  # Diff against previous
  if [ -f "/tmp/${name}-prev.doclean" ]; then
    changes=$(python3 cli.py diff "/tmp/${name}-prev.doclean" "output/${name}.doclean" --format summary)
    if [ -n "$changes" ]; then
      echo "Changes detected in ${name}:"
      echo "$changes"
      # Send notification (Slack, email, etc.)
    fi
  fi
done
```
