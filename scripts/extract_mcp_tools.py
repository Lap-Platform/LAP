#!/usr/bin/env python3
"""
Extract MCP tool definitions from TypeScript source files.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any


def extract_tools_from_ts(source_code: str, server_name: str) -> List[Dict[str, Any]]:
    """Extract tool registrations from TypeScript MCP server source code."""
    tools = []
    
    # Pattern to match server.registerTool calls
    # Matches both single and multi-line tool registrations
    pattern = r'server\.registerTool\s*\(\s*["\']([^"\']+)["\']\s*,\s*\{([^}]+(?:\{[^}]*\})*[^}]*)\}'
    
    matches = re.finditer(pattern, source_code, re.MULTILINE | re.DOTALL)
    
    for match in matches:
        tool_name = match.group(1)
        tool_config = match.group(2)
        
        # Extract description
        desc_match = re.search(r'description:\s*["\']([^"\']+)["\']', tool_config, re.DOTALL)
        description = ""
        if desc_match:
            # Handle multi-line strings with concatenation
            desc_text = desc_match.group(1)
            # Clean up description
            description = desc_text.replace('\\n', ' ').strip()
        else:
            # Try multi-line description with template literals or concatenation
            desc_match = re.search(r'description:\s*["\']([^"\']*(?:[+\n\s]+["\'][^"\']*)*)["\']', tool_config, re.DOTALL)
            if desc_match:
                description = re.sub(r'["\s+]+', ' ', desc_match.group(1)).strip()
        
        # Extract inputSchema
        input_schema = {"type": "object", "properties": {}, "required": []}
        schema_match = re.search(r'inputSchema:\s*\{([^}]+(?:\{[^}]*\})*[^}]*)\}', tool_config, re.DOTALL)
        
        if schema_match:
            schema_text = schema_match.group(1)
            # Try to extract property definitions
            prop_pattern = r'(\w+):\s*z\.(\w+)\(\)\.?([^,}\n]*)'
            props = re.findall(prop_pattern, schema_text)
            
            for prop_name, prop_type, modifiers in props:
                if prop_name in ['type', 'properties', 'required']:
                    continue
                    
                prop_def = {
                    "type": "string" if prop_type == "string" else 
                           "number" if prop_type == "number" else
                           "integer" if prop_type == "int" else
                           "boolean" if prop_type in ["boolean", "bool"] else
                           "array" if prop_type == "array" else
                           "object" if prop_type == "object" else "string"
                }
                
                # Check if optional
                if "optional" not in modifiers and "default" not in modifiers:
                    input_schema["required"].append(prop_name)
                
                # Extract description from modifiers
                desc_in_mod = re.search(r'describe\(["\']([^"\']+)["\']\)', modifiers)
                if desc_in_mod:
                    prop_def["description"] = desc_in_mod.group(1)
                
                # Handle array items
                if prop_type == "array":
                    items_match = re.search(r'z\.(\w+)\(\)', modifiers)
                    if items_match:
                        item_type = items_match.group(1)
                        prop_def["items"] = {
                            "type": "string" if item_type == "string" else
                                   "number" if item_type == "number" else
                                   "object" if item_type == "object" else "string"
                        }
                
                input_schema["properties"][prop_name] = prop_def
        
        if not input_schema["required"]:
            del input_schema["required"]
        
        tool = {
            "name": tool_name,
            "description": description or f"{tool_name.replace('_', ' ').title()}",
            "inputSchema": input_schema
        }
        
        tools.append(tool)
    
    return tools


def main():
    if len(sys.argv) < 3:
        print("Usage: extract_mcp_tools.py <source_file.ts> <output_file.json> [server_name]")
        sys.exit(1)
    
    source_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    server_name = sys.argv[3] if len(sys.argv) > 3 else source_file.stem
    
    if not source_file.exists():
        print(f"Error: Source file {source_file} not found")
        sys.exit(1)
    
    source_code = source_file.read_text()
    tools = extract_tools_from_ts(source_code, server_name)
    
    manifest = {
        "name": server_name,
        "version": "0.1.0",
        "description": f"MCP {server_name} server tools",
        "tools": tools
    }
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(manifest, indent=2))
    
    print(f"✓ Extracted {len(tools)} tools from {server_name}")
    print(f"  Saved to: {output_file}")


if __name__ == "__main__":
    main()
