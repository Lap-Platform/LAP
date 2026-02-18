#!/usr/bin/env python3
"""
Test MCP tool compression via LAP format.

Loads real MCP tool manifests from test fixtures, compiles them through
LAP format with compression, and measures compression ratios.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from lap.core.compilers.lap_tools import compile_mcp_tool, compile_mcp_manifest
from integrations.mcp.compress import (
    compress_mcp_tool,
    compress_mcp_manifest,
    get_compression_stats,
)


def calculate_manifest_size(manifest: Dict[str, Any]) -> int:
    """Calculate total character size of all descriptions in a manifest."""
    total = 0
    
    # Add manifest description
    if 'description' in manifest:
        total += len(manifest['description'])
    
    # Add all tool descriptions and schema descriptions
    for tool in manifest.get('tools', []):
        if 'description' in tool:
            total += len(tool['description'])
        
        # Add input schema descriptions
        if 'inputSchema' in tool:
            total += _count_schema_descriptions(tool['inputSchema'])
    
    return total


def _count_schema_descriptions(schema: Dict[str, Any]) -> int:
    """Recursively count all description characters in a schema."""
    total = 0
    
    if 'description' in schema:
        total += len(schema['description'])
    
    if 'properties' in schema:
        for prop in schema['properties'].values():
            if isinstance(prop, dict):
                total += _count_schema_descriptions(prop)
    
    if 'items' in schema:
        if isinstance(schema['items'], dict):
            total += _count_schema_descriptions(schema['items'])
        elif isinstance(schema['items'], list):
            for item in schema['items']:
                if isinstance(item, dict):
                    total += _count_schema_descriptions(item)
    
    for key in ['allOf', 'anyOf', 'oneOf']:
        if key in schema and isinstance(schema[key], list):
            for sub in schema[key]:
                if isinstance(sub, dict):
                    total += _count_schema_descriptions(sub)
    
    return total


def test_fixture_compression(fixture_path: Path) -> Dict[str, Any]:
    """
    Test compression on a single fixture file.
    
    Returns:
        Dict with fixture name, tool count, and compression stats
    """
    # Load fixture
    manifest = json.loads(fixture_path.read_text())
    server_name = manifest.get('name', fixture_path.stem)
    tools = manifest.get('tools', [])
    
    # Calculate original size
    orig_size = calculate_manifest_size(manifest)
    
    # Compress manifest
    compressed_tools = compress_mcp_manifest(tools)
    compressed_manifest = manifest.copy()
    compressed_manifest['tools'] = compressed_tools
    
    # Compress manifest description if present
    if 'description' in compressed_manifest:
        from integrations.mcp.compress import compress_tool_description
        compressed_manifest['description'] = compress_tool_description(
            compressed_manifest['description']
        )
    
    # Calculate compressed size
    comp_size = calculate_manifest_size(compressed_manifest)
    
    # Calculate stats
    stats = get_compression_stats(str(orig_size), str(comp_size))
    
    # Verify compressed descriptions aren't empty
    for tool in compressed_tools:
        assert tool.get('description'), f"Tool {tool.get('name')} has empty description after compression"
    
    # Verify JSON Schema is still valid (has required structure)
    for tool in compressed_tools:
        schema = tool.get('inputSchema', {})
        assert isinstance(schema, dict), f"Tool {tool.get('name')} has invalid inputSchema"
        if 'properties' in schema:
            assert isinstance(schema['properties'], dict), "Schema properties must be a dict"
    
    return {
        'server': server_name,
        'tools_count': len(tools),
        'original_chars': orig_size,
        'compressed_chars': comp_size,
        'saved_chars': orig_size - comp_size,
        'ratio': (orig_size - comp_size) / orig_size if orig_size > 0 else 0,
        'manifest': compressed_manifest,
    }


def print_compression_table(results: List[Dict[str, Any]]) -> None:
    """Print a formatted table of compression results."""
    
    print("\n" + "=" * 90)
    print("MCP TOOL MANIFEST COMPRESSION RESULTS")
    print("=" * 90)
    print(f"{'Server':<20} {'Tools':<8} {'Original':<12} {'Compressed':<12} {'Saved':<10} {'Ratio':<8}")
    print("-" * 90)
    
    total_tools = 0
    total_orig = 0
    total_comp = 0
    
    for result in results:
        server = result['server']
        tools = result['tools_count']
        orig = result['original_chars']
        comp = result['compressed_chars']
        saved = result['saved_chars']
        ratio = result['ratio']
        
        total_tools += tools
        total_orig += orig
        total_comp += comp
        
        print(f"{server:<20} {tools:<8} {orig:<12,} {comp:<12,} {saved:<10,} {ratio:>6.1%}")
    
    print("-" * 90)
    total_saved = total_orig - total_comp
    total_ratio = total_saved / total_orig if total_orig > 0 else 0
    print(f"{'TOTAL':<20} {total_tools:<8} {total_orig:<12,} {total_comp:<12,} {total_saved:<10,} {total_ratio:>6.1%}")
    print("=" * 90)
    print()


def test_lap_compilation(fixture_path: Path) -> None:
    """Test that LAP compilation works for a fixture."""
    manifest = json.loads(fixture_path.read_text())
    
    # Test single tool compilation
    if manifest.get('tools'):
        tool = manifest['tools'][0]
        spec = compile_mcp_tool(tool)
        assert spec.name, "Compiled tool must have a name"
        
        # Convert to LAP format
        lap_str = spec.to_lap(lean=False)
        assert '@tool' in lap_str, "LAP output must contain @tool directive"
        assert '@in' in lap_str or len(spec.inputs) == 0, "LAP must contain @in for tools with inputs"
    
    # Test full manifest compilation
    bundle = compile_mcp_manifest(manifest)
    assert bundle.name == manifest.get('name', ''), "Bundle name should match manifest"
    assert len(bundle.tools) == len(manifest.get('tools', [])), "All tools should be compiled"
    
    # Convert bundle to LAP
    bundle_str = bundle.to_lap(lean=True)  # Test lean mode
    assert bundle_str, "Bundle LAP output should not be empty"


def main():
    """Run all compression tests."""
    fixtures_dir = Path(__file__).parent.parent / 'test_fixtures'
    
    if not fixtures_dir.exists():
        print(f"Error: Fixtures directory not found: {fixtures_dir}")
        sys.exit(1)
    
    fixture_files = sorted(fixtures_dir.glob('*.json'))
    
    if not fixture_files:
        print(f"Error: No fixture files found in {fixtures_dir}")
        sys.exit(1)
    
    print(f"\nTesting {len(fixture_files)} MCP server fixtures...")
    print(f"Fixtures directory: {fixtures_dir}")
    
    results = []
    failed = []
    
    for fixture_path in fixture_files:
        try:
            print(f"\n📦 Testing: {fixture_path.name}")
            
            # Test LAP compilation
            test_lap_compilation(fixture_path)
            print("  ✓ LAP compilation passed")
            
            # Test compression
            result = test_fixture_compression(fixture_path)
            results.append(result)
            print(f"  ✓ Compression: {result['ratio']:.1%} reduction")
            
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed.append((fixture_path.name, str(e)))
    
    # Print results table
    print_compression_table(results)
    
    # Print example compressed tool
    if results:
        print("\n" + "=" * 90)
        print("EXAMPLE: Compressed Tool from", results[0]['server'])
        print("=" * 90)
        example_tool = results[0]['manifest']['tools'][0]
        print(json.dumps(example_tool, indent=2))
        print()
    
    # Report failures
    if failed:
        print("\n⚠️  FAILURES:")
        for name, error in failed:
            print(f"  - {name}: {error}")
        sys.exit(1)
    else:
        print("✅ All tests passed!")
        
    # Save compressed manifests for inspection
    output_dir = fixtures_dir.parent / 'compressed_fixtures'
    output_dir.mkdir(exist_ok=True)
    
    for result in results:
        output_path = output_dir / f"{result['server']}_compressed.json"
        output_path.write_text(json.dumps(result['manifest'], indent=2))
    
    print(f"\n💾 Compressed manifests saved to: {output_dir}")


if __name__ == '__main__':
    main()
