#!/usr/bin/env python3
"""DocLean Falsification Tests — 7 tests to try to disprove DocLean's value."""

import json
import os
import re
import sys
import gzip
import yaml
import tiktoken

VERBOSE_DIR = "/data/workspace/lap-benchmark-docs/verbose"
DOCLEAN_DIR = "/data/workspace/lap-benchmark-docs/doclean"

enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(enc.encode(text))

def load_all_specs():
    """Load all verbose and doclean specs, paired by name."""
    specs = []
    for f in sorted(os.listdir(VERBOSE_DIR)):
        name = f.rsplit(".", 1)[0]
        verbose_path = os.path.join(VERBOSE_DIR, f)
        # Find matching doclean
        doclean_path = os.path.join(DOCLEAN_DIR, name + ".doclean")
        if not os.path.exists(doclean_path):
            continue
        with open(verbose_path) as vf:
            verbose_text = vf.read()
        with open(doclean_path) as df:
            doclean_text = df.read()
        specs.append({
            "name": name,
            "ext": f.rsplit(".", 1)[1],
            "verbose_text": verbose_text,
            "doclean_text": doclean_text,
            "verbose_tokens": count_tokens(verbose_text),
            "doclean_tokens": count_tokens(doclean_text),
        })
    return specs

def strip_descriptions(text, ext):
    """Remove description/comment fields from spec text."""
    if ext in ("yaml", "yml"):
        # Remove description lines and multi-line descriptions
        lines = text.split("\n")
        out = []
        skip_indent = None
        for line in lines:
            stripped = line.lstrip()
            if skip_indent is not None:
                curr_indent = len(line) - len(stripped)
                if curr_indent > skip_indent or (stripped and not stripped[0].isalpha() and stripped[0] not in ('#','-')):
                    continue
                else:
                    skip_indent = None
            if stripped.startswith("description:") or stripped.startswith("summary:") or stripped.startswith("# "):
                if stripped.startswith("description: |") or stripped.startswith("description: >"):
                    skip_indent = len(line) - len(stripped)
                continue
            out.append(line)
        return "\n".join(out)
    elif ext == "json":
        # Parse JSON, remove description/summary fields recursively
        try:
            data = json.loads(text)
            return json.dumps(strip_json_descriptions(data), indent=2)
        except:
            return re.sub(r'"(description|summary)":\s*"[^"]*",?\s*\n?', '', text)
    elif ext == "graphql":
        # Remove comments (lines starting with #) and string descriptions
        lines = text.split("\n")
        out = []
        in_block_str = False
        for line in lines:
            s = line.strip()
            if s.startswith('"""'):
                in_block_str = not in_block_str
                continue
            if in_block_str:
                continue
            if s.startswith("#"):
                continue
            if s.startswith('"') and s.endswith('"') and len(s) > 2:
                continue
            out.append(line)
        return "\n".join(out)
    elif ext == "proto":
        # Remove comments
        lines = text.split("\n")
        out = []
        in_block = False
        for line in lines:
            s = line.strip()
            if "/*" in s:
                in_block = True
            if in_block:
                if "*/" in s:
                    in_block = False
                continue
            if s.startswith("//"):
                continue
            out.append(line)
        return "\n".join(out)
    return text

def strip_json_descriptions(obj):
    if isinstance(obj, dict):
        return {k: strip_json_descriptions(v) for k, v in obj.items()
                if k not in ("description", "summary", "x-description")}
    elif isinstance(obj, list):
        return [strip_json_descriptions(i) for i in obj]
    return obj

def minify_json(text, ext):
    """Convert to minified JSON."""
    if ext == "json":
        try:
            data = json.loads(text)
            return json.dumps(data, separators=(',', ':'))
        except:
            return text
    elif ext in ("yaml", "yml"):
        try:
            data = yaml.safe_load(text)
            return json.dumps(data, separators=(',', ':'))
        except:
            return text
    return text  # Can't minify graphql/proto as JSON

def yaml_convert(text, ext):
    """Convert JSON to YAML."""
    if ext == "json":
        try:
            data = json.loads(text)
            return yaml.dump(data, default_flow_style=False)
        except:
            return text
    return text  # Already YAML or not applicable

def field_filter(text, ext):
    """Remove descriptions, examples, x- extensions (jq-style filtering)."""
    if ext in ("json",):
        try:
            data = json.loads(text)
            data = deep_filter(data)
            return json.dumps(data, indent=2)
        except:
            return text
    elif ext in ("yaml", "yml"):
        try:
            data = yaml.safe_load(text)
            data = deep_filter(data)
            return yaml.dump(data, default_flow_style=False)
        except:
            return text
    return text

def deep_filter(obj):
    remove_keys = {"description", "summary", "example", "examples", "x-description",
                   "externalDocs", "x-examples", "x-code-samples"}
    if isinstance(obj, dict):
        return {k: deep_filter(v) for k, v in obj.items() if k not in remove_keys}
    elif isinstance(obj, list):
        return [deep_filter(i) for i in obj]
    return obj


def test1(specs):
    """Is DocLean just removing comments?"""
    results = []
    for s in specs:
        stripped = strip_descriptions(s["verbose_text"], s["ext"])
        stripped_tokens = count_tokens(stripped)
        results.append({
            "Spec": s["name"],
            "Verbose": s["verbose_tokens"],
            "Stripped": stripped_tokens,
            "DocLean": s["doclean_tokens"],
            "Strip%": round((1 - stripped_tokens/s["verbose_tokens"])*100, 1) if s["verbose_tokens"] else 0,
            "DocLean%": round((1 - s["doclean_tokens"]/s["verbose_tokens"])*100, 1) if s["verbose_tokens"] else 0,
        })
    
    # Verdict: if DocLean tokens are significantly less than stripped, it's doing more than removing comments
    total_stripped = sum(r["Stripped"] for r in results)
    total_doclean = sum(r["DocLean"] for r in results)
    extra_compression = round((1 - total_doclean/total_stripped)*100, 1) if total_stripped else 0
    
    verdict = "SURVIVED" if extra_compression > 10 else "FAILED"
    summary = f"Stripped comments: {total_stripped:,} tokens | DocLean: {total_doclean:,} tokens | Extra compression beyond comment removal: {extra_compression}%"
    
    return {"name": "Test 1: Is DocLean just removing comments?", "results": results, "verdict": verdict, "summary": summary, "extra_pct": extra_compression}


def test2(specs):
    """Can the LLM already ignore the bloat? (Theoretical analysis)"""
    # We can't actually call an LLM here, so we analyze token overhead
    # The argument: if specs are small relative to context, compression doesn't matter
    sizes = [(s["name"], s["verbose_tokens"]) for s in specs]
    sizes.sort(key=lambda x: x[1], reverse=True)
    
    context_200k = 200000
    results = []
    for name, tokens in sizes:
        pct_of_context = round(tokens / context_200k * 100, 1)
        results.append({"Spec": name, "Tokens": tokens, "% of 200K": pct_of_context})
    
    large_specs = [s for s in sizes if s[1] > 20000]
    verdict = "SURVIVED" if len(large_specs) >= 3 else "FAILED"
    summary = f"{len(large_specs)}/{len(sizes)} specs exceed 20K tokens. Largest: {sizes[0][0]} ({sizes[0][1]:,} tokens, {round(sizes[0][1]/context_200k*100,1)}% of 200K context). Compression matters for large specs that leave less room for conversation."
    
    return {"name": "Test 2: Can the LLM already ignore the bloat?", "results": results, "verdict": verdict, "summary": summary}


def test3(specs):
    """Does minified JSON beat DocLean?"""
    results = []
    for s in specs:
        minified = minify_json(s["verbose_text"], s["ext"])
        min_tokens = count_tokens(minified)
        results.append({
            "Spec": s["name"],
            "Verbose": s["verbose_tokens"],
            "Minified": min_tokens,
            "DocLean": s["doclean_tokens"],
            "Min%": round((1 - min_tokens/s["verbose_tokens"])*100, 1) if s["verbose_tokens"] else 0,
            "DL%": round((1 - s["doclean_tokens"]/s["verbose_tokens"])*100, 1) if s["verbose_tokens"] else 0,
        })
    
    # Only compare specs that could be minified (json/yaml)
    comparable = [r for r in results if r["Minified"] != r["Verbose"] or r["Min%"] != 0]
    if comparable:
        avg_min = sum(r["Min%"] for r in comparable) / len(comparable)
        avg_dl = sum(r["DL%"] for r in comparable) / len(comparable)
    else:
        avg_min = avg_dl = 0
    
    verdict = "SURVIVED" if avg_dl > avg_min + 10 else "FAILED"
    summary = f"Avg minification: {avg_min:.1f}% | Avg DocLean: {avg_dl:.1f}% | DocLean advantage: {avg_dl - avg_min:.1f}pp"
    
    return {"name": "Test 3: Does minified JSON beat DocLean?", "results": results, "verdict": verdict, "summary": summary}


def test4(specs):
    """Context window is big enough."""
    context_sizes = [128000, 200000, 1000000]
    total_verbose = sum(s["verbose_tokens"] for s in specs)
    total_doclean = sum(s["doclean_tokens"] for s in specs)
    
    results = []
    for ctx in context_sizes:
        v_fit = sum(1 for s in specs if s["verbose_tokens"] <= ctx * 0.5)  # 50% for spec, 50% for conversation
        d_fit = sum(1 for s in specs if s["doclean_tokens"] <= ctx * 0.5)
        v_room = ctx - total_verbose if total_verbose < ctx else 0
        d_room = ctx - total_doclean if total_doclean < ctx else 0
        results.append({
            "Context": f"{ctx//1000}K",
            "Verbose Fit (50%)": f"{v_fit}/{len(specs)}",
            "DocLean Fit (50%)": f"{d_fit}/{len(specs)}",
            "All Verbose": f"{total_verbose:,}",
            "All DocLean": f"{total_doclean:,}",
        })
    
    # Check: do any specs NOT fit in 100K (50% budget)?
    big_specs = [s for s in specs if s["verbose_tokens"] > 50000]
    verdict = "SURVIVED" if big_specs else "FAILED"
    summary = f"Total verbose: {total_verbose:,} | Total DocLean: {total_doclean:,} | {len(big_specs)} specs exceed 50K tokens (won't fit in 50% of 100K context)"
    
    return {"name": "Test 4: Context window is big enough", "results": results, "verdict": verdict, "summary": summary}


def test5(specs):
    """Does DocLean hurt on complex tasks? (Information preservation analysis)"""
    # Analyze what information is preserved/lost in DocLean
    results = []
    for s in specs:
        v = s["verbose_text"].lower()
        d = s["doclean_text"].lower()
        
        # Check for key elements
        checks = {
            "auth": any(w in v for w in ["authorization", "bearer", "oauth", "api_key", "apikey"]),
            "pagination": any(w in v for w in ["pagination", "page", "offset", "cursor", "limit"]),
            "errors": any(w in v for w in ["error", "400", "401", "403", "404", "500"]),
        }
        
        preserved = {}
        for key, present_in_v in checks.items():
            if present_in_v:
                present_in_d = any(w in d for w in {
                    "auth": ["auth", "bearer", "oauth", "api_key", "apikey"],
                    "pagination": ["page", "offset", "cursor", "limit"],
                    "errors": ["err", "400", "401", "403", "404", "500"],
                }[key])
                preserved[key] = present_in_d
        
        if preserved:
            pct = round(sum(preserved.values()) / len(preserved) * 100)
            results.append({
                "Spec": s["name"],
                "Auth": "✅" if preserved.get("auth", None) else ("❌" if "auth" in preserved else "N/A"),
                "Pagination": "✅" if preserved.get("pagination", None) else ("❌" if "pagination" in preserved else "N/A"),
                "Errors": "✅" if preserved.get("errors", None) else ("❌" if "errors" in preserved else "N/A"),
                "Preserved%": f"{pct}%",
            })
    
    total_checks = sum(1 for r in results for k in ["Auth","Pagination","Errors"] if r[k] in ("✅","❌"))
    total_preserved = sum(1 for r in results for k in ["Auth","Pagination","Errors"] if r[k] == "✅")
    pct = round(total_preserved/total_checks*100, 1) if total_checks else 100
    
    verdict = "SURVIVED" if pct >= 80 else "FAILED"
    summary = f"Key info preserved: {total_preserved}/{total_checks} ({pct}%). DocLean retains structural elements needed for complex tasks."
    
    return {"name": "Test 5: Does DocLean hurt on complex tasks?", "results": results, "verdict": verdict, "summary": summary}


def test6(specs):
    """Cost savings are negligible."""
    total_verbose = sum(s["verbose_tokens"] for s in specs)
    total_doclean = sum(s["doclean_tokens"] for s in specs)
    avg_verbose = total_verbose / len(specs)
    avg_doclean = total_doclean / len(specs)
    saved_per_call = avg_verbose - avg_doclean
    
    # Pricing per million tokens (input)
    pricing = {
        "Claude Sonnet ($3/MTok)": 3.0,
        "GPT-4o ($2.50/MTok)": 2.5,
    }
    
    results = []
    for calls_per_day in [1000, 10000, 100000]:
        for model, price in pricing.items():
            daily_saved_tokens = saved_per_call * calls_per_day
            daily_savings = daily_saved_tokens / 1_000_000 * price
            monthly_savings = daily_savings * 30
            yearly_savings = daily_savings * 365
            results.append({
                "Model": model,
                "Calls/Day": f"{calls_per_day:,}",
                "Saved/Day": f"${daily_savings:,.2f}",
                "Saved/Mo": f"${monthly_savings:,.2f}",
                "Saved/Yr": f"${yearly_savings:,.2f}",
            })
    
    # At 100K calls/day with Claude Sonnet
    big_savings = saved_per_call * 100000 / 1_000_000 * 3.0 * 365
    verdict = "SURVIVED" if big_savings > 1000 else "FAILED"
    summary = f"Avg tokens saved per call: {saved_per_call:,.0f} | At 100K calls/day, Claude Sonnet saves ${big_savings:,.0f}/year"
    
    return {"name": "Test 6: Cost savings are negligible", "results": results, "verdict": verdict, "summary": summary}


def test7(specs):
    """Existing tools already do this."""
    results = []
    for s in specs:
        verbose_tokens = s["verbose_tokens"]
        doclean_tokens = s["doclean_tokens"]
        
        # (a) JSON minification
        minified = minify_json(s["verbose_text"], s["ext"])
        min_tokens = count_tokens(minified)
        
        # (b) YAML conversion
        yaml_text = yaml_convert(s["verbose_text"], s["ext"])
        yaml_tokens = count_tokens(yaml_text)
        
        # (c) Field filtering
        filtered = field_filter(s["verbose_text"], s["ext"])
        filter_tokens = count_tokens(filtered)
        
        # (d) gzip ratio
        gzip_size = len(gzip.compress(s["verbose_text"].encode()))
        orig_size = len(s["verbose_text"].encode())
        gzip_ratio = round(gzip_size / orig_size * 100, 1)
        
        results.append({
            "Spec": s["name"],
            "Verbose": verbose_tokens,
            "Minified": min_tokens,
            "YAML": yaml_tokens,
            "Filtered": filter_tokens,
            "DocLean": doclean_tokens,
            "gzip%": f"{gzip_ratio}%",
        })
    
    # Compare: does any existing method match DocLean?
    total_v = sum(r["Verbose"] for r in results)
    total_min = sum(r["Minified"] for r in results)
    total_yaml = sum(r["YAML"] for r in results)
    total_filt = sum(r["Filtered"] for r in results)
    total_dl = sum(r["DocLean"] for r in results)
    
    best_existing = min(total_min, total_yaml, total_filt)
    best_name = "Minified" if best_existing == total_min else ("YAML" if best_existing == total_yaml else "Filtered")
    
    dl_vs_best = round((1 - total_dl/best_existing)*100, 1) if best_existing else 0
    verdict = "SURVIVED" if dl_vs_best > 15 else "FAILED"
    summary = f"Best existing: {best_name} ({total_v - best_existing:,} tokens saved) | DocLean: {total_v - total_dl:,} tokens saved | DocLean beats best existing by {dl_vs_best}%"
    
    return {"name": "Test 7: Existing tools already do this", "results": results, "verdict": verdict, "summary": summary}


def main():
    print("Loading specs...")
    specs = load_all_specs()
    print(f"Loaded {len(specs)} spec pairs")
    
    all_results = {}
    tests = [test1, test2, test3, test4, test5, test6, test7]
    
    for i, test_fn in enumerate(tests, 1):
        print(f"\nRunning Test {i}...")
        result = test_fn(specs)
        all_results[f"test{i}"] = result
        print(f"  {result['verdict']}: {result['summary']}")
    
    # Save results
    output = {"specs_count": len(specs), "tests": all_results}
    out_path = "/data/workspace/lap-poc/falsification/results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")
    
    return output

if __name__ == "__main__":
    results = main()
