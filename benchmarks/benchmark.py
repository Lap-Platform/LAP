#!/usr/bin/env python3
"""
Token Benchmark — Compare token usage between original docs and LAP format.

Usage:
    python benchmark.py <openapi-spec.yaml> [lap-output.lap]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from lap.core.compilers.openapi import compile_openapi
from lap.core.utils import count_tokens, MODEL_COSTS


def run_benchmark(spec_path: str, lap_path: str = None):
    """Run token comparison benchmark."""
    # Compile
    lap_spec = compile_openapi(spec_path)
    lap_text = lap_spec.to_lap()
    verbose_text = lap_spec.to_original_text()

    # Also read raw source for comparison
    raw_source = Path(spec_path).read_text(encoding='utf-8')

    # If a pre-compiled lap file is provided, use that
    if lap_path:
        lap_text = Path(lap_path).read_text(encoding='utf-8')

    print("=" * 60)
    print("📊 LAP LAP Token Benchmark")
    print("=" * 60)

    # Character counts
    print(f"\n📏 Character Count:")
    print(f"  Raw OpenAPI spec:    {len(raw_source):>8,} chars")
    print(f"  Verbose (human-readable): {len(verbose_text):>8,} chars")
    print(f"  LAP (compressed): {len(lap_text):>8,} chars")
    print(f"  Char reduction:      {(1 - len(lap_text)/len(verbose_text))*100:.1f}%")

    # Token counts per model
    print(f"\n🔢 Token Counts:")
    print(f"  {'Model':<20} {'Verbose':>10} {'LAP':>10} {'Reduction':>10} {'Ratio':>8}")
    print(f"  {'-'*18:<20} {'-'*10:>10} {'-'*10:>10} {'-'*10:>10} {'-'*8:>8}")

    results = {}
    for model_name in MODEL_COSTS:
        verbose_tokens = count_tokens(verbose_text, "gpt-4o")  # tiktoken approx
        lap_tokens = count_tokens(lap_text, "gpt-4o")
        reduction = (1 - lap_tokens / verbose_tokens) * 100
        ratio = verbose_tokens / lap_tokens if lap_tokens > 0 else float("inf")

        results[model_name] = {
            "verbose_tokens": verbose_tokens,
            "lap_tokens": lap_tokens,
            "reduction_pct": reduction,
            "ratio": ratio,
        }

        print(f"  {model_name:<20} {verbose_tokens:>10,} {lap_tokens:>10,} {reduction:>9.1f}% {ratio:>7.1f}x")

    # Cost savings
    print(f"\n💰 Cost Savings (per 1,000 API doc lookups):")
    print(f"  {'Model':<20} {'Verbose':>10} {'LAP':>10} {'Saved':>10}")
    print(f"  {'-'*18:<20} {'-'*10:>10} {'-'*10:>10} {'-'*10:>10}")

    for model_name, cost_per_1k in MODEL_COSTS.items():
        r = results[model_name]
        verbose_cost = (r["verbose_tokens"] / 1000) * cost_per_1k * 1000
        lap_cost = (r["lap_tokens"] / 1000) * cost_per_1k * 1000
        saved = verbose_cost - lap_cost

        print(f"  {model_name:<20} ${verbose_cost:>8.2f} ${lap_cost:>8.2f} ${saved:>8.2f}")

    # At scale
    print(f"\n🚀 At Scale (1M daily lookups, gpt-4o pricing):")
    r = results["gpt-4o"]
    daily_verbose = (r["verbose_tokens"] / 1000) * MODEL_COSTS["gpt-4o"] * 1_000_000
    daily_lap = (r["lap_tokens"] / 1000) * MODEL_COSTS["gpt-4o"] * 1_000_000
    daily_saved = daily_verbose - daily_lap
    print(f"  Daily cost (verbose):  ${daily_verbose:>12,.2f}")
    print(f"  Daily cost (LAP):  ${daily_lap:>12,.2f}")
    print(f"  Daily savings:         ${daily_saved:>12,.2f}")
    print(f"  Monthly savings:       ${daily_saved * 30:>12,.2f}")
    print(f"  Annual savings:        ${daily_saved * 365:>12,.2f}")

    print(f"\n📐 Endpoints compiled: {len(lap_spec.endpoints)}")
    print("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark token usage: verbose vs LAP")
    parser.add_argument("spec", help="Path to OpenAPI spec")
    parser.add_argument("lap", nargs="?", help="Path to LAP output (optional, will compile if missing)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    results = run_benchmark(args.spec, args.lap)

    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
