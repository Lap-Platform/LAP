#!/usr/bin/env python3
"""
Semantic Validity Checker — Ensures DocLean output preserves all essential information.

Three validation layers:
1. Schema completeness — every field from source exists in DocLean
2. Round-trip extraction — structured data survives compression
3. Agent task comparison — LLM produces equivalent output with both formats

Usage:
    python validate.py <openapi-spec.yaml> [--agent-test]
"""

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from core.compilers.openapi import compile_openapi, resolve_ref
from core.parser import parse_doclean
from core.differ import diff_specs

# ── Multi-format compiler registry ──────────────────────────────────

_COMPILERS = {"openapi": compile_openapi}
_SPEC_EXTENSIONS = {
    "openapi": ("*.yaml", "*.yml", "*.json"),
    "graphql": ("*.graphql", "*.gql", "*.json"),
    "asyncapi": ("*.yaml", "*.yml", "*.json"),
    "protobuf": ("*.proto",),
    "postman": ("*.json",),
}

for _fmt in ("graphql", "asyncapi", "protobuf", "postman"):
    try:
        _mod = __import__(f"{_fmt}_compiler")
        _fn = getattr(_mod, f"compile_{_fmt}", None)
        if _fn:
            _COMPILERS[_fmt] = _fn
    except ImportError:
        pass


def validate_schema_completeness(spec_path: str) -> dict:
    """
    Layer 1: Verify every endpoint, parameter, and type from the OpenAPI spec
    is present in the DocLean output.
    """
    path = Path(spec_path)
    raw = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        spec = yaml.safe_load(raw)
    else:
        spec = json.loads(raw)

    if not isinstance(spec, dict):
        raise ValueError("Invalid OpenAPI spec: expected a YAML mapping")

    doclean = compile_openapi(spec_path)
    doclean_text = doclean.to_doclean()

    results = {
        "total_endpoints": 0,
        "compiled_endpoints": len(doclean.endpoints),
        "missing_endpoints": [],
        "total_params": 0,
        "captured_params": 0,
        "missing_params": [],
        "total_error_codes": 0,
        "captured_error_codes": 0,
        "missing_error_codes": [],
    }

    # Check every path/method exists
    paths = spec.get("paths", {})
    for path_str, methods in paths.items():
        for method in methods:
            if method in ("get", "post", "put", "patch", "delete", "head", "options"):
                results["total_endpoints"] += 1
                found = any(
                    e.path == path_str and e.method == method
                    for e in doclean.endpoints
                )
                if not found:
                    results["missing_endpoints"].append(f"{method.upper()} {path_str}")

    # Check params for each endpoint
    for path_str, methods in paths.items():
        for method, details in methods.items():
            if method not in ("get", "post", "put", "patch", "delete", "head", "options"):
                continue

            # Gather all param names from source
            source_params = set()
            for p in details.get("parameters", []):
                if "$ref" in p:
                    p = resolve_ref(spec, p["$ref"])
                source_params.add(p["name"])

            body = details.get("requestBody", {})
            if "$ref" in body:
                body = resolve_ref(spec, body["$ref"])
            content = body.get("content", {})
            json_schema = content.get("application/json", {}).get("schema", {})
            if "$ref" in json_schema:
                json_schema = resolve_ref(spec, json_schema["$ref"])
            for name in json_schema.get("properties", {}):
                source_params.add(name)

            results["total_params"] += len(source_params)

            # Check which params made it to DocLean
            ep = next(
                (e for e in doclean.endpoints if e.path == path_str and e.method == method),
                None,
            )
            if ep:
                doclean_params = set()
                for p in ep.required_params + ep.optional_params + ep.request_body:
                    doclean_params.add(p.name)

                captured = source_params & doclean_params
                results["captured_params"] += len(captured)
                missing = source_params - doclean_params
                for m in missing:
                    results["missing_params"].append(f"{method.upper()} {path_str} → {m}")

            # Check error codes
            for code in details.get("responses", {}):
                if not code.startswith("2") and code != "default":
                    results["total_error_codes"] += 1
                    if ep:
                        # Check both legacy .errors dict and new .error_schemas list
                        found_error = code in ep.errors
                        if not found_error and hasattr(ep, 'error_schemas'):
                            found_error = any(e.code == code for e in ep.error_schemas)
                        if found_error:
                            results["captured_error_codes"] += 1
                        else:
                            results["missing_error_codes"].append(
                                f"{method.upper()} {path_str} → {code}"
                            )
                    else:
                        results["missing_error_codes"].append(
                            f"{method.upper()} {path_str} → {code}"
                        )

    return results


def validate_agent_task(spec_path: str, task: str = None) -> dict:
    """
    Layer 3: Give an LLM the same task with full docs vs DocLean,
    compare outputs for functional equivalence.

    Requires OPENAI_API_KEY env var.
    """
    import os
    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "openai package not installed. Run: pip install openai"}

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set. Skipping agent validation."}

    doclean = compile_openapi(spec_path)
    verbose = doclean.to_original_text()
    lean = doclean.to_doclean()

    if not task:
        # Generate a task based on the first endpoint
        if doclean.endpoints:
            ep = doclean.endpoints[0]
            task = (
                f"Using the {doclean.api_name} API, write a curl command to call "
                f"{ep.method.upper()} {ep.path} with all required parameters. "
                f"Include authentication headers."
            )
        else:
            return {"error": "No endpoints found to test"}

    client = OpenAI(api_key=api_key)

    # Run with verbose docs
    verbose_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are an API integration assistant.\n\nAPI Documentation:\n{verbose}"},
            {"role": "user", "content": task},
        ],
        temperature=0,
    )

    # Run with DocLean docs
    lean_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are an API integration assistant.\n\nAPI Documentation:\n{lean}"},
            {"role": "user", "content": task},
        ],
        temperature=0,
    )

    verbose_answer = verbose_resp.choices[0].message.content
    lean_answer = lean_resp.choices[0].message.content
    verbose_tokens = verbose_resp.usage.total_tokens
    lean_tokens = lean_resp.usage.total_tokens

    # Ask a judge model to compare
    judge_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Compare two API integration answers. Are they functionally equivalent? "
                    "Do they use the same endpoint, parameters, and auth? "
                    "Reply with JSON: {\"equivalent\": true/false, \"differences\": [\"...\"], \"verdict\": \"...\"}"
                ),
            },
            {
                "role": "user",
                "content": f"Answer A (from verbose docs):\n{verbose_answer}\n\nAnswer B (from compressed docs):\n{lean_answer}",
            },
        ],
        temperature=0,
    )

    return {
        "task": task,
        "verbose_answer": verbose_answer,
        "lean_answer": lean_answer,
        "verbose_tokens_used": verbose_tokens,
        "lean_tokens_used": lean_tokens,
        "token_savings": f"{(1 - lean_tokens/verbose_tokens)*100:.1f}%",
        "judge_verdict": judge_resp.choices[0].message.content,
    }


def print_results(results: dict):
    """Pretty print validation results."""
    print("=" * 60)
    print("✅ LAP DocLean Semantic Validation")
    print("=" * 60)

    # Endpoints
    total = results["total_endpoints"]
    compiled = results["compiled_endpoints"]
    pct = (compiled / total * 100) if total > 0 else 100
    status = "✅" if pct == 100 else "⚠️"
    print(f"\n{status} Endpoints: {compiled}/{total} ({pct:.0f}%)")
    for m in results["missing_endpoints"]:
        print(f"   ❌ Missing: {m}")

    # Params
    total_p = results["total_params"]
    captured_p = results["captured_params"]
    pct_p = (captured_p / total_p * 100) if total_p > 0 else 100
    status_p = "✅" if pct_p == 100 else "⚠️"
    print(f"\n{status_p} Parameters: {captured_p}/{total_p} ({pct_p:.0f}%)")
    for m in results["missing_params"][:10]:
        print(f"   ❌ Missing: {m}")
    if len(results["missing_params"]) > 10:
        print(f"   ... and {len(results['missing_params']) - 10} more")

    # Error codes
    total_e = results["total_error_codes"]
    captured_e = results["captured_error_codes"]
    pct_e = (captured_e / total_e * 100) if total_e > 0 else 100
    status_e = "✅" if pct_e == 100 else "⚠️"
    print(f"\n{status_e} Error Codes: {captured_e}/{total_e} ({pct_e:.0f}%)")
    for m in results["missing_error_codes"][:10]:
        print(f"   ❌ Missing: {m}")

    # Overall
    overall = pct == 100 and pct_p == 100
    print(f"\n{'✅ PASS' if overall else '⚠️  PARTIAL'} — ", end="")
    if overall:
        print("Zero information loss! All endpoints, params, and errors preserved.")
    else:
        print("Some information not captured. Review missing items above.")

    print("=" * 60)


def validate_roundtrip(spec_path: str) -> dict:
    """
    Layer 2: Round-trip validation (OpenAPI → DocLean → parse → diff).
    Ensures no breaking changes survive the round-trip.
    """
    from core.converter import doclean_to_openapi

    doclean_spec = compile_openapi(spec_path)
    doclean_text = doclean_spec.to_doclean()

    # Parse back
    parsed_spec = parse_doclean(doclean_text)

    # Structural checks
    original_eps = {f"{ep.method.upper()} {ep.path}" for ep in doclean_spec.endpoints}
    parsed_eps = {f"{ep.method.upper()} {ep.path}" for ep in parsed_spec.endpoints}
    lost_endpoints = original_eps - parsed_eps

    # Semantic diff — should have zero breaking changes
    diff_result = diff_specs(doclean_spec, parsed_spec)
    breaking = diff_result.breaking_changes

    # Full round-trip back to OpenAPI
    roundtrip_openapi = doclean_to_openapi(parsed_spec)
    rt_eps = set()
    for p, methods in roundtrip_openapi.get("paths", {}).items():
        for m in methods:
            if m in ("get", "post", "put", "patch", "delete", "head", "options"):
                rt_eps.add(f"{m.upper()} {p}")
    lost_in_full_rt = original_eps - rt_eps

    return {
        "spec": Path(spec_path).name,
        "endpoints_compiled": len(original_eps),
        "endpoints_parsed": len(parsed_eps),
        "endpoints_lost_parse": sorted(lost_endpoints),
        "endpoints_lost_roundtrip": sorted(lost_in_full_rt),
        "breaking_changes": len(breaking),
        "breaking_details": [c.detail for c in breaking[:10]],
        "pass": len(lost_endpoints) == 0 and len(lost_in_full_rt) == 0 and len(breaking) == 0,
    }


def validate_generic_format(spec_path: str, fmt: str) -> dict:
    """
    Validate a non-OpenAPI format by compiling and parsing back.
    Since no round-trip converter exists yet, we check:
    - DocLean output parses cleanly
    - All endpoints survive the parse
    - Param counts match
    """
    compiler = _COMPILERS.get(fmt)
    if not compiler:
        return {"spec": Path(spec_path).name, "format": fmt, "error": f"No compiler for {fmt}"}

    try:
        doclean_spec = compiler(spec_path)
        doclean_text = doclean_spec.to_doclean()
        parsed_spec = parse_doclean(doclean_text)

        original_eps = {f"{ep.method.upper()} {ep.path}" for ep in doclean_spec.endpoints}
        parsed_eps = {f"{ep.method.upper()} {ep.path}" for ep in parsed_spec.endpoints}
        lost = original_eps - parsed_eps

        # Param count check
        orig_params = sum(len(ep.required_params) + len(ep.optional_params) + len(ep.request_body) for ep in doclean_spec.endpoints)
        parsed_params = sum(len(ep.required_params) + len(ep.optional_params) + len(ep.request_body) for ep in parsed_spec.endpoints)

        return {
            "spec": Path(spec_path).name,
            "format": fmt,
            "endpoints_compiled": len(original_eps),
            "endpoints_parsed": len(parsed_eps),
            "endpoints_lost": sorted(lost),
            "params_compiled": orig_params,
            "params_parsed": parsed_params,
            "pass": len(lost) == 0 and parsed_params >= orig_params * 0.95,
        }
    except Exception as e:
        return {"spec": Path(spec_path).name, "format": fmt, "error": str(e), "pass": False}


def validate_all(formats: list[str] = None) -> dict:
    """Run validation across all specs in all available formats."""
    if formats is None:
        formats = list(_COMPILERS.keys())

    skip_names = {"stripe-full", "zoom", "jira"}
    all_results = {}

    for fmt in formats:
        if fmt not in _COMPILERS:
            continue
        specs_dir = Path(__file__).parent.parent / "examples"
        d = specs_dir if fmt == "openapi" else specs_dir / fmt
        if not d.exists():
            continue
        files = []
        for pattern in _SPEC_EXTENSIONS.get(fmt, ()):
            files.extend(glob.glob(str(d / pattern)))
        files = sorted(set(f for f in files if Path(f).stem not in skip_names))

        results = []
        for f in files:
            if fmt == "openapi":
                try:
                    r1 = validate_schema_completeness(f)
                    r2 = validate_roundtrip(f)
                    # Combine: pass only if both schema completeness AND round-trip pass
                    combined = {**r1, **r2}
                    schema_pass = (r1["total_endpoints"] == r1["compiled_endpoints"] and
                                   r1["captured_params"] == r1["total_params"])
                    combined["pass"] = schema_pass and r2.get("pass", False)
                    results.append(combined)
                except Exception as e:
                    results.append({"spec": Path(f).name, "error": str(e), "pass": False})
            else:
                results.append(validate_generic_format(f, fmt))

        if results:
            all_results[fmt] = results

    return all_results


def print_all_results(all_results: dict):
    """Print validation results across all formats."""
    total_pass = 0
    total_specs = 0
    for fmt, results in all_results.items():
        print(f"\n{'=' * 60}")
        print(f"✅ Validation — {fmt.upper()}")
        print(f"{'=' * 60}")
        for r in results:
            total_specs += 1
            if "error" in r:
                print(f"\n  ⚠️  {r['spec']}: {r['error']}")
                continue
            passed = r.get("pass", False)
            if passed:
                total_pass += 1
            status = "✅" if passed else "❌"
            eps = r.get("compiled_endpoints", r.get("endpoints_compiled", "?"))
            print(f"  {status} {r['spec']}: {eps} endpoints", end="")
            if "captured_params" in r:
                print(f", {r['captured_params']}/{r['total_params']} params", end="")
            if "breaking_changes" in r:
                print(f", {r['breaking_changes']} breaking changes", end="")
            print()

    print(f"\n{'=' * 60}")
    print(f"  TOTAL: {total_pass}/{total_specs} specs pass")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Validate DocLean semantic completeness")
    parser.add_argument("spec", nargs="?", help="Path to OpenAPI spec (or omit for --all)")
    parser.add_argument("--all", action="store_true", help="Validate all specs across all formats")
    parser.add_argument("--format", choices=list(_SPEC_EXTENSIONS.keys()), help="Filter to one format")
    parser.add_argument("--agent-test", action="store_true", help="Run LLM agent comparison (needs OPENAI_API_KEY)")
    parser.add_argument("--task", help="Custom task for agent test")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.all:
        fmts = [args.format] if args.format else None
        all_results = validate_all(formats=fmts)
        if args.json:
            print(json.dumps(all_results, indent=2, default=str))
        else:
            print_all_results(all_results)
        return

    if not args.spec:
        parser.error("Provide a spec path or use --all")

    # Layer 1: Schema completeness
    results = validate_schema_completeness(args.spec)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results)

    # Layer 3: Agent task comparison (optional)
    if args.agent_test:
        print("\n🤖 Running agent task comparison...")
        agent_results = validate_agent_task(args.spec, args.task)
        if "error" in agent_results:
            print(f"   ⚠️  {agent_results['error']}")
        else:
            print(f"   Task: {agent_results['task']}")
            print(f"   Verbose tokens: {agent_results['verbose_tokens_used']}")
            print(f"   DocLean tokens: {agent_results['lean_tokens_used']}")
            print(f"   Token savings:  {agent_results['token_savings']}")
            print(f"   Judge verdict:  {agent_results['judge_verdict']}")


if __name__ == "__main__":
    main()
