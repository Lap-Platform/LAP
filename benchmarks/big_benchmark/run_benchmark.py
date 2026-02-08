#!/usr/bin/env python3
"""
Big Benchmark Runner - Reads all prompt files and writes spawn-ready task files.
Since we can't call sessions_spawn from Python, this prepares everything
so the main agent can spawn with embedded content using exec cat.
"""
import os
import json

BENCH_DIR = "/data/workspace/lap-poc/benchmarks/big_benchmark"
RESULTS_DIR = os.path.join(BENCH_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

SPECS = [
    "stripe-charges", "github-core", "discord",  # small
    "twitter", "resend", "launchdarkly", "petstore",  # medium
    "snyk", "hetzner", "plaid"  # large
]

PREFIX = """You are running an API benchmark. Below is API documentation followed by 5 tasks.
For each task, write the EXACT curl command. Do NOT read any files - everything you need is below.

Format your response EXACTLY as:
TASK 1: <curl command>
TASK 2: <curl command>
TASK 3: <curl command>
TASK 4: <curl command>
TASK 5: <curl command>

"""

summary = []
for spec in SPECS:
    for variant in ["verbose", "doclean"]:
        prompt_file = os.path.join(BENCH_DIR, f"{variant}_{spec}.txt")
        if not os.path.exists(prompt_file):
            print(f"SKIP: {prompt_file} not found")
            continue
        
        size = os.path.getsize(prompt_file)
        lines = sum(1 for _ in open(prompt_file))
        
        # Write a task file that can be cat'd into sessions_spawn
        task_file = os.path.join(BENCH_DIR, f"task_{variant}_{spec}.txt")
        with open(prompt_file) as f:
            content = f.read()
        
        # Prepend instruction to NOT use file tools
        task_content = PREFIX + content
        with open(task_file, 'w') as f:
            f.write(task_content)
        
        summary.append({
            "spec": spec,
            "variant": variant,
            "size_bytes": size,
            "lines": lines,
            "task_file": task_file,
            "result_file": os.path.join(RESULTS_DIR, f"{variant}_{spec}_results.txt")
        })
        print(f"{variant}_{spec}: {size:,} bytes, {lines} lines")

# Write summary for the spawner
with open(os.path.join(BENCH_DIR, "spawn_manifest.json"), 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\nTotal: {len(summary)} agents to spawn")
print(f"Manifest: {os.path.join(BENCH_DIR, 'spawn_manifest.json')}")
