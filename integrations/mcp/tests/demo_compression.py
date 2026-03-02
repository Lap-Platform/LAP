#!/usr/bin/env python3
"""
Demonstrate MCP tool compression with before/after examples.
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from integrations.mcp.compress import compress_mcp_tool, get_compression_stats


def demonstrate_compression():
    """Show before/after compression examples."""
    
    fixtures_dir = Path(__file__).parent.parent / 'test_fixtures'
    
    print("\n" + "=" * 90)
    print("MCP TOOL COMPRESSION DEMONSTRATION")
    print("=" * 90)
    
    # Example 1: PostgreSQL query tool (most compressed)
    postgres_file = fixtures_dir / 'postgres.json'
    if postgres_file.exists():
        manifest = json.loads(postgres_file.read_text())
        tool = manifest['tools'][0]  # postgres_query
        
        print("\n📊 EXAMPLE 1: PostgreSQL Query Tool")
        print("-" * 90)
        print("BEFORE:")
        print(f"  {tool['description']}")
        print(f"  Length: {len(tool['description'])} chars")
        
        compressed = compress_mcp_tool(tool)
        print("\nAFTER:")
        print(f"  {compressed['description']}")
        print(f"  Length: {len(compressed['description'])} chars")
        
        stats = get_compression_stats(tool['description'], compressed['description'])
        print(f"\n  💾 Saved: {stats['saved_chars']} chars ({stats['compression_pct']:.1f}%)")
    
    # Example 2: GitHub create_or_update_file (good compression)
    github_file = fixtures_dir / 'github.json'
    if github_file.exists():
        manifest = json.loads(github_file.read_text())
        tool = manifest['tools'][0]  # create_or_update_file
        
        print("\n" + "=" * 90)
        print("📊 EXAMPLE 2: GitHub File Management Tool")
        print("-" * 90)
        print("BEFORE:")
        print(f"  {tool['description']}")
        print(f"  Length: {len(tool['description'])} chars")
        
        compressed = compress_mcp_tool(tool)
        print("\nAFTER:")
        print(f"  {compressed['description']}")
        print(f"  Length: {len(compressed['description'])} chars")
        
        stats = get_compression_stats(tool['description'], compressed['description'])
        print(f"\n  💾 Saved: {stats['saved_chars']} chars ({stats['compression_pct']:.1f}%)")
        
        # Show parameter compression too
        if 'inputSchema' in tool and 'properties' in tool['inputSchema']:
            orig_param = tool['inputSchema']['properties'].get('owner', {}).get('description', '')
            comp_param = compressed['inputSchema']['properties'].get('owner', {}).get('description', '')
            if orig_param != comp_param:
                print("\n  Parameter description compression:")
                print(f"    Before: '{orig_param}'")
                print(f"    After:  '{comp_param}'")
    
    # Example 3: Brave Search (minimal compression on concise input)
    brave_file = fixtures_dir / 'brave-search.json'
    if brave_file.exists():
        manifest = json.loads(brave_file.read_text())
        tool = manifest['tools'][0]  # web_search
        
        print("\n" + "=" * 90)
        print("📊 EXAMPLE 3: Brave Web Search (Already Concise)")
        print("-" * 90)
        print("BEFORE:")
        print(f"  {tool['description']}")
        print(f"  Length: {len(tool['description'])} chars")
        
        compressed = compress_mcp_tool(tool)
        print("\nAFTER:")
        print(f"  {compressed['description']}")
        print(f"  Length: {len(compressed['description'])} chars")
        
        stats = get_compression_stats(tool['description'], compressed['description'])
        print(f"\n  💾 Saved: {stats['saved_chars']} chars ({stats['compression_pct']:.1f}%)")
        print("  ℹ️  Minimal compression - already well-written description")
    
    print("\n" + "=" * 90)
    print("KEY COMPRESSION TECHNIQUES")
    print("=" * 90)
    print("""
  1. Filler Removal:        "This tool enables you to" → ""
  2. Term Shortening:       "repository" → "repo", "database" → "DB"
  3. Operation Simplify:    "retrieve" → "get", "execute" → "run"
  4. Redundancy Removal:    "very useful" → "useful"
  5. Safety Note Removal:   "Use with caution..." → "" (kept in schema)
  6. Phrase Compression:    "provides ability to" → ""
    """)
    
    print("=" * 90)
    print("\n✅ Compression preserves semantic meaning while reducing token usage\n")


if __name__ == '__main__':
    demonstrate_compression()
