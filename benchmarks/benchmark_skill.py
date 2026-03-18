#!/usr/bin/env python3
"""
Skill benchmark -- measures token efficiency and endpoint coverage
across the spec corpus.

Two dimensions:
A. Token efficiency (automated, runs against spec corpus)
B. Agent task benchmark (semi-automated, 10 representative APIs)
"""

import glob
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lap.core.compilers.openapi import compile_openapi
from lap.core.compilers.skill import generate_skill, SkillOptions, SKILL_MD_TOKEN_BUDGET
from lap.core.utils import count_tokens


def benchmark_single(spec_path: str) -> dict:
    """Benchmark a single spec's skill output."""
    raw = Path(spec_path).read_text(encoding='utf-8')
    spec = compile_openapi(spec_path)
    skill = generate_skill(spec)

    raw_tokens = count_tokens(raw)
    skill_md_tokens = count_tokens(skill.file_map[skill.main_file])

    # Per-file breakdown
    file_tokens = {}
    for file_path, content in skill.file_map.items():
        file_tokens[file_path] = count_tokens(content)

    return {
        "name": Path(spec_path).stem,
        "api_name": spec.api_name,
        "endpoints": len(spec.endpoints),
        "raw_tokens": raw_tokens,
        "skill_md_tokens": skill_md_tokens,
        "file_tokens": file_tokens,
        "total_tokens": skill.token_count,
        "compression_ratio": raw_tokens / skill.token_count if skill.token_count else 0,
        "endpoint_coverage": _check_coverage(spec, skill),
    }


def benchmark_corpus(directory: str) -> list:
    """Benchmark all specs in a directory."""
    spec_files = sorted(
        glob.glob(os.path.join(directory, "*.yaml")) +
        glob.glob(os.path.join(directory, "*.yml")) +
        glob.glob(os.path.join(directory, "*.json"))
    )
    spec_files = [f for f in spec_files if "stripe-full" not in f]

    results = []
    for spec_path in spec_files:
        try:
            result = benchmark_single(spec_path)
            results.append(result)
        except Exception as e:
            print(f"  SKIP {Path(spec_path).stem}: {e}", file=sys.stderr)
    return results


def print_report(results: list):
    """Print a formatted benchmark report."""
    if not results:
        print("No results to report.")
        return

    print(f"\n{'='*80}")
    print(f"  Skill Token Benchmark -- {len(results)} specs")
    print(f"{'='*80}\n")

    # Per-spec results
    print(f"{'API':<30} {'EPs':>4} {'Raw':>8} {'Skill.md':>8} {'Total':>8} {'Ratio':>6} {'Cov':>5}")
    print(f"{'-'*30} {'-'*4} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*5}")

    for r in results:
        print(
            f"{r['name'][:30]:<30} {r['endpoints']:>4} "
            f"{r['raw_tokens']:>8,} {r['skill_md_tokens']:>8,} "
            f"{r['total_tokens']:>8,} {r['compression_ratio']:>5.1f}x "
            f"{r['endpoint_coverage']:>4.0f}%"
        )

    # Aggregates
    skill_md_tokens = [r["skill_md_tokens"] for r in results]
    total_tokens = [r["total_tokens"] for r in results]
    coverages = [r["endpoint_coverage"] for r in results]
    ratios = [r["compression_ratio"] for r in results]

    print(f"\n{'='*80}")
    print("  Aggregate Statistics")
    print(f"{'='*80}\n")

    print(f"  SKILL.md tokens:")
    print(f"    Median: {sorted(skill_md_tokens)[len(skill_md_tokens)//2]:,}")
    print(f"    P95:    {sorted(skill_md_tokens)[min(int(len(skill_md_tokens)*0.95), len(skill_md_tokens)-1)]:,}")
    print(f"    Min:    {min(skill_md_tokens):,}")
    print(f"    Max:    {max(skill_md_tokens):,}")

    print(f"\n  Total skill tokens:")
    print(f"    Median: {sorted(total_tokens)[len(total_tokens)//2]:,}")
    print(f"    P95:    {sorted(total_tokens)[min(int(len(total_tokens)*0.95), len(total_tokens)-1)]:,}")
    print(f"    Min:    {min(total_tokens):,}")
    print(f"    Max:    {max(total_tokens):,}")

    print(f"\n  Compression ratio (raw -> skill):")
    print(f"    Median: {sorted(ratios)[len(ratios)//2]:.1f}x")
    print(f"    Min:    {min(ratios):.1f}x")
    print(f"    Max:    {max(ratios):.1f}x")

    print(f"\n  Endpoint coverage:")
    print(f"    Mean:   {sum(coverages)/len(coverages):.1f}%")
    print(f"    Min:    {min(coverages):.1f}%")

    # Budget check
    over_budget = sum(1 for t in skill_md_tokens if t > SKILL_MD_TOKEN_BUDGET)
    print(f"\n  Budget (SKILL.md < {SKILL_MD_TOKEN_BUDGET} tokens):")
    print(f"    Pass:   {len(results) - over_budget}/{len(results)}")
    if over_budget:
        print(f"    Over:   {over_budget} specs exceed {SKILL_MD_TOKEN_BUDGET} token target")


def _check_coverage(spec, skill) -> float:
    """Check what percentage of spec endpoints appear in the skill catalog."""
    skill_md = skill.file_map[skill.main_file]
    found = sum(
        1 for ep in spec.endpoints
        if f"| {ep.method.upper()} |" in skill_md and ep.path in skill_md
    )
    return (found / len(spec.endpoints) * 100) if spec.endpoints else 100.0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python benchmark_skill.py <spec_or_directory>")
        sys.exit(1)

    target = sys.argv[1]
    if os.path.isdir(target):
        results = benchmark_corpus(target)
        print_report(results)
    else:
        result = benchmark_single(target)
        print(f"\n  API: {result['api_name']}")
        print(f"  Endpoints: {result['endpoints']}")
        print(f"  Raw tokens: {result['raw_tokens']:,}")
        print(f"  SKILL.md tokens: {result['skill_md_tokens']:,}")
        print(f"  Total skill tokens: {result['total_tokens']:,}")
        print(f"  Compression: {result['compression_ratio']:.1f}x")
        print(f"  Coverage: {result['endpoint_coverage']:.0f}%")
