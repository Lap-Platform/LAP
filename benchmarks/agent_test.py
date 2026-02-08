#!/usr/bin/env python3
"""
Agent Validation Test — Prove DocLean produces functionally equivalent LLM output.

Compares LLM responses when given: verbose human docs, DocLean standard, DocLean lean.
Uses --dry-run to show token counts and what would be compared without an LLM call.

Usage:
    python agent_test.py --all --dry-run
    python agent_test.py --spec examples/stripe-charges.yaml --task "Create a charge for $10"
    python agent_test.py --all --api-key sk-... --model gpt-4o
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from core.compilers.openapi import compile_openapi
from core.utils import count_tokens

SYSTEM_PROMPT = "You are an API integration assistant. Given the API documentation below, write a curl command to accomplish the task. Output ONLY the curl command, nothing else."


def build_prompt(docs: str, task: str) -> str:
    return f"{SYSTEM_PROMPT}\n\n--- API DOCUMENTATION ---\n{docs}\n--- END DOCUMENTATION ---\n\nTask: {task}"


def call_llm(prompt: str, api_key: str, model: str) -> str:
    """Call OpenAI-compatible API. Returns response text."""
    import urllib.request
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 512,
    })
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body.encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


def extract_curl_parts(curl_str: str) -> dict:
    """Extract endpoint, method, and key params from a curl command."""
    parts = {"method": "GET", "url": "", "headers": [], "data_keys": []}
    # Method
    m = re.search(r'-X\s+(\w+)', curl_str)
    if m:
        parts["method"] = m.group(1).upper()
    elif re.search(r'-d\s|--data', curl_str):
        parts["method"] = "POST"
    # URL
    urls = re.findall(r'https?://[^\s\'"\\]+', curl_str)
    if urls:
        parts["url"] = urls[0].rstrip("'\"\\")
    # Data keys
    data_matches = re.findall(r'-d\s+[\'"]?([^"\']+)', curl_str)
    for d in data_matches:
        keys = re.findall(r'[\w]+(?==)', d)
        parts["data_keys"].extend(keys)
    # JSON body keys
    json_match = re.search(r'\{[^}]+\}', curl_str)
    if json_match:
        try:
            obj = json.loads(json_match.group())
            parts["data_keys"].extend(obj.keys())
        except (json.JSONDecodeError, AttributeError):
            pass
    return parts


def check_equivalence(a: dict, b: dict) -> tuple[bool, list[str]]:
    """Check if two curl extractions are functionally equivalent."""
    diffs = []
    if a["method"] != b["method"]:
        diffs.append(f"method: {a['method']} vs {b['method']}")
    # Compare URL path (ignore host differences)
    path_a = re.sub(r'https?://[^/]+', '', a["url"])
    path_b = re.sub(r'https?://[^/]+', '', b["url"])
    if path_a != path_b:
        diffs.append(f"path: {path_a} vs {path_b}")
    keys_a = set(a["data_keys"])
    keys_b = set(b["data_keys"])
    if keys_a != keys_b:
        diffs.append(f"params: {keys_a} vs {keys_b}")
    return len(diffs) == 0, diffs


def run_single_test(spec_path: str, task: str, api_key: str = None, model: str = "gpt-4o",
                    dry_run: bool = True, expect_endpoint: str = None, expect_params: list = None) -> dict:
    """Run a single agent validation test."""
    spec = compile_openapi(spec_path)
    verbose = spec.to_original_text()
    doclean_std = spec.to_doclean(lean=False)
    doclean_lean = spec.to_doclean(lean=True)

    prompt_verbose = build_prompt(verbose, task)
    prompt_std = build_prompt(doclean_std, task)
    prompt_lean = build_prompt(doclean_lean, task)

    tokens = {
        "verbose": count_tokens(prompt_verbose),
        "doclean": count_tokens(prompt_std),
        "lean": count_tokens(prompt_lean),
    }
    tokens["reduction_std"] = f"{(1 - tokens['doclean'] / tokens['verbose']) * 100:.1f}%"
    tokens["reduction_lean"] = f"{(1 - tokens['lean'] / tokens['verbose']) * 100:.1f}%"

    result = {
        "spec": spec_path,
        "task": task,
        "tokens": tokens,
        "dry_run": dry_run,
        "expect_endpoint": expect_endpoint,
        "expect_params": expect_params,
    }

    if dry_run:
        result["status"] = "dry-run"
        result["responses"] = None
        return result

    # Live LLM calls
    responses = {}
    for label, prompt in [("verbose", prompt_verbose), ("doclean", prompt_std), ("lean", prompt_lean)]:
        responses[label] = call_llm(prompt, api_key, model)

    curls = {k: extract_curl_parts(v) for k, v in responses.items()}

    eq_std, diffs_std = check_equivalence(curls["verbose"], curls["doclean"])
    eq_lean, diffs_lean = check_equivalence(curls["verbose"], curls["lean"])

    result["responses"] = responses
    result["equivalence"] = {
        "verbose_vs_doclean": {"match": eq_std, "diffs": diffs_std},
        "verbose_vs_lean": {"match": eq_lean, "diffs": diffs_lean},
    }
    result["status"] = "pass" if (eq_std and eq_lean) else "partial"
    return result


def run_all(tasks_file: str, **kwargs) -> list[dict]:
    tasks = yaml.safe_load(Path(tasks_file).read_text())["tasks"]
    results = []
    for t in tasks:
        print(f"  [{t['api']}] {t['task'][:60]}...", end=" ", flush=True)
        r = run_single_test(t["spec"], t["task"], expect_endpoint=t.get("expect_endpoint"),
                            expect_params=t.get("expect_params"), **kwargs)
        print(f"✓ ({r['tokens']['verbose']}→{r['tokens']['doclean']}→{r['tokens']['lean']} tokens)")
        results.append(r)
    return results


def print_summary(results: list[dict]):
    print("\n" + "=" * 70)
    print("📊 Agent Validation Test Summary")
    print("=" * 70)
    print(f"\n{'Task':<55} {'Verbose':>7} {'DocLean':>7} {'Lean':>6} {'Saved':>6}")
    print("-" * 85)
    total = {"verbose": 0, "doclean": 0, "lean": 0}
    for r in results:
        t = r["tokens"]
        total["verbose"] += t["verbose"]
        total["doclean"] += t["doclean"]
        total["lean"] += t["lean"]
        task_short = r["task"][:53]
        print(f"{task_short:<55} {t['verbose']:>7} {t['doclean']:>7} {t['lean']:>6} {t['reduction_lean']:>6}")

    print("-" * 85)
    overall_red = f"{(1 - total['lean'] / total['verbose']) * 100:.1f}%"
    print(f"{'TOTAL':<55} {total['verbose']:>7} {total['doclean']:>7} {total['lean']:>6} {overall_red:>6}")

    if results[0].get("equivalence"):
        matches = sum(1 for r in results if r.get("equivalence", {}).get("verbose_vs_lean", {}).get("match"))
        print(f"\n✅ Functional equivalence (lean): {matches}/{len(results)} tasks match")


def save_results(results: list[dict], output: str):
    Path(output).write_text(json.dumps(results, indent=2, default=str))
    print(f"\n💾 Results saved to {output}")


def main():
    parser = argparse.ArgumentParser(description="LAP Agent Validation Test")
    parser.add_argument("--spec", help="Single spec file to test")
    parser.add_argument("--task", help="Task description")
    parser.add_argument("--all", action="store_true", help="Run all tasks from test_tasks.yaml")
    parser.add_argument("--tasks-file", default=str(Path(__file__).parent / "test_tasks.yaml"))
    parser.add_argument("--dry-run", action="store_true", help="Show token counts without calling LLM")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--output", default=str(Path(__file__).parent.parent / "output" / "agent_results.json"))
    args = parser.parse_args()

    import os
    api_key = os.environ.get("OPENAI_API_KEY")
    dry_run = args.dry_run or (not api_key)
    if dry_run and not args.dry_run:
        print("⚠️  OPENAI_API_KEY not set, running in dry-run mode\n")

    if args.all:
        print("🧪 Running all agent validation tests...\n")
        results = run_all(args.tasks_file, api_key=api_key, model=args.model, dry_run=dry_run)
    elif args.spec and args.task:
        results = [run_single_test(args.spec, args.task, api_key=api_key, model=args.model, dry_run=dry_run)]
    else:
        parser.error("Provide --all or both --spec and --task")

    print_summary(results)
    save_results(results, args.output)


if __name__ == "__main__":
    main()
