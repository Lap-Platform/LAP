#!/usr/bin/env python3
"""
Blind Agent Benchmark Runner for LAP (Lean API Protocol)

Tests whether agents perform equally well or better with LAP-compiled specs
vs raw OpenAPI, across multiple models and APIs.

Usage:
    python blind_agent_benchmark.py --api stripe --format lap_lean --model claude --dry-run
    python blind_agent_benchmark.py --all
    python blind_agent_benchmark.py --score --report

See docs/BLIND_AGENT_BENCHMARK_PLAN.md for full methodology.
"""

import argparse
import json
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# LAP compilation imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.compilers.openapi import compile_openapi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SPEC_DIR = Path(__file__).parent.parent / "examples" / "verbose" / "openapi"
RESULTS_DIR = Path(__file__).parent / "results" / "blind_benchmark"

MODELS = ["claude-sonnet-4", "gpt-4o", "gemini-2.0-flash"]

FORMATS = ["raw", "json_min", "yaml_nodesc", "lap_standard", "lap_lean"]

# Map from task API name to spec filename (without .yaml)
API_SPEC_MAP = {
    "stripe": "stripe-charges",
    "github": "github-core",
    "plaid": "plaid",
    "hetzner": "hetzner",
    "notion": "notion",
    "snyk": "snyk",
    "twilio": "twilio-core",
}

# ---------------------------------------------------------------------------
# Tasks: 3 per API, 7 APIs = 21 tasks × 5 formats × 3 models = 315 tests
# (Plan says 10 APIs × 3 tasks × 5 formats × 3 models = 450 — add more as needed)
# ---------------------------------------------------------------------------

TASKS = {
    "stripe": [
        {"id": "stripe_1", "desc": "Write a Python function to create a charge for $50 USD, capture it, then retrieve the charge details"},
        {"id": "stripe_2", "desc": "List all charges for customer cus_ABC, handling pagination to get all results"},
        {"id": "stripe_3", "desc": "Create a charge with metadata, handle the error if the card is declined"},
    ],
    "github": [
        {"id": "github_1", "desc": "Create an issue with labels, then list all open issues sorted by creation date"},
        {"id": "github_2", "desc": "Create a pull request from feature branch to main, then merge it with squash"},
        {"id": "github_3", "desc": "List all issues with the 'bug' label, paginate through all pages"},
    ],
    "plaid": [
        {"id": "plaid_1", "desc": "Exchange a public token for an access token, then fetch recent transactions"},
        {"id": "plaid_2", "desc": "Get account balances and format them by account type"},
        {"id": "plaid_3", "desc": "Set up a webhook for transaction updates and handle the verification"},
    ],
    "hetzner": [
        {"id": "hetzner_1", "desc": "Create a server with Ubuntu, attach a floating IP, and create a firewall rule allowing SSH"},
        {"id": "hetzner_2", "desc": "List all servers, find those running CentOS, and resize them to cx21"},
        {"id": "hetzner_3", "desc": "Create a load balancer, add two servers as targets, configure health checks"},
    ],
    "notion": [
        {"id": "notion_1", "desc": "Create a new database with Name, Status, and Date columns"},
        {"id": "notion_2", "desc": "Query a database filtering by status='Active', sorted by date descending"},
        {"id": "notion_3", "desc": "Create a page in a database with rich text content and a checkbox property"},
    ],
    "snyk": [
        {"id": "snyk_1", "desc": "List all projects in an organization, handling pagination"},
        {"id": "snyk_2", "desc": "Get all issues for a project, filter by severity 'high' or 'critical'"},
        {"id": "snyk_3", "desc": "Import a new project from a GitHub repo and monitor it"},
    ],
    "twilio": [
        {"id": "twilio_1", "desc": "Send an SMS message and check its delivery status"},
        {"id": "twilio_2", "desc": "List all messages sent in the last 24 hours with pagination"},
        {"id": "twilio_3", "desc": "Send an MMS with a media URL, handle authentication properly"},
    ],
}

# ---------------------------------------------------------------------------
# Spec loading & format conversion
# ---------------------------------------------------------------------------

def load_raw_yaml(api: str) -> str:
    """Load the original YAML spec file."""
    spec_name = API_SPEC_MAP.get(api, api)
    path = SPEC_DIR / f"{spec_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Spec not found: {path}")
    return path.read_text()


def strip_descriptions(obj):
    """Recursively strip description, summary, and example fields."""
    if isinstance(obj, dict):
        return {
            k: strip_descriptions(v)
            for k, v in obj.items()
            if k not in ("description", "summary", "example", "examples")
        }
    elif isinstance(obj, list):
        return [strip_descriptions(item) for item in obj]
    return obj


def prepare_spec(api: str, fmt: str) -> str:
    """
    Prepare an API spec in the requested format.

    Returns the spec as a string ready to embed in a prompt.
    """
    raw = load_raw_yaml(api)

    if fmt == "raw":
        return raw

    elif fmt == "json_min":
        parsed = yaml.safe_load(raw)
        return json.dumps(parsed, separators=(",", ":"), default=str)

    elif fmt == "yaml_nodesc":
        parsed = yaml.safe_load(raw)
        stripped = strip_descriptions(parsed)
        return yaml.dump(stripped, default_flow_style=False, width=200)

    elif fmt == "lap_standard":
        spec_name = API_SPEC_MAP.get(api, api)
        path = SPEC_DIR / f"{spec_name}.yaml"
        compiled = compile_openapi(str(path))
        return compiled.to_lap(lean=False)

    elif fmt == "lap_lean":
        spec_name = API_SPEC_MAP.get(api, api)
        path = SPEC_DIR / f"{spec_name}.yaml"
        compiled = compile_openapi(str(path))
        return compiled.to_lap(lean=True)

    else:
        raise ValueError(f"Unknown format: {fmt}")


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior software engineer. You will be given an API specification and a task.
Write a complete, working Python implementation for the task using the `requests` library.
Include proper authentication, error handling, and type hints.
Only use endpoints and parameters that exist in the provided specification.
Do NOT hallucinate endpoints or parameters that aren't in the spec."""

def build_prompt(spec: str, task_desc: str) -> tuple[str, str]:
    """Build (system, user) prompt pair."""
    user = f"""Given this API specification:

{spec}

Task: {task_desc}

Write a complete Python implementation."""
    return SYSTEM_PROMPT, user


# ---------------------------------------------------------------------------
# Model interface (TODO: implement with actual API keys)
# ---------------------------------------------------------------------------

def call_model(model: str, system: str, user: str) -> dict:
    """
    Call an LLM and return results.

    Returns:
        {"output": str, "input_tokens": int, "output_tokens": int, "latency_ms": int}

    TODO: Implement with actual API calls. You'll need:
        - ANTHROPIC_API_KEY for Claude
        - OPENAI_API_KEY for GPT-4o
        - GOOGLE_API_KEY for Gemini

    Example implementation for Claude:
        import anthropic
        client = anthropic.Anthropic()
        t0 = time.time()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        latency = int((time.time() - t0) * 1000)
        return {
            "output": resp.content[0].text,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "latency_ms": latency,
        }
    """
    raise NotImplementedError(
        "Add API keys and implement call_model() for each provider. "
        "See docstring for example."
    )


# ---------------------------------------------------------------------------
# Scoring (TODO: implement manual or LLM-as-judge scoring)
# ---------------------------------------------------------------------------

def score_output(task_id: str, output: str) -> dict:
    """
    Score a model output on 5 dimensions, each 0-3.

    Returns:
        {correctness, completeness, api_usage, error_handling, auth}

    Scoring rubric (from BLIND_AGENT_BENCHMARK_PLAN.md):
        0 = Missing/broken
        1 = Minimal/basic
        2 = Good with minor issues
        3 = Perfect

    TODO: Implement scoring. Options:
        1. Manual review: print outputs for human reviewers
        2. LLM-as-judge: use a strong model to score outputs
        3. Automated checks: syntax validation + endpoint/param matching
    """
    return {
        "correctness": 0,
        "completeness": 0,
        "api_usage": 0,
        "error_handling": 0,
        "auth": 0,
    }


# ---------------------------------------------------------------------------
# Result storage
# ---------------------------------------------------------------------------

def result_path(api: str, task_id: str, fmt: str, model: str) -> Path:
    """Get the path for storing a single test result."""
    return RESULTS_DIR / api / f"{task_id}__{fmt}__{model}.json"


def save_result(api: str, task_id: str, fmt: str, model: str, result: dict):
    """Save a single benchmark result to disk."""
    path = result_path(api, task_id, fmt, model)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))


def load_all_results() -> list[dict]:
    """Load all saved results."""
    results = []
    if not RESULTS_DIR.exists():
        return results
    for f in RESULTS_DIR.rglob("*.json"):
        try:
            results.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            continue
    return results


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def generate_report(results: list[dict]) -> str:
    """Generate a markdown summary report from benchmark results."""
    if not results:
        return "# Blind Agent Benchmark Report\n\nNo results found.\n"

    lines = [
        "# Blind Agent Benchmark Report",
        f"\nGenerated: {datetime.now(timezone.utc).isoformat()}",
        f"\nTotal results: {len(results)}",
        "",
        "## Summary: Average Score by Format × Model",
        "",
        "| Format | Model | Avg Score (/15) | Avg Input Tokens | Avg Output Tokens | Avg Latency (ms) |",
        "|--------|-------|----------------|-----------------|------------------|-----------------|",
    ]

    # Aggregate by (format, model)
    from collections import defaultdict
    agg = defaultdict(lambda: {"scores": [], "input_tokens": [], "output_tokens": [], "latency": []})
    for r in results:
        key = (r.get("format", "?"), r.get("model", "?"))
        score = r.get("score", {})
        total = sum(score.values()) if isinstance(score, dict) else 0
        agg[key]["scores"].append(total)
        agg[key]["input_tokens"].append(r.get("input_tokens", 0))
        agg[key]["output_tokens"].append(r.get("output_tokens", 0))
        agg[key]["latency"].append(r.get("latency_ms", 0))

    for (fmt, model), data in sorted(agg.items()):
        n = len(data["scores"])
        avg_score = sum(data["scores"]) / n if n else 0
        avg_in = sum(data["input_tokens"]) / n if n else 0
        avg_out = sum(data["output_tokens"]) / n if n else 0
        avg_lat = sum(data["latency"]) / n if n else 0
        lines.append(f"| {fmt} | {model} | {avg_score:.1f} | {avg_in:.0f} | {avg_out:.0f} | {avg_lat:.0f} |")

    lines += [
        "",
        "## Summary: Average Score by API",
        "",
        "| API | Avg Score (/15) | Tests |",
        "|-----|----------------|-------|",
    ]

    api_agg = defaultdict(lambda: {"scores": [], "count": 0})
    for r in results:
        api = r.get("api", "?")
        score = r.get("score", {})
        total = sum(score.values()) if isinstance(score, dict) else 0
        api_agg[api]["scores"].append(total)
        api_agg[api]["count"] += 1

    for api, data in sorted(api_agg.items()):
        n = len(data["scores"])
        avg = sum(data["scores"]) / n if n else 0
        lines.append(f"| {api} | {avg:.1f} | {n} |")

    lines += [
        "",
        "## Token Savings",
        "",
        "| Format | Avg Input Tokens | vs Raw |",
        "|--------|-----------------|--------|",
    ]

    fmt_tokens = defaultdict(list)
    for r in results:
        fmt_tokens[r.get("format", "?")].append(r.get("input_tokens", 0))

    raw_avg = sum(fmt_tokens.get("raw", [0])) / max(len(fmt_tokens.get("raw", [1])), 1)
    for fmt in FORMATS:
        tokens = fmt_tokens.get(fmt, [])
        if tokens:
            avg = sum(tokens) / len(tokens)
            ratio = f"{raw_avg / avg:.1f}x" if avg > 0 else "N/A"
            lines.append(f"| {fmt} | {avg:.0f} | {ratio} |")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    apis: list[str],
    formats: list[str],
    models: list[str],
    dry_run: bool = False,
    verbose: bool = False,
):
    """Run the benchmark across all combinations."""
    total = sum(len(TASKS.get(a, [])) for a in apis) * len(formats) * len(models)
    print(f"Benchmark: {len(apis)} APIs × {len(formats)} formats × {len(models)} models = {total} tests")

    if dry_run:
        print("\n[DRY RUN] Would execute these tests:\n")

    completed = 0
    skipped = 0
    errors = 0

    for api in apis:
        tasks = TASKS.get(api, [])
        if not tasks:
            print(f"  ⚠ No tasks defined for API: {api}")
            continue

        for fmt in formats:
            # Prepare spec once per api×format
            try:
                spec = prepare_spec(api, fmt)
                spec_tokens_approx = len(spec) // 4  # rough estimate
            except Exception as e:
                print(f"  ✗ Failed to prepare {api}/{fmt}: {e}")
                errors += len(tasks) * len(models)
                continue

            for task in tasks:
                for model in models:
                    label = f"{task['id']} | {fmt} | {model}"

                    # Skip if result already exists
                    if result_path(api, task["id"], fmt, model).exists():
                        if verbose:
                            print(f"  ⊘ {label} (cached)")
                        skipped += 1
                        continue

                    if dry_run:
                        print(f"  → {label} (~{spec_tokens_approx} input tokens)")
                        completed += 1
                        continue

                    system, user = build_prompt(spec, task["desc"])

                    try:
                        result = call_model(model, system, user)
                    except NotImplementedError:
                        # Save placeholder so we know it was attempted
                        result = {
                            "output": "[NOT IMPLEMENTED]",
                            "input_tokens": spec_tokens_approx,
                            "output_tokens": 0,
                            "latency_ms": 0,
                        }
                        print(f"  ⚠ {label} (model not implemented)")
                    except Exception as e:
                        result = {
                            "output": f"[ERROR: {e}]",
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "latency_ms": 0,
                        }
                        print(f"  ✗ {label}: {e}")
                        errors += 1
                        continue

                    # Score the output
                    score = score_output(task["id"], result["output"])

                    # Build full result record
                    record = {
                        "api": api,
                        "task_id": task["id"],
                        "task_desc": task["desc"],
                        "format": fmt,
                        "model": model,
                        "spec_chars": len(spec),
                        "input_tokens": result["input_tokens"],
                        "output_tokens": result["output_tokens"],
                        "latency_ms": result["latency_ms"],
                        "output": result["output"],
                        "score": score,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "spec_hash": hashlib.sha256(spec.encode()).hexdigest()[:12],
                    }

                    save_result(api, task["id"], fmt, model, record)
                    total_score = sum(score.values())
                    print(f"  ✓ {label} → {total_score}/15")
                    completed += 1

    print(f"\nDone: {completed} completed, {skipped} skipped, {errors} errors")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Blind Agent Benchmark for LAP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run                          # Preview all 315+ tests
  %(prog)s --api stripe --format lap_lean     # Run one API/format combo
  %(prog)s --all                              # Run everything
  %(prog)s --score                            # Re-score existing results
  %(prog)s --report                           # Generate markdown report
        """,
    )

    parser.add_argument("--api", nargs="+", choices=list(TASKS.keys()),
                        help="APIs to test (default: all)")
    parser.add_argument("--format", nargs="+", choices=FORMATS, dest="formats",
                        help="Formats to test (default: all)")
    parser.add_argument("--model", nargs="+", choices=MODELS,
                        help="Models to test (default: all)")
    parser.add_argument("--all", action="store_true",
                        help="Run all combinations")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview tests without running them")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--score", action="store_true",
                        help="Re-score all existing results")
    parser.add_argument("--report", action="store_true",
                        help="Generate markdown report from results")

    args = parser.parse_args()

    # Report mode
    if args.report:
        results = load_all_results()
        report = generate_report(results)
        report_path = RESULTS_DIR / "REPORT.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)
        print(report)
        print(f"\nSaved to {report_path}")
        return

    # Score mode
    if args.score:
        results = load_all_results()
        print(f"Re-scoring {len(results)} results...")
        for r in results:
            r["score"] = score_output(r["task_id"], r["output"])
            path = result_path(r["api"], r["task_id"], r["format"], r["model"])
            path.write_text(json.dumps(r, indent=2))
        print("Done.")
        return

    # Determine scope
    apis = args.api or list(TASKS.keys())
    formats = args.formats or FORMATS
    models = args.model or MODELS

    run_benchmark(apis, formats, models, dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
