#!/usr/bin/env python3
"""
LAP — Compressed AI tool/skill manifests for the LAP protocol

Part of LAP (Lean Agent Protocol). LAP provides a compact, structured
representation for AI tool definitions from any source: MCP servers,
OpenClaw/ClawHub skills, Claude skills, or generic agent tools.

Usage:
    python lap.py compile-mcp <manifest.json> [-o output.lap]
    python lap.py compile-skill <SKILL.md> [-o output.lap]
    python lap.py compile-json <tool.json> [-o output.lap]
    python lap.py parse <file.lap>
    python lap.py stats <file.lap>
"""

import argparse
import json
import sys
from pathlib import Path

from lap.core.formats.lap_tools import LAPToolSpec, LAPToolBundle
from lap.core.compilers.lap_tools import (
    compile_mcp_file, compile_mcp_tool, compile_mcp_manifest,
    compile_skill_file, compile_skill_md,
    compile_generic_file, compile_generic_json,
)
from lap.core.compilers.lap_tools_parser import parse_lap_tools, parse_single_tool


def cmd_compile_mcp(args):
    bundle = compile_mcp_file(args.input)
    result = bundle.to_lap(lean=args.lean)
    _output(result, args.output)


def cmd_compile_skill(args):
    spec = compile_skill_file(args.input)
    result = spec.to_lap(lean=args.lean)
    _output(result, args.output)


def cmd_compile_json(args):
    spec = compile_generic_file(args.input)
    result = spec.to_lap(lean=args.lean)
    _output(result, args.output)


def cmd_parse(args):
    text = Path(args.input).read_text(encoding='utf-8')
    bundle = parse_lap_tools(text)
    for tool in bundle.tools:
        print(f"Tool: {tool.name}")
        print(f"  Desc: {tool.description}")
        print(f"  Auth: {tool.auth}")
        print(f"  Tags: {tool.tags}")
        print(f"  Inputs: {len(tool.inputs)}")
        for p in tool.inputs:
            opt = " (optional)" if not p.required else ""
            print(f"    {p.name}: {p.type}{opt} — {p.description}")
        print(f"  Outputs: {len(tool.outputs)}")
        for o in tool.outputs:
            print(f"    {o.name}: {o.type} — {o.description}")
        print()


def cmd_stats(args):
    text = Path(args.input).read_text(encoding='utf-8')
    bundle = parse_lap_tools(text)
    original_size = Path(args.input).stat().st_size
    print(f"File: {args.input}")
    print(f"Size: {original_size} bytes")
    print(f"Tools: {len(bundle.tools)}")
    total_params = sum(len(t.inputs) for t in bundle.tools)
    print(f"Total params: {total_params}")


def _output(text: str, path: str = None):
    if path:
        Path(path).write_text(text)
        print(f"✅ Written to {path}", file=sys.stderr)
    else:
        print(text)


def main():
    parser = argparse.ArgumentParser(description="LAP — Compressed AI tool manifests")
    sub = parser.add_subparsers(dest="command")

    for name in ("compile-mcp", "compile-skill", "compile-json", "parse", "stats"):
        sp = sub.add_parser(name)
        sp.add_argument("input", help="Input file path")
        if name.startswith("compile"):
            sp.add_argument("-o", "--output", help="Output file")
            sp.add_argument("--lean", action="store_true", help="Strip descriptions for max compression")

    args = parser.parse_args()
    cmds = {
        "compile-mcp": cmd_compile_mcp,
        "compile-skill": cmd_compile_skill,
        "compile-json": cmd_compile_json,
        "parse": cmd_parse,
        "stats": cmd_stats,
    }
    if args.command in cmds:
        cmds[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
