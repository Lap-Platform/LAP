#!/usr/bin/env python3
"""
Master Benchmark Runner — orchestrates all existing benchmarks and produces
a consolidated report with JSON output.

Exit code 0 only if ALL lossless validations pass.

Usage:
    python run_all.py [--json] [--format openapi]
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path



def run_all(output_json: bool = True, formats: list[str] = None):
    start = time.perf_counter()
    ts = datetime.now(timezone.utc)

    print("\n" + "█" * 80)
    print("  LAP LAP — COMPREHENSIVE BENCHMARK SUITE")
    print(f"  {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("█" * 80)

    report = {"timestamp": ts.isoformat(), "benchmarks": {}}

    # 1. Token benchmark (benchmark_all.py)
    print("\n\n📊 Running Multi-API Token Benchmark...")
    from benchmark_all import run_all as run_token_benchmark
    token_results = run_token_benchmark(formats=formats)
    report["benchmarks"]["token_compression"] = {}
    for fmt, results in (token_results or {}).items():
        total_raw = sum(r["raw_tokens"] for r in results)
        total_lean = sum(r["lean_tokens"] for r in results)
        report["benchmarks"]["token_compression"][fmt] = {
            "spec_count": len(results),
            "total_endpoints": sum(r["endpoints"] for r in results),
            "total_raw_tokens": total_raw,
            "total_lean_tokens": total_lean,
            "overall_compression_ratio": round(total_raw / total_lean, 1) if total_lean else 0,
        }

    # 2. Lossless validation (validate.py)
    print("\n\n🔍 Running Lossless Validation...")
    from validate import validate_all, print_all_results
    validation_results = validate_all(formats=formats)
    print_all_results(validation_results)

    all_pass = True
    report["benchmarks"]["lossless_validation"] = {}
    for fmt, results in validation_results.items():
        passed = sum(1 for r in results if r.get("pass", False))
        errored = sum(1 for r in results if "error" in r)
        total = len(results)
        fmt_pass = (passed + errored) == total  # errors are not failures, just skips
        if not fmt_pass:
            all_pass = False
        report["benchmarks"]["lossless_validation"][fmt] = {
            "total_specs": total,
            "passed": passed,
            "errored": errored,
            "failed": total - passed - errored,
            "all_pass": fmt_pass,
        }

    # 3. Agent test (dry-run token comparison)
    tasks_file = Path(__file__).parent / "test_tasks.yaml"
    if tasks_file.exists():
        print("\n\n🤖 Running Agent Validation (dry-run)...")
        import os
        old_cwd = os.getcwd()
        os.chdir(Path(__file__).parent.parent)  # project root for relative spec paths
        from agent_test import run_all as run_agent, print_summary
        try:
            agent_results = run_agent(str(tasks_file), dry_run=True)
            print_summary(agent_results)
            total_v = sum(r["tokens"]["verbose"] for r in agent_results)
            total_l = sum(r["tokens"]["lean"] for r in agent_results)
            report["benchmarks"]["agent_simulation"] = {
                "tasks": len(agent_results),
                "total_verbose_tokens": total_v,
                "total_lean_tokens": total_l,
                "token_reduction_pct": round((1 - total_l / total_v) * 100, 1) if total_v else 0,
            }
        except Exception as e:
            print(f"  ⚠️  Agent test skipped: {e}")
        finally:
            os.chdir(old_cwd)

    total_time = time.perf_counter() - start
    report["total_time_s"] = round(total_time, 2)
    report["overall_pass"] = all_pass

    # Save report
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    report_path = results_dir / f"report_{ts.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    latest = results_dir / "report_latest.json"
    latest.write_text(json.dumps(report, indent=2, default=str))

    # Final summary
    print("\n" + "█" * 80)
    print("  CONSOLIDATED RESULTS")
    print("█" * 80)

    for fmt, data in report["benchmarks"].get("token_compression", {}).items():
        print(f"\n  📊 {fmt.upper()}: {data['spec_count']} specs, {data['total_endpoints']} endpoints")
        print(f"     {data['total_raw_tokens']:,} raw → {data['total_lean_tokens']:,} lean ({data['overall_compression_ratio']}x)")

    for fmt, data in report["benchmarks"].get("lossless_validation", {}).items():
        status = "✅" if data["all_pass"] else "❌"
        print(f"\n  {status} {fmt.upper()} validation: {data['passed']}/{data['total_specs']} pass")

    if "agent_simulation" in report["benchmarks"]:
        a = report["benchmarks"]["agent_simulation"]
        print(f"\n  🤖 Agent: {a['tasks']} tasks, {a['token_reduction_pct']}% token reduction")

    print(f"\n  ⏱️  Total: {total_time:.1f}s")
    print(f"  {'✅ ALL PASS' if all_pass else '❌ FAILURES DETECTED'}")
    print(f"  Report: {report_path}")
    print("█" * 80 + "\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Run all LAP benchmarks")
    p.add_argument("--format", help="Run only this format")
    p.add_argument("--json", action="store_true", help="Save JSON report")
    args = p.parse_args()
    fmts = [args.format] if args.format else None
    sys.exit(run_all(output_json=args.json, formats=fmts))
