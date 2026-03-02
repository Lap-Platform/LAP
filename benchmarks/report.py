#!/usr/bin/env python3
"""
Generate a comprehensive markdown report of all LAP benchmarks.
Outputs to REPORT.md in the project root.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from lap.core.compilers.openapi import compile_openapi
from lap.core.utils import count_tokens, MODEL_COSTS

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output"
REPORT = ROOT / "REPORT.md"


def compile_all_specs():
    specs = sorted(ROOT.glob("examples/*.yaml"))
    results = []
    for sp in specs:
        name = sp.stem
        spec = compile_openapi(str(sp))
        verbose = spec.to_original_text()
        lap = spec.to_lap(lean=False)
        lean = spec.to_lap(lean=True)
        tv, td, tl = count_tokens(verbose), count_tokens(lap), count_tokens(lean)
        results.append({
            "name": name, "verbose_chars": len(verbose), "lap_chars": len(lap), "lean_chars": len(lean),
            "verbose_tokens": tv, "lap_tokens": td, "lean_tokens": tl,
            "reduction_std": (1 - td / tv) * 100, "reduction_lean": (1 - tl / tv) * 100,
        })
    return results


def load_agent_results():
    p = OUTPUT / "agent_results.json"
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return None


def generate():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    specs = compile_all_specs()
    agent = load_agent_results()

    lines = [
        "# LAP LAP — Benchmark Report",
        f"\n*Generated: {now}*\n",
        "## Token Compression Benchmarks\n",
        "| Spec | Verbose | LAP | Lean | Reduction (Std) | Reduction (Lean) |",
        "|------|--------:|--------:|-----:|----------------:|-----------------:|",
    ]

    totals = {"v": 0, "d": 0, "l": 0}
    for s in specs:
        totals["v"] += s["verbose_tokens"]
        totals["d"] += s["lap_tokens"]
        totals["l"] += s["lean_tokens"]
        lines.append(f"| {s['name']} | {s['verbose_tokens']:,} | {s['lap_tokens']:,} | {s['lean_tokens']:,} "
                      f"| {s['reduction_std']:.1f}% | {s['reduction_lean']:.1f}% |")

    overall_std = (1 - totals["d"] / totals["v"]) * 100
    overall_lean = (1 - totals["l"] / totals["v"]) * 100
    lines.append(f"| **TOTAL** | **{totals['v']:,}** | **{totals['d']:,}** | **{totals['l']:,}** "
                 f"| **{overall_std:.1f}%** | **{overall_lean:.1f}%** |")

    # Cost projections
    lines.extend([
        "\n## Cost Projections (per 1K lookups)\n",
        "| Model | Verbose | LAP | Lean | Savings |",
        "|-------|--------:|--------:|-----:|--------:|",
    ])
    for model, cost in MODEL_COSTS.items():
        cv = totals["v"] / 1000 * cost * 1000
        cl = totals["l"] / 1000 * cost * 1000
        lines.append(f"| {model} | ${cv:.2f} | — | ${cl:.2f} | ${cv - cl:.2f} |")

    # Agent results
    if agent:
        lines.extend([
            "\n## Agent Validation Tests\n",
            "| # | API | Task | Verbose | LAP | Lean | Reduction | Status |",
            "|---|-----|------|--------:|--------:|-----:|----------:|--------|",
        ])
        for i, r in enumerate(agent, 1):
            t = r["tokens"]
            status = r.get("status", "dry-run")
            emoji = "🏃" if status == "dry-run" else ("✅" if status == "pass" else "⚠️")
            task_short = r["task"][:40]
            api = r.get("spec", "").split("/")[-1].split("-")[0].title()
            lines.append(f"| {i} | {api} | {task_short} | {t['verbose']:,} | {t['lap']:,} | {t['lean']:,} "
                         f"| {t['reduction_lean']} | {emoji} {status} |")

        if any(r.get("equivalence") for r in agent):
            matches = sum(1 for r in agent if r.get("equivalence", {}).get("verbose_vs_lean", {}).get("match"))
            lines.append(f"\n**Functional Equivalence (Lean vs Verbose): {matches}/{len(agent)} tasks match**\n")

    lines.extend([
        "\n## Key Findings\n",
        f"- **Average token reduction (standard):** {overall_std:.1f}%",
        f"- **Average token reduction (lean):** {overall_lean:.1f}%",
        f"- **Compression ratio:** {totals['v'] / totals['l']:.1f}x (lean)",
        f"- **Specs tested:** {len(specs)}",
        f"- **Agent tasks defined:** {len(agent) if agent else 'N/A'}",
        "",
        "## Methodology\n",
        "- Token counts via tiktoken (cl100k_base encoding)",
        "- LAP compiled from OpenAPI 3.x specs",
        "- Agent tests use identical prompts, varying only the documentation format",
        "- Functional equivalence = same HTTP method, endpoint path, and required parameters",
    ])

    report = "\n".join(lines) + "\n"
    REPORT.write_text(report)
    print(f"📄 Report written to {REPORT} ({len(report):,} chars)")


if __name__ == "__main__":
    generate()
