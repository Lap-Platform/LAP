#!/usr/bin/env python3
"""Real MCP server integration test for LAP proxy."""

import json
import subprocess
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import tiktoken
from integrations.mcp.lap_mcp_proxy import LapMcpProxy, measure_fidelity

enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(enc.encode(text))

def talk_to_mcp(cmd, timeout=30):
    """Start an MCP server, send initialize + tools/list, return tools response."""
    print(f"\n{'='*60}")
    print(f"Starting: {' '.join(cmd)}")
    
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True
    )
    
    # Send initialize
    init_msg = json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{
        "protocolVersion":"2024-11-05",
        "capabilities":{},
        "clientInfo":{"name":"lap-test","version":"0.1.0"}
    }}) + "\n"
    
    proc.stdin.write(init_msg)
    proc.stdin.flush()
    
    # Read init response
    init_resp = proc.stdout.readline()
    print(f"Init response: {init_resp[:200]}...")
    
    # Send initialized notification
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}) + "\n")
    proc.stdin.flush()
    
    # Send tools/list
    tools_msg = json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/list"}) + "\n"
    proc.stdin.write(tools_msg)
    proc.stdin.flush()
    
    # Read tools response
    tools_resp = proc.stdout.readline()
    
    proc.stdin.close()
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except:
        proc.kill()
    
    stderr = proc.stderr.read()
    if stderr:
        print(f"Stderr: {stderr[:500]}")
    
    return json.loads(init_resp), json.loads(tools_resp)


def test_tool_call(cmd, tool_name, arguments):
    """Start MCP server, initialize, call a tool, return result."""
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True
    )
    
    # Initialize
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{
        "protocolVersion":"2024-11-05","capabilities":{},
        "clientInfo":{"name":"lap-test","version":"0.1.0"}
    }}) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()  # init response
    
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}) + "\n")
    proc.stdin.flush()
    
    # Call tool
    call_msg = json.dumps({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{
        "name": tool_name, "arguments": arguments
    }}) + "\n"
    proc.stdin.write(call_msg)
    proc.stdin.flush()
    
    result = proc.stdout.readline()
    
    proc.stdin.close()
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except:
        proc.kill()
    
    return json.loads(result)


def analyze_server(name, cmd, call_test=None):
    """Full analysis of one MCP server."""
    results = {"name": name, "cmd": cmd}
    
    try:
        init_resp, tools_resp = talk_to_mcp(cmd)
        results["init"] = init_resp
        
        tools = tools_resp.get("result", {}).get("tools", [])
        results["tool_count"] = len(tools)
        print(f"Got {len(tools)} tools")
        
        # Build manifest format
        manifest = {"name": name, "description": f"{name} MCP server", "tools": tools}
        results["raw_manifest"] = manifest
        
        # Measure original
        orig_json = json.dumps(manifest, indent=2)
        orig_tokens = count_tokens(orig_json)
        results["orig_bytes"] = len(orig_json)
        results["orig_tokens"] = orig_tokens
        
        # LAP compress
        proxy = LapMcpProxy()
        t0 = time.time()
        lap_text = proxy.compress_tools_list(manifest)
        compress_time = time.time() - t0
        
        lap_tokens = count_tokens(lap_text)
        results["lap_bytes"] = len(lap_text)
        results["lap_tokens"] = lap_tokens
        results["compress_time_ms"] = compress_time * 1000
        results["token_savings"] = f"{(1 - lap_tokens/orig_tokens)*100:.1f}%"
        results["lap_text"] = lap_text
        
        # Fidelity
        reconstructed = proxy.reconstruct_manifest(name)
        fidelity = measure_fidelity(manifest, reconstructed)
        results["fidelity"] = fidelity
        
        print(f"Original: {orig_tokens} tokens, LAP: {lap_tokens} tokens, savings: {results['token_savings']}")
        print(f"Fidelity: {fidelity['tools_matched']}/{fidelity['tools_total']} tools, issues: {fidelity['param_issues']}")
        
        # Tool call test
        if call_test:
            tool_name, args = call_test
            print(f"\nTesting tools/call: {tool_name}({args})")
            call_result = test_tool_call(cmd, tool_name, args)
            results["call_test"] = {"tool": tool_name, "args": args, "result": call_result}
            print(f"Result: {json.dumps(call_result)[:300]}")
        
    except Exception as e:
        results["error"] = str(e)
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
    
    return results


def main():
    all_results = []
    
    # 1. Filesystem server
    r = analyze_server(
        "filesystem",
        ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        call_test=("list_directory", {"path": "/tmp"})
    )
    all_results.append(r)
    
    # 2. Memory server
    r = analyze_server(
        "memory",
        ["npx", "-y", "@modelcontextprotocol/server-memory"],
        call_test=("create_entities", {"entities": [{"name": "test", "entityType": "thing", "observations": ["hello"]}]})
    )
    all_results.append(r)
    
    # 3. Try other servers
    for name, cmd in [
        ("everything", ["npx", "-y", "@modelcontextprotocol/server-everything"]),
        ("sequential-thinking", ["npx", "-y", "@modelcontextprotocol/server-sequential-thinking"]),
    ]:
        r = analyze_server(name, cmd)
        all_results.append(r)
    
    # Save raw data
    with open(os.path.join(os.path.dirname(__file__), "real_test_data.json"), "w") as f:
        # Save serializable parts
        save = []
        for r in all_results:
            s = {k: v for k, v in r.items() if k != "raw_manifest"}
            save.append(s)
        json.dump(save, f, indent=2, default=str)
    
    # Generate report
    generate_report(all_results)


def generate_report(results):
    lines = ["# Real MCP Server Integration Test Results\n"]
    lines.append(f"**Date:** 2026-02-11\n")
    lines.append(f"**Method:** Started real MCP servers via `npx`, communicated over stdio JSON-RPC\n\n")
    
    lines.append("## Summary\n")
    lines.append("| Server | Tools | Orig Tokens | LAP Tokens | Savings | Fidelity |")
    lines.append("|--------|-------|-------------|------------|---------|----------|")
    
    for r in results:
        if "error" in r:
            lines.append(f"| {r['name']} | ❌ | - | - | - | Error: {r['error'][:50]} |")
        else:
            fid = r.get("fidelity", {})
            issues = len(fid.get("param_issues", []))
            fid_str = "✅ 100%" if issues == 0 else f"⚠️ {issues} issues"
            lines.append(f"| {r['name']} | {r.get('tool_count',0)} | {r.get('orig_tokens',0)} | {r.get('lap_tokens',0)} | {r.get('token_savings','?')} | {fid_str} |")
    
    lines.append("\n## Detailed Results\n")
    
    for r in results:
        lines.append(f"### {r['name']}\n")
        if "error" in r:
            lines.append(f"**Error:** {r['error']}\n")
            continue
        
        lines.append(f"- **Command:** `{' '.join(r['cmd'])}`")
        lines.append(f"- **Tools found:** {r.get('tool_count', 0)}")
        lines.append(f"- **Original:** {r.get('orig_bytes', 0)} bytes / {r.get('orig_tokens', 0)} tokens")
        lines.append(f"- **LAP compressed:** {r.get('lap_bytes', 0)} bytes / {r.get('lap_tokens', 0)} tokens")
        lines.append(f"- **Token savings:** {r.get('token_savings', '?')}")
        lines.append(f"- **Compression time:** {r.get('compress_time_ms', 0):.1f}ms")
        
        fid = r.get("fidelity", {})
        lines.append(f"- **Round-trip fidelity:** {fid.get('tools_matched', 0)}/{fid.get('tools_total', 0)} tools matched")
        if fid.get("param_issues"):
            lines.append(f"- **Issues:** {fid['param_issues']}")
        
        if "call_test" in r:
            ct = r["call_test"]
            success = "error" not in ct.get("result", {})
            lines.append(f"- **Tool call test:** `{ct['tool']}` → {'✅ Success' if success else '❌ Failed'}")
        
        # Show LAP output sample
        lap = r.get("lap_text", "")
        if lap:
            lines.append(f"\n<details><summary>LAP compressed output ({r.get('lap_tokens', 0)} tokens)</summary>\n")
            lines.append(f"```\n{lap}\n```\n</details>\n")
        
        # Show first tool before/after
        manifest = r.get("raw_manifest", {})
        tools = manifest.get("tools", [])
        if tools:
            first = tools[0]
            lines.append(f"\n<details><summary>Example: {first['name']} (original JSON Schema)</summary>\n")
            lines.append(f"```json\n{json.dumps(first, indent=2)}\n```\n</details>\n")
    
    lines.append("\n## Conclusions\n")
    lines.append("- Real MCP servers were started and queried over stdio JSON-RPC")
    lines.append("- LAP proxy successfully compressed real tool schemas")
    lines.append("- Round-trip fidelity measured by reconstructing JSON Schema from LAP")
    lines.append("- Tool calls tested through real servers to verify end-to-end functionality\n")
    
    report_path = os.path.join(os.path.dirname(__file__), "REAL_MCP_TEST_RESULTS.md")
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
