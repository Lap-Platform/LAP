#!/usr/bin/env python3
"""
Full Multi-Protocol Agent Benchmark for LAP

Comprehensive benchmark comparing LLM agent performance with verbose docs vs. DocLean.
Tests OpenAPI, GraphQL, AsyncAPI, Postman, and Protobuf protocols.

Usage:
    python full_agent_benchmark.py --dry-run
    python full_agent_benchmark.py --protocol openapi --limit 5
    python full_agent_benchmark.py --all --api-key sk-...
    python full_agent_benchmark.py --anthropic --api-key sk-ant-...
    python full_agent_benchmark.py --protocol graphql --model gpt-4o
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add src to path

# Import compilers based on availability
try:
    from core.compilers.openapi import compile_openapi
except ImportError:
    compile_openapi = None

try:
    from core.compilers.graphql import compile_graphql
except ImportError:
    compile_graphql = None

try:
    from core.compilers.asyncapi import compile_asyncapi
except ImportError:
    compile_asyncapi = None

try:
    from core.compilers.postman import compile_postman
except ImportError:
    compile_postman = None

try:
    from core.compilers.protobuf import compile_protobuf
except ImportError:
    compile_protobuf = None

from core.utils import count_tokens


SYSTEM_PROMPT_TEMPLATES = {
    "openapi": "You are an API integration assistant. Given the API documentation below, write the exact curl command to accomplish the task. Output ONLY the curl command, nothing else.",
    "graphql": "You are a GraphQL API assistant. Given the GraphQL schema below, write the exact GraphQL query or mutation to accomplish the task. Output ONLY the GraphQL operation, nothing else.",
    "asyncapi": "You are an async messaging assistant. Given the AsyncAPI documentation below, write the exact subscription/publish command to accomplish the task. Output ONLY the command, nothing else.",
    "postman": "You are an API integration assistant. Given the API documentation below, write the exact HTTP request (curl format) to accomplish the task. Output ONLY the curl command, nothing else.",
    "protobuf": "You are a gRPC API assistant. Given the Protocol Buffer service definition below, write the exact gRPC call command to accomplish the task. Output ONLY the gRPC call, nothing else.",
}


def build_prompt(protocol: str, docs: str, task: str) -> str:
    """Build prompt for LLM with system message, docs, and task."""
    system_prompt = SYSTEM_PROMPT_TEMPLATES.get(protocol, SYSTEM_PROMPT_TEMPLATES["openapi"])
    return f"{system_prompt}\n\n--- API DOCUMENTATION ---\n{docs}\n--- END DOCUMENTATION ---\n\nTask: {task}"


def call_openai_llm(prompt: str, api_key: str, model: str = "gpt-4o") -> Tuple[str, int, int, float]:
    """Call OpenAI-compatible API. Returns (response, input_tokens, output_tokens, response_time)."""
    start = time.time()
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 1024,
    })
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body.encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        elapsed = time.time() - start
        
        response = data["choices"][0]["message"]["content"].strip()
        input_tokens = data.get("usage", {}).get("prompt_tokens", count_tokens(prompt))
        output_tokens = data.get("usage", {}).get("completion_tokens", count_tokens(response))
        
        return response, input_tokens, output_tokens, elapsed
    except Exception as e:
        print(f"\n⚠️  API call failed: {e}")
        return "", 0, 0, 0.0


def call_anthropic_llm(prompt: str, api_key: str, model: str = "claude-3-5-sonnet-20241022") -> Tuple[str, int, int, float]:
    """Call Anthropic API. Returns (response, input_tokens, output_tokens, response_time)."""
    start = time.time()
    body = json.dumps({
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    })
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body.encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        elapsed = time.time() - start
        
        response = data["content"][0]["text"].strip()
        input_tokens = data.get("usage", {}).get("input_tokens", count_tokens(prompt))
        output_tokens = data.get("usage", {}).get("output_tokens", count_tokens(response))
        
        return response, input_tokens, output_tokens, elapsed
    except Exception as e:
        print(f"\n⚠️  API call failed: {e}")
        return "", 0, 0, 0.0


def extract_api_call_features(response: str, protocol: str) -> Dict[str, Any]:
    """Extract key features from API call response for comparison."""
    features = {"raw": response, "method": "", "endpoint": "", "params": []}
    
    if protocol == "openapi" or protocol == "postman":
        # Extract from curl
        m = re.search(r'-X\s+(\w+)', response)
        if m:
            features["method"] = m.group(1).upper()
        elif re.search(r'-d\s|--data', response):
            features["method"] = "POST"
        else:
            features["method"] = "GET"
        
        # Extract URL/endpoint
        urls = re.findall(r'https?://[^\s\'"\\]+|(?:GET|POST|PUT|PATCH|DELETE)\s+(/[^\s\'"\\]*)', response)
        if urls:
            url = urls[0]
            # Strip protocol and domain, keep path
            path = re.sub(r'https?://[^/]+', '', url)
            features["endpoint"] = path.rstrip("'\"\\")
        
        # Extract params from data
        data_matches = re.findall(r'-d\s+[\'"]?([^"\']+)', response)
        for d in data_matches:
            keys = re.findall(r'[\w]+(?==)', d)
            features["params"].extend(keys)
        
        # Extract from JSON body
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            try:
                obj = json.loads(json_match.group())
                features["params"].extend(list(obj.keys()))
            except:
                pass
    
    elif protocol == "graphql":
        # Extract operation type and fields
        if "mutation" in response.lower():
            features["method"] = "mutation"
        else:
            features["method"] = "query"
        
        # Extract main operation name
        op_match = re.search(r'(query|mutation)\s*\{?\s*(\w+)', response, re.IGNORECASE)
        if op_match:
            features["endpoint"] = op_match.group(2)
        
        # Extract field names in parentheses (parameters)
        params = re.findall(r'(\w+):', response)
        features["params"] = params
    
    elif protocol == "asyncapi":
        # Extract operation (subscribe/publish)
        if "subscribe" in response.lower():
            features["method"] = "subscribe"
        elif "publish" in response.lower():
            features["method"] = "publish"
        else:
            features["method"] = "message"
        
        # Extract topic/channel
        topic_match = re.search(r'(?:subscribe|publish|to|topic)\s+["\']?([^\s"\']+)', response, re.IGNORECASE)
        if topic_match:
            features["endpoint"] = topic_match.group(1)
    
    elif protocol == "protobuf":
        # Extract RPC method
        rpc_match = re.search(r'(?:rpc|call)\s+(\w+)', response, re.IGNORECASE)
        if rpc_match:
            features["endpoint"] = rpc_match.group(1)
            features["method"] = "rpc"
        
        # Extract parameter names
        params = re.findall(r'(\w+):', response)
        features["params"] = params
    
    return features


def check_task_correctness(features: Dict[str, Any], expect_endpoint: Optional[str], 
                           expect_params: Optional[List[str]]) -> Tuple[bool, List[str]]:
    """Check if extracted features match expected endpoint and parameters."""
    issues = []
    
    if expect_endpoint:
        endpoint = features.get("endpoint", "")
        # Flexible matching - allow partial matches for path params
        if expect_endpoint.lower() not in endpoint.lower() and endpoint.lower() not in expect_endpoint.lower():
            issues.append(f"endpoint mismatch: expected '{expect_endpoint}', got '{endpoint}'")
    
    if expect_params:
        actual_params = set(p.lower() for p in features.get("params", []))
        expected_params = set(p.lower() for p in expect_params)
        missing = expected_params - actual_params
        if missing:
            issues.append(f"missing params: {missing}")
    
    return len(issues) == 0, issues


def compile_spec(protocol: str, spec_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Compile spec to verbose (raw original file) and lean versions. Returns (verbose, lean)."""
    try:
        # Read the raw original file as the verbose baseline
        from pathlib import Path
        verbose = Path(spec_path).read_text()
        
        compiler_map = {
            "openapi": compile_openapi,
            "graphql": compile_graphql,
            "asyncapi": compile_asyncapi,
            "postman": compile_postman,
            "protobuf": compile_protobuf,
        }
        compiler = compiler_map.get(protocol)
        if not compiler:
            return None, None
        
        spec = compiler(spec_path)
        lean = spec.to_doclean(lean=True)
        return verbose, lean
    except Exception as e:
        print(f"\n⚠️  Failed to compile {spec_path}: {e}")
        return None, None


def run_task_benchmark(
    protocol: str,
    spec_path: str,
    task: str,
    expect_endpoint: Optional[str],
    expect_params: Optional[List[str]],
    api_key: Optional[str],
    model: str,
    use_anthropic: bool,
    dry_run: bool
) -> Dict[str, Any]:
    """Run benchmark for a single task."""
    
    # Compile spec
    verbose, lean = compile_spec(protocol, spec_path)
    if verbose is None or lean is None:
        return {
            "protocol": protocol,
            "spec": spec_path,
            "task": task,
            "status": "compilation_failed",
            "error": "Could not compile spec"
        }
    
    # Build prompts
    prompt_verbose = build_prompt(protocol, verbose, task)
    prompt_lean = build_prompt(protocol, lean, task)
    
    # Token counts
    tokens = {
        "verbose_input": count_tokens(prompt_verbose),
        "lean_input": count_tokens(prompt_lean),
    }
    tokens["reduction_pct"] = round((1 - tokens["lean_input"] / tokens["verbose_input"]) * 100, 1)
    
    result = {
        "protocol": protocol,
        "spec": spec_path,
        "task": task,
        "expect_endpoint": expect_endpoint,
        "expect_params": expect_params,
        "tokens": tokens,
        "dry_run": dry_run,
    }
    
    if dry_run:
        result["status"] = "dry-run"
        return result
    
    # Make LLM calls
    llm_call = call_anthropic_llm if use_anthropic else call_openai_llm
    
    # Verbose version
    resp_verbose, in_tok_v, out_tok_v, time_v = llm_call(prompt_verbose, api_key, model)
    tokens["verbose_output"] = out_tok_v
    tokens["verbose_total"] = in_tok_v + out_tok_v
    
    # Lean version
    resp_lean, in_tok_l, out_tok_l, time_l = llm_call(prompt_lean, api_key, model)
    tokens["lean_output"] = out_tok_l
    tokens["lean_total"] = in_tok_l + out_tok_l
    
    # Extract features
    features_verbose = extract_api_call_features(resp_verbose, protocol)
    features_lean = extract_api_call_features(resp_lean, protocol)
    
    # Check correctness
    correct_verbose, issues_verbose = check_task_correctness(features_verbose, expect_endpoint, expect_params)
    correct_lean, issues_lean = check_task_correctness(features_lean, expect_endpoint, expect_params)
    
    result.update({
        "status": "completed",
        "responses": {
            "verbose": resp_verbose,
            "lean": resp_lean,
        },
        "features": {
            "verbose": features_verbose,
            "lean": features_lean,
        },
        "correctness": {
            "verbose": correct_verbose,
            "lean": correct_lean,
            "verbose_issues": issues_verbose,
            "lean_issues": issues_lean,
        },
        "timing": {
            "verbose_seconds": round(time_v, 2),
            "lean_seconds": round(time_l, 2),
        },
    })
    
    return result


def load_tasks(tasks_file: str, protocol_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
    """Load tasks from YAML file with optional filtering."""
    with open(tasks_file, 'r') as f:
        data = yaml.safe_load(f)
    
    all_tasks = []
    protocols = data.get("protocols", {})
    
    for protocol, proto_data in protocols.items():
        if protocol_filter and protocol != protocol_filter:
            continue
        
        docs = proto_data.get("docs", [])
        for doc in docs:
            spec = doc.get("spec")
            api = doc.get("api")
            tasks = doc.get("tasks", [])
            
            for task_data in tasks:
                all_tasks.append({
                    "protocol": protocol,
                    "spec": spec,
                    "api": api,
                    "task": task_data.get("task"),
                    "expect_endpoint": task_data.get("expect_endpoint"),
                    "expect_params": task_data.get("expect_params"),
                })
                
                if limit and len(all_tasks) >= limit:
                    return all_tasks
    
    return all_tasks


def print_progress(current: int, total: int, result: Dict):
    """Print progress during benchmark run."""
    protocol = result["protocol"]
    api = result.get("api", "Unknown")
    task_short = result["task"][:50]
    
    # Handle compilation failures
    if result.get("status") == "compilation_failed":
        print(f"  [{current}/{total}] ✗ {protocol:10} {api:25} {task_short:50} | COMPILATION FAILED")
        return
    
    if result.get("dry_run"):
        tokens = result.get("tokens", {})
        reduction = tokens.get("reduction_pct", 0)
        print(f"  [{current}/{total}] {protocol:10} {api:25} {task_short:50} | "
              f"{tokens.get('verbose_input', 0):6} → {tokens.get('lean_input', 0):6} tokens ({reduction:5.1f}% reduction)")
    else:
        status = "✓" if result.get("status") == "completed" else "✗"
        correct = result.get("correctness", {})
        v_ok = "✓" if correct.get("verbose") else "✗"
        l_ok = "✓" if correct.get("lean") else "✗"
        tokens = result.get("tokens", {})
        print(f"  [{current}/{total}] {status} {protocol:10} {api:20} | "
              f"Verbose: {v_ok} Lean: {l_ok} | "
              f"{tokens.get('verbose_total', 0):5} → {tokens.get('lean_total', 0):5} tokens")


def generate_markdown_summary(results: List[Dict], output_path: str):
    """Generate markdown summary report."""
    
    # Aggregate by protocol
    by_protocol = defaultdict(list)
    for r in results:
        by_protocol[r["protocol"]].append(r)
    
    total_verbose_tokens = sum(r.get("tokens", {}).get("verbose_total", 0) for r in results if not r.get("dry_run"))
    total_lean_tokens = sum(r.get("tokens", {}).get("lean_total", 0) for r in results if not r.get("dry_run"))
    
    md = []
    md.append("# Full Multi-Protocol Agent Benchmark Results\n")
    md.append(f"**Total Tasks:** {len(results)}\n")
    
    if results and not results[0].get("dry_run"):
        total_correct_verbose = sum(1 for r in results if r.get("correctness", {}).get("verbose"))
        total_correct_lean = sum(1 for r in results if r.get("correctness", {}).get("lean"))
        
        md.append(f"**Verbose Correctness:** {total_correct_verbose}/{len(results)} ({total_correct_verbose/len(results)*100:.1f}%)\n")
        md.append(f"**Lean Correctness:** {total_correct_lean}/{len(results)} ({total_correct_lean/len(results)*100:.1f}%)\n")
        md.append(f"**Total Tokens (Verbose):** {total_verbose_tokens:,}\n")
        md.append(f"**Total Tokens (Lean):** {total_lean_tokens:,}\n")
        
        if total_verbose_tokens > 0:
            reduction = (1 - total_lean_tokens / total_verbose_tokens) * 100
            md.append(f"**Overall Token Reduction:** {reduction:.1f}%\n")
    
    md.append("\n## By Protocol\n")
    
    for protocol, proto_results in sorted(by_protocol.items()):
        md.append(f"\n### {protocol.upper()}\n")
        
        # Filter out failed compilations
        successful = [r for r in proto_results if r.get("status") != "compilation_failed"]
        failed = len(proto_results) - len(successful)
        
        if successful and not successful[0].get("dry_run"):
            correct_v = sum(1 for r in successful if r.get("correctness", {}).get("verbose"))
            correct_l = sum(1 for r in successful if r.get("correctness", {}).get("lean"))
            tokens_v = sum(r.get("tokens", {}).get("verbose_total", 0) for r in successful)
            tokens_l = sum(r.get("tokens", {}).get("lean_total", 0) for r in successful)
            
            md.append(f"- **Tasks:** {len(proto_results)} ({failed} failed)\n" if failed else f"- **Tasks:** {len(proto_results)}\n")
            md.append(f"- **Verbose Correctness:** {correct_v}/{len(successful)}\n")
            md.append(f"- **Lean Correctness:** {correct_l}/{len(successful)}\n")
            if tokens_v > 0:
                md.append(f"- **Token Reduction:** {tokens_v:,} → {tokens_l:,} ({(1-tokens_l/tokens_v)*100:.1f}%)\n")
        elif successful:
            avg_reduction = sum(r.get("tokens", {}).get("reduction_pct", 0) for r in successful) / len(successful) if successful else 0
            md.append(f"- **Tasks:** {len(proto_results)} ({failed} failed)\n" if failed else f"- **Tasks:** {len(proto_results)}\n")
            md.append(f"- **Avg Token Reduction:** {avg_reduction:.1f}%\n")
        else:
            md.append(f"- **Tasks:** {len(proto_results)} (all failed compilation)\n")
    
    # Write markdown
    md_path = output_path.replace(".json", ".md")
    Path(md_path).write_text("\n".join(md))
    print(f"\n📄 Markdown summary: {md_path}")


def main():
    parser = argparse.ArgumentParser(description="Full Multi-Protocol Agent Benchmark for LAP")
    parser.add_argument("--tasks-file", default=str(Path(__file__).parent / "full_test_tasks.yaml"),
                       help="Path to tasks YAML file")
    parser.add_argument("--protocol", choices=["openapi", "graphql", "asyncapi", "postman", "protobuf"],
                       help="Filter to specific protocol")
    parser.add_argument("--limit", type=int, help="Limit number of tasks to run")
    parser.add_argument("--dry-run", action="store_true", help="Show token counts without calling LLM")
    parser.add_argument("--anthropic", action="store_true", help="Use Anthropic API instead of OpenAI")
    parser.add_argument("--model", help="Model name (default: gpt-4o for OpenAI, claude-3-5-sonnet for Anthropic)")
    parser.add_argument("--api-key", help="API key (or set OPENAI_API_KEY / ANTHROPIC_API_KEY env var)")
    parser.add_argument("--output", default=str(Path(__file__).parent / "results" / "full_benchmark_report.json"),
                       help="Output JSON report path")
    
    args = parser.parse_args()
    
    # Determine API key
    api_key = args.api_key
    if not api_key:
        if args.anthropic:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        else:
            api_key = os.environ.get("OPENAI_API_KEY")
    
    dry_run = args.dry_run or (not api_key)
    if dry_run and not args.dry_run:
        print("⚠️  No API key provided, running in dry-run mode\n")
    
    # Determine model
    model = args.model
    if not model:
        model = "claude-3-5-sonnet-20241022" if args.anthropic else "gpt-4o"
    
    # Load tasks
    print(f"📋 Loading tasks from {args.tasks_file}...")
    tasks = load_tasks(args.tasks_file, args.protocol, args.limit)
    print(f"✓ Loaded {len(tasks)} tasks\n")
    
    if not tasks:
        print("No tasks to run!")
        return
    
    # Run benchmarks
    print(f"🧪 Running {'dry-run' if dry_run else 'live'} benchmark...\n")
    results = []
    
    for i, task_config in enumerate(tasks, 1):
        result = run_task_benchmark(
            protocol=task_config["protocol"],
            spec_path=task_config["spec"],
            task=task_config["task"],
            expect_endpoint=task_config.get("expect_endpoint"),
            expect_params=task_config.get("expect_params"),
            api_key=api_key,
            model=model,
            use_anthropic=args.anthropic,
            dry_run=dry_run
        )
        result["api"] = task_config.get("api", "Unknown")
        results.append(result)
        print_progress(i, len(tasks), result)
    
    # Save results
    os.makedirs(Path(args.output).parent, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Results saved to {args.output}")
    
    # Generate markdown summary
    generate_markdown_summary(results, args.output)
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 BENCHMARK SUMMARY")
    print("=" * 80)
    
    if not dry_run:
        total_correct_v = sum(1 for r in results if r.get("correctness", {}).get("verbose"))
        total_correct_l = sum(1 for r in results if r.get("correctness", {}).get("lean"))
        total_tokens_v = sum(r.get("tokens", {}).get("verbose_total", 0) for r in results)
        total_tokens_l = sum(r.get("tokens", {}).get("lean_total", 0) for r in results)
        
        print(f"\nTotal Tasks: {len(results)}")
        print(f"Verbose Correctness: {total_correct_v}/{len(results)} ({total_correct_v/len(results)*100:.1f}%)")
        print(f"Lean Correctness: {total_correct_l}/{len(results)} ({total_correct_l/len(results)*100:.1f}%)")
        print(f"\nTotal Tokens (Verbose): {total_tokens_v:,}")
        print(f"Total Tokens (Lean): {total_tokens_l:,}")
        
        if total_tokens_v > 0:
            reduction = (1 - total_tokens_l / total_tokens_v) * 100
            print(f"Overall Reduction: {reduction:.1f}%")
    else:
        avg_reduction = sum(r.get("tokens", {}).get("reduction_pct", 0) for r in results) / len(results)
        print(f"\nTotal Tasks: {len(results)}")
        print(f"Average Token Reduction: {avg_reduction:.1f}%")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
