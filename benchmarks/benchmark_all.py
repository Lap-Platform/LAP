#!/usr/bin/env python3
"""
Multi-API Benchmark — Compile all specs and produce a summary table.

Supports OpenAPI (built-in) and pluggable formats: GraphQL, AsyncAPI, Protobuf, Postman.
New compilers are auto-detected from src/<format>_compiler.py with a compile_<format>() function.

Usage:
    python benchmark_all.py [--md] [--format openapi] [--all-formats]
"""

import argparse
import glob
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.compilers.openapi import compile_openapi
from core.utils import count_tokens

# ── Multi-format compiler registry ──────────────────────────────────

COMPILERS = {"openapi": compile_openapi}

SPEC_EXTENSIONS = {
    "openapi": ("*.yaml", "*.yml", "*.json"),
    "graphql": ("*.graphql", "*.gql", "*.json"),
    "asyncapi": ("*.yaml", "*.yml", "*.json"),
    "protobuf": ("*.proto",),
    "postman": ("*.json",),
}

# Auto-detect new format compilers
for _fmt in ("graphql", "asyncapi", "protobuf", "postman"):
    try:
        _mod = __import__(f"{_fmt}_compiler")
        _fn = getattr(_mod, f"compile_{_fmt}", None)
        if _fn:
            COMPILERS[_fmt] = _fn
    except ImportError:
        pass


def get_spec_dir(fmt: str) -> Path:
    """Return the spec directory for a format."""
    base = Path(__file__).parent.parent / "examples"
    if fmt == "openapi":
        return base
    return base / fmt


def find_specs(fmt: str, skip_names: set = None) -> list[str]:
    """Find all spec files for a given format."""
    d = get_spec_dir(fmt)
    if not d.exists():
        return []
    files = []
    for pattern in SPEC_EXTENSIONS.get(fmt, ()):
        files.extend(glob.glob(str(d / pattern)))
    files = sorted(set(files))
    if skip_names:
        files = [f for f in files if Path(f).stem not in skip_names]
    return files


def get_real_docs_tokens(api_name: str) -> tuple:
    """Get real human docs token count if available, otherwise return None.
    Returns (tokens, is_measured) tuple."""
    real_docs_dir = Path(__file__).parent.parent / "examples" / "real-docs"
    real_doc = real_docs_dir / f"{api_name}.md"
    if real_doc.exists():
        return count_tokens(real_doc.read_text()), True
    return None, False


def run_all(output_md: bool = False, formats: list[str] = None):
    if formats is None:
        formats = list(COMPILERS.keys())

    # Skip very large specs that take too long to compile
    skip_names = {"stripe-full", "zoom", "google_compute"}

    all_results = {}  # format -> list of results

    for fmt in formats:
        if fmt not in COMPILERS:
            print(f"⚠️  No compiler found for {fmt} — skipping")
            continue

        spec_files = find_specs(fmt, skip_names)
        if not spec_files:
            continue

        compiler = COMPILERS[fmt]
        results = []
        output_dir = Path(__file__).parent.parent / "output"

        for spec_path in spec_files:
            name = Path(spec_path).stem
            raw_text = Path(spec_path).read_text()

            # Use cached output if available (faster for large specs)
            cached_doclean = output_dir / f"{name}.doclean"
            cached_lean = output_dir / f"{name}.lean.doclean"
            if fmt == "openapi" and cached_doclean.exists() and cached_lean.exists():
                doclean_text = cached_doclean.read_text()
                lean_text = cached_lean.read_text()
                endpoint_count = sum(1 for l in doclean_text.split("\n") if l.startswith("@endpoint "))
                compile_ms = 0
            else:
                try:
                    t0 = time.perf_counter()
                    doclean_spec = compiler(spec_path)
                    compile_ms = round((time.perf_counter() - t0) * 1000, 1)
                    doclean_text = doclean_spec.to_doclean(lean=False)
                    lean_text = doclean_spec.to_doclean(lean=True)
                    endpoint_count = len(doclean_spec.endpoints)
                except Exception as e:
                    print(f"  ⚠️  {name}: {e}")
                    continue

            raw_tokens = count_tokens(raw_text)
            real_tokens, is_measured = get_real_docs_tokens(name)
            human_tokens = real_tokens if real_tokens else None
            doclean_tokens = count_tokens(doclean_text)
            lean_tokens = count_tokens(lean_text)

            results.append({
                "name": name,
                "format": fmt,
                "endpoints": endpoint_count,
                "raw_tokens": raw_tokens,
                "human_tokens": human_tokens,
                "human_measured": is_measured,
                "doclean_tokens": doclean_tokens,
                "lean_tokens": lean_tokens,
                "ratio_vs_raw": raw_tokens / doclean_tokens if doclean_tokens else 0,
                "ratio_vs_human": human_tokens / doclean_tokens if (human_tokens and doclean_tokens) else None,
                "lean_ratio_vs_raw": raw_tokens / lean_tokens if lean_tokens else 0,
                "lean_ratio_vs_human": human_tokens / lean_tokens if (human_tokens and lean_tokens) else None,
                "std_vs_raw_note": "larger" if doclean_tokens > raw_tokens else "",
                "compile_ms": compile_ms,
            })

        if results:
            all_results[fmt] = results

    # Print tables per format
    for fmt, results in all_results.items():
        header = f"{'API':<20} {'EPs':>4} {'Raw':>9} {'HumanDoc':>9} {'DocLean':>9} {'Lean':>9} {'Std/Raw':>8} {'Lean/Raw':>8} {'Lean/HD':>8} {'Time':>8} {'Note':>6}"
        sep = "-" * len(header)

        print()
        print("=" * len(header))
        print(f"📊 LAP DocLean Multi-API Benchmark — {fmt.upper()}")
        print("=" * len(header))
        print()
        print(header)
        print(sep)

        totals = {"raw": 0, "human": 0, "doclean": 0, "lean": 0, "human_count": 0}
        total_endpoints = 0
        for r in results:
            totals["raw"] += r["raw_tokens"]
            if r["human_tokens"]:
                totals["human"] += r["human_tokens"]
                totals["human_count"] += 1
            totals["doclean"] += r["doclean_tokens"]
            totals["lean"] += r["lean_tokens"]
            total_endpoints += r["endpoints"]
            human_str = f"{r['human_tokens']:>9,}" if r["human_tokens"] else "      n/a"
            human_mark = "†" if r["human_measured"] else ""
            lean_hd = f"{r['lean_ratio_vs_human']:>7.1f}x" if r["lean_ratio_vs_human"] else "     n/a"
            note = "  +std" if r["std_vs_raw_note"] else ""
            time_str = f"{r['compile_ms']:>6.0f}ms" if r["compile_ms"] else "  cached"
            print(f"{r['name']:<20} {r['endpoints']:>4} {r['raw_tokens']:>9,} {human_str}{human_mark} {r['doclean_tokens']:>9,} {r['lean_tokens']:>9,} {r['ratio_vs_raw']:>7.1f}x {r['lean_ratio_vs_raw']:>7.1f}x {lean_hd}{note} {time_str}")

        print(sep)
        t = totals
        print(f"{'TOTAL':<20} {total_endpoints:>4} {t['raw']:>9,}           {t['doclean']:>9,} {t['lean']:>9,} {t['raw']/t['doclean']:>7.1f}x {t['raw']/t['lean']:>7.1f}x")
        print()
        print("† = measured from real API documentation pages")
        print("+std = DocLean standard is LARGER than raw spec (adds typed schemas)")
        print()

    if output_md:
        for fmt, results in all_results.items():
            t = {"raw": sum(r["raw_tokens"] for r in results), "doclean": sum(r["doclean_tokens"] for r in results), "lean": sum(r["lean_tokens"] for r in results)}
            te = sum(r["endpoints"] for r in results)
            print(f"\n## {fmt.upper()} Benchmark\n")
            print("| API | Endpoints | Raw | DocLean Std | DocLean Lean | Std vs Raw | Lean vs Raw | Human Docs† | Lean vs HD |")
            print("|-----|-----------|-----|-------------|-------------|-----------|-----------|-------------|-----------|")
            for r in results:
                human_str = f"{r['human_tokens']:,}†" if r["human_measured"] else ("n/a" if not r["human_tokens"] else f"~{r['human_tokens']:,}")
                lean_hd = f"{r['lean_ratio_vs_human']:.1f}x" if r["lean_ratio_vs_human"] else "n/a"
                std_note = " ⚠️" if r["std_vs_raw_note"] else ""
                print(f"| {r['name']} | {r['endpoints']} | {r['raw_tokens']:,} | {r['doclean_tokens']:,}{std_note} | {r['lean_tokens']:,} | {r['ratio_vs_raw']:.1f}x | {r['lean_ratio_vs_raw']:.1f}x | {human_str} | {lean_hd} |")
            print(f"| **TOTAL** | **{te}** | **{t['raw']:,}** | **{t['doclean']:,}** | **{t['lean']:,}** | **{t['raw']/t['doclean']:.1f}x** | **{t['raw']/t['lean']:.1f}x** | | |")

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Multi-API DocLean benchmark")
    parser.add_argument("--md", action="store_true", help="Also output markdown table")
    parser.add_argument("--format", choices=list(SPEC_EXTENSIONS.keys()), help="Run only this format")
    parser.add_argument("--all-formats", action="store_true", help="Run all detected formats")
    args = parser.parse_args()
    formats = [args.format] if args.format else (list(COMPILERS.keys()) if args.all_formats else None)
    run_all(output_md=args.md, formats=formats)


if __name__ == "__main__":
    main()
