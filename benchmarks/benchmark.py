#!/usr/bin/env python3
"""
Token Benchmark — Compare token usage between original docs and DocLean format.

Usage:
    python benchmark.py <openapi-spec.yaml> [doclean-output.doclean]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from core.compilers.openapi import compile_openapi
from core.utils import count_tokens, MODEL_COSTS


def run_benchmark(spec_path: str, doclean_path: str = None):
    """Run token comparison benchmark."""
    # Compile
    doclean_spec = compile_openapi(spec_path)
    doclean_text = doclean_spec.to_doclean()
    verbose_text = doclean_spec.to_original_text()

    # Also read raw source for comparison
    raw_source = Path(spec_path).read_text()

    # If a pre-compiled doclean file is provided, use that
    if doclean_path:
        doclean_text = Path(doclean_path).read_text()

    print("=" * 60)
    print("📊 LAP DocLean Token Benchmark")
    print("=" * 60)

    # Character counts
    print(f"\n📏 Character Count:")
    print(f"  Raw OpenAPI spec:    {len(raw_source):>8,} chars")
    print(f"  Verbose (human-readable): {len(verbose_text):>8,} chars")
    print(f"  DocLean (compressed): {len(doclean_text):>8,} chars")
    print(f"  Char reduction:      {(1 - len(doclean_text)/len(verbose_text))*100:.1f}%")

    # Token counts per model
    print(f"\n🔢 Token Counts:")
    print(f"  {'Model':<20} {'Verbose':>10} {'DocLean':>10} {'Reduction':>10} {'Ratio':>8}")
    print(f"  {'-'*18:<20} {'-'*10:>10} {'-'*10:>10} {'-'*10:>10} {'-'*8:>8}")

    results = {}
    for model_name in MODEL_COSTS:
        verbose_tokens = count_tokens(verbose_text, "gpt-4o")  # tiktoken approx
        doclean_tokens = count_tokens(doclean_text, "gpt-4o")
        reduction = (1 - doclean_tokens / verbose_tokens) * 100
        ratio = verbose_tokens / doclean_tokens if doclean_tokens > 0 else float("inf")

        results[model_name] = {
            "verbose_tokens": verbose_tokens,
            "doclean_tokens": doclean_tokens,
            "reduction_pct": reduction,
            "ratio": ratio,
        }

        print(f"  {model_name:<20} {verbose_tokens:>10,} {doclean_tokens:>10,} {reduction:>9.1f}% {ratio:>7.1f}x")

    # Cost savings
    print(f"\n💰 Cost Savings (per 1,000 API doc lookups):")
    print(f"  {'Model':<20} {'Verbose':>10} {'DocLean':>10} {'Saved':>10}")
    print(f"  {'-'*18:<20} {'-'*10:>10} {'-'*10:>10} {'-'*10:>10}")

    for model_name, cost_per_1k in MODEL_COSTS.items():
        r = results[model_name]
        verbose_cost = (r["verbose_tokens"] / 1000) * cost_per_1k * 1000
        doclean_cost = (r["doclean_tokens"] / 1000) * cost_per_1k * 1000
        saved = verbose_cost - doclean_cost

        print(f"  {model_name:<20} ${verbose_cost:>8.2f} ${doclean_cost:>8.2f} ${saved:>8.2f}")

    # At scale
    print(f"\n🚀 At Scale (1M daily lookups, gpt-4o pricing):")
    r = results["gpt-4o"]
    daily_verbose = (r["verbose_tokens"] / 1000) * MODEL_COSTS["gpt-4o"] * 1_000_000
    daily_doclean = (r["doclean_tokens"] / 1000) * MODEL_COSTS["gpt-4o"] * 1_000_000
    daily_saved = daily_verbose - daily_doclean
    print(f"  Daily cost (verbose):  ${daily_verbose:>12,.2f}")
    print(f"  Daily cost (DocLean):  ${daily_doclean:>12,.2f}")
    print(f"  Daily savings:         ${daily_saved:>12,.2f}")
    print(f"  Monthly savings:       ${daily_saved * 30:>12,.2f}")
    print(f"  Annual savings:        ${daily_saved * 365:>12,.2f}")

    print(f"\n📐 Endpoints compiled: {len(doclean_spec.endpoints)}")
    print("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark token usage: verbose vs DocLean")
    parser.add_argument("spec", help="Path to OpenAPI spec")
    parser.add_argument("doclean", nargs="?", help="Path to DocLean output (optional, will compile if missing)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    results = run_benchmark(args.spec, args.doclean)

    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
