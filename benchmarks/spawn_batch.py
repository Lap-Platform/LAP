#!/usr/bin/env python3
"""
Reads prompt files from live_prompts/ and prints them as JSON for spawning.
Usage: python3 spawn_batch.py --list  (show all prompts)
       python3 spawn_batch.py --prompt <name>  (print prompt content)
"""
import sys
from pathlib import Path

prompts_dir = Path(__file__).parent / "live_prompts"

if "--list" in sys.argv:
    for f in sorted(prompts_dir.glob("*.txt")):
        print(f"{f.stem}: {f.stat().st_size} bytes")
elif "--prompt" in sys.argv:
    idx = sys.argv.index("--prompt") + 1
    name = sys.argv[idx]
    path = prompts_dir / f"{name}.txt"
    if path.exists():
        print(path.read_text())
    else:
        print(f"Not found: {path}", file=sys.stderr)
        sys.exit(1)
