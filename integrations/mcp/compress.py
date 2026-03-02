"""
MCP Tool Description Compression

Rule-based compression for verbose MCP tool descriptions to reduce token usage
while preserving semantic meaning for LLM agent discovery.
"""

import re
from typing import Dict, List, Any


# Common verbose phrases and their compressed equivalents
COMPRESSION_RULES = [
    # Remove filler phrases (most aggressive first)
    (r'\bThis tool (?:will |can |is used to |enables (?:you|users|LLMs|AI assistants) to |allows (?:you|users|LLMs|AI assistants) to )', r''),
    (r'\bThis server (?:enables|allows|provides)\b', r''),
    (r'\bThis operation (?:will|can)\b', r''),
    (r'\bYou can use this (?:tool |to )\b', r''),
    (r'\bLLMs and agentic applications\b', r'LLMs'),
    (r'\bAI assistants?\b', r'agents'),
    
    # Shorten common patterns
    (r'\bProvides? (?:the )?ability to\b', r''),
    (r'\bProvides? (?:you|users|agents) with\b', r'Provides'),
    (r'\bProvides? access to\b', r'Access'),
    (r'\bGives? (?:you )?access to\b', r'Access'),
    (r'\bmust be provided\b', r'required'),
    (r'\bshould be provided\b', r'recommended'),
    (r'\bcan be used (?:to |for )\b', r'for '),
    (r'\bis useful for\b', r'for'),
    (r'\bis perfect for\b', r'for'),
    (r'\bis essential for\b', r'for'),
    (r'\bis great for\b', r'for'),
    (r'\bHelps you\b', r'Helps'),
    (r'\bEnables you to\b', r''),
    (r'\bAllows you to\b', r''),
    
    # Simplify technical phrases
    (r'\bin order to\b', r'to'),
    (r'\bas well as\b', r'and'),
    (r'\bin the case of\b', r'if'),
    (r'\bprior to\b', r'before'),
    (r'\bsubsequent to\b', r'after'),
    (r'\bwith respect to\b', r'for'),
    (r'\bin accordance with\b', r'per'),
    
    # Remove redundant qualifiers
    (r'\bvery\b', r''),
    (r'\bquite\b', r''),
    (r'\bjust\b', r''),
    (r'\bsimply\b', r''),
    (r'\bbasically\b', r''),
    (r'\bessentially\b', r''),
    (r'\bactually\b', r''),
    
    # Shorten database/API terms
    (r'\brepository\b', r'repo'),
    (r'\bconfiguration\b', r'config'),
    (r'\binformation\b', r'info'),
    (r'\bdocumentation\b', r'docs'),
    (r'\bapplication\b', r'app'),
    (r'\bdatabase\b', r'DB'),
    (r'\benvironment\b', r'env'),
    (r'\bparameters\b', r'params'),
    (r'\bparameter\b', r'param'),
    
    # Shorten operation descriptions
    (r'\bretrieve(?:s)? detailed\b', r'get'),
    (r'\bretrieve(?:s)?\b', r'get'),
    (r'\bfetch(?:es)?\b', r'get'),
    (r'\bobtain(?:s)?\b', r'get'),
    (r'\bprovide(?:s)?\b', r'returns'),
    (r'\bperform(?:s)? a\b', r''),
    (r'\bexecute(?:s)? a\b', r'run'),
    (r'\bexecute(?:s)? an\b', r'run'),
    (r'\bexecute(?:s)?\b', r'run'),
    (r'\bgenerate(?:s)?\b', r'create'),
    (r'\bprogrammatic(?:ally)?\b', r''),
    (r'\binteract(?:ion)? with\b', r'use'),
    (r'\bintegrat(?:e|ion) with\b', r'use'),
    
    # Remove safety warnings and obvious notes (preserve meaning in schema)
    (r'\. ?Use with caution[^.]*\.', r'.'),
    (r'\. ?Exercise extreme caution[^.]*\.', r'.'),
    (r'\. ?Be careful[^.]*\.', r'.'),
    (r'\. ?Note that[^.]*\.', r'.'),
    (r'\. ?Keep in mind[^.]*\.', r'.'),
    (r'\. ?Please note[^.]*\.', r'.'),
    (r'\. ?Important:[^.]*\.', r'.'),
    (r'\bfor example\b', r'e.g.'),
    (r'\bsuch as\b', r'like'),
    (r'\bincluding but not limited to\b', r'including'),
    (r'\band so on\b', r'etc'),
    (r'\band so forth\b', r'etc'),
    
    # Clean up spacing and punctuation
    (r'  +', r' '),  # Multiple spaces
    (r' +([.,;:])', r'\1'),  # Space before punctuation
    (r'([.,;:]) +', r'\1 '),  # Normalize space after punctuation
    (r'^\s+|\s+$', r''),  # Trim
]


def compress_tool_description(desc: str) -> str:
    """
    Apply rule-based compression to a tool description.
    
    Reduces verbosity while preserving semantic meaning:
    - Removes filler phrases and redundant qualifiers
    - Shortens common technical terms
    - Simplifies sentence structure
    - Preserves key information for agent discovery
    
    Args:
        desc: Original tool description
        
    Returns:
        Compressed description
    """
    if not desc or len(desc) < 20:
        return desc
    
    compressed = desc
    
    # Apply compression rules in order
    for pattern, replacement in COMPRESSION_RULES:
        compressed = re.sub(pattern, replacement, compressed, flags=re.IGNORECASE)
    
    # Remove duplicate punctuation
    compressed = re.sub(r'\.+', '.', compressed)
    compressed = re.sub(r',+', ',', compressed)
    
    # Clean up sentences that now start with lowercase after rule application
    compressed = re.sub(r'(\. )([a-z])', lambda m: m.group(1) + m.group(2).upper(), compressed)
    
    # Capitalize first letter
    if compressed and compressed[0].islower():
        compressed = compressed[0].upper() + compressed[1:]
    
    return compressed.strip()


def compress_schema_descriptions(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively compress description fields in a JSON Schema.
    
    Processes:
    - Top-level description
    - Property descriptions
    - Nested object/array item descriptions
    
    Args:
        schema: JSON Schema dict (may be mutated)
        
    Returns:
        The same schema dict with compressed descriptions
    """
    if not isinstance(schema, dict):
        return schema
    
    # Compress top-level description
    if 'description' in schema:
        schema['description'] = compress_tool_description(schema['description'])
    
    # Compress property descriptions
    if 'properties' in schema:
        for prop_name, prop_schema in schema['properties'].items():
            if isinstance(prop_schema, dict):
                compress_schema_descriptions(prop_schema)
    
    # Compress array item descriptions
    if 'items' in schema:
        if isinstance(schema['items'], dict):
            compress_schema_descriptions(schema['items'])
        elif isinstance(schema['items'], list):
            for item in schema['items']:
                if isinstance(item, dict):
                    compress_schema_descriptions(item)
    
    # Handle allOf, anyOf, oneOf
    for key in ['allOf', 'anyOf', 'oneOf']:
        if key in schema and isinstance(schema[key], list):
            for sub_schema in schema[key]:
                if isinstance(sub_schema, dict):
                    compress_schema_descriptions(sub_schema)
    
    return schema


def compress_mcp_tool(tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compress a single MCP tool definition.
    
    Compresses:
    - Tool description
    - Input schema descriptions (recursively)
    
    Args:
        tool: MCP tool dict with name, description, inputSchema
        
    Returns:
        Compressed tool dict (new dict, doesn't mutate input)
    """
    compressed = tool.copy()
    
    # Compress tool description
    if 'description' in compressed:
        compressed['description'] = compress_tool_description(compressed['description'])
    
    # Compress input schema descriptions
    if 'inputSchema' in compressed:
        compressed['inputSchema'] = compress_schema_descriptions(compressed['inputSchema'].copy())
    
    return compressed


def compress_mcp_manifest(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compress a full MCP tools/list response.
    
    Args:
        tools: List of MCP tool definitions
        
    Returns:
        List of compressed tool definitions
    """
    return [compress_mcp_tool(tool) for tool in tools]


def get_compression_stats(original: str, compressed: str) -> Dict[str, Any]:
    """
    Calculate compression statistics.
    
    Args:
        original: Original text
        compressed: Compressed text
        
    Returns:
        Dict with char counts and compression ratio
    """
    orig_len = len(original)
    comp_len = len(compressed)
    ratio = (orig_len - comp_len) / orig_len if orig_len > 0 else 0.0
    
    return {
        'original_chars': orig_len,
        'compressed_chars': comp_len,
        'saved_chars': orig_len - comp_len,
        'compression_ratio': ratio,
        'compression_pct': ratio * 100,
    }
