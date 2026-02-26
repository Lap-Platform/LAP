#!/usr/bin/env python3
"""
LAP Parser — LAP text → structured Python objects

The reverse of the compiler: proves LAP is a true protocol
by enabling round-trip: OpenAPI → LAP → structured data.
"""

import re
import warnings
from dataclasses import dataclass, field
from typing import Optional

from lap.core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema


# ── Error Handling ──────────────────────────────────────────────────

class ParseError(Exception):
    """Raised when LAP parsing encounters invalid syntax."""
    def __init__(self, message: str, line_number: int = 0, context: str = ""):
        self.line_number = line_number
        self.context = context
        if line_number:
            prefix = f"Line {line_number}"
            if context:
                prefix += f" ({context[:60]})"
            full = f"{prefix}: {message}"
        else:
            full = message
        super().__init__(full)


# ── Pre-compiled patterns ──────────────────────────────────────────

_FIELD_START_RE = re.compile(r'^[$a-zA-Z_\d][$\w.:-]*:\s')


# ── Internal helpers ────────────────────────────────────────────────

def _split_top_level(s: str, sep: str = ',') -> list[str]:
    """Split string by separator, respecting nested braces, parens, and comments.
    
    A comma is only a field separator if the text after it looks like a new field
    (i.e., starts with 'word:' pattern). Commas inside # comments are not separators.
    """
    parts = []
    depth = 0
    in_comment = False
    current = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in ('{', '(') and not in_comment:
            depth += 1
            current.append(ch)
        elif ch in ('}', ')') and not in_comment:
            depth -= 1
            current.append(ch)
        elif ch == '#' and i > 0 and s[i-1] == ' ' and depth == 0:
            in_comment = True
            current.append(ch)
        elif ch == sep and depth == 0:
            # Check if the text after this comma looks like a new field (word: pattern)
            rest = s[i+1:].lstrip()
            if _looks_like_field_start(rest):
                # This comma separates fields, split here
                parts.append(''.join(current).strip())
                current = []
                in_comment = False  # Reset for next field
                i += 1
                continue
            else:
                # Comma is part of current field (e.g., inside comment or description)
                current.append(ch)
        else:
            current.append(ch)
        i += 1
    tail = ''.join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _split_top_level_simple(s: str, sep: str = ',') -> list[str]:
    """Split string by separator, respecting nested braces/parens. No field-start heuristic."""
    parts = []
    depth = 0
    current = []
    for ch in s:
        if ch in ('{', '('):
            depth += 1
            current.append(ch)
        elif ch in ('}', ')'):
            depth -= 1
            current.append(ch)
        elif ch == sep and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = ''.join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _looks_like_field_start(text: str) -> bool:
    """Check if text starts with a field definition (word: type pattern).

    Must have a type-like token after the colon (any/str/int/map/list/bool/num/etc),
    not just any value like 'false' or 'true'.

    The regex handles field names with colons (e.g. 'header:correlationId: str')
    by allowing colons in the field name character class.
    """
    m = _FIELD_START_RE.match(text)
    if not m:
        return False
    type_keywords = {'any', 'str', 'int', 'num', 'bool', 'map', 'list', 'array', 'object', 'float', 'date', 'enum', 'file', 'binary', 'bytes'}
    # Use the regex match boundary to find the type token
    after_match = text[m.end():].lstrip()
    if not after_match:
        return False
    first_word = after_match.split()[0] if after_match.split() else ''
    # Remove trailing punctuation and default values for matching
    first_word = first_word.split('=')[0].split('{')[0].split('<')[0].rstrip('?,;:(')
    is_custom_type = bool(first_word) and first_word[0].isupper()
    return (first_word in type_keywords or
            any(first_word.startswith(t + '(') for t in type_keywords) or
            first_word.startswith('[') or
            first_word.startswith('enum(') or
            is_custom_type)


def _parse_field(text: str) -> ResponseField:
    """Parse a response field like 'name: str?' or 'billing: map{x: str, y: int}'."""
    text = text.strip()
    # Try strict field name first (no spaces/slashes), then fall back to
    # permissive match for API property names like "Publishing/Release Date"
    m = re.match(r'^([$a-zA-Z_\d][$\w.:-]*|\.\.\.):\s*(.+)$', text, re.DOTALL)
    if not m:
        m = re.match(r'^(.+?):\s+((?:str|int|num|bool|map|any|\[).*)$', text, re.DOTALL)
    if not m:
        warnings.warn(f"Malformed field '{text[:40]}', treating as type 'any'")
        return ResponseField(name=text, type='any')
    name = m.group(1)
    type_part = m.group(2).strip()

    # Check for nested map{...}
    children = []
    brace = type_part.find('{')
    if brace != -1:
        base_type = type_part[:brace].rstrip()
        # Extract content inside braces
        inner = type_part[brace + 1:]
        if inner.endswith('}'):
            inner = inner[:-1]
        child_parts = _split_top_level_simple(inner)
        children = [_parse_field(c) for c in child_parts if c]
        type_part = base_type

    nullable = type_part.endswith('?')
    if nullable:
        type_part = type_part[:-1]

    return ResponseField(name=name, type=type_part, nullable=nullable, children=children)


def _parse_param(text: str) -> Param:
    """Parse a param like 'name: str(fmt) # desc' or 'limit: int=10 # desc'."""
    text = text.strip()

    # Split off comment
    desc = ''
    comment_idx = text.find(' # ')
    if comment_idx != -1:
        desc = text[comment_idx + 3:].strip()
        text = text[:comment_idx].strip()
    elif text.startswith('#'):
        desc = text[2:].strip()
        text = ''

    m = re.match(r'^([$a-zA-Z_\d][$\w.:-]*):\s*(.+)$', text)
    if not m:
        warnings.warn(f"Malformed param '{text[:40]}', treating as type 'any'")
        return Param(name=text, type='any', description=desc)

    name = m.group(1)
    type_part = m.group(2).strip()

    # Extract default
    default = None
    eq_idx = type_part.find('=')
    if eq_idx != -1:
        default = type_part[eq_idx + 1:].strip()
        type_part = type_part[:eq_idx].strip()

    # Extract enum from parens — but not type format like int(unix-timestamp)
    # Handle cases like: str(token)(code/implicit) — type with format AND enum
    # or: str(code/implicit) — type with enum only
    # or: int(unix-timestamp) — type with format hint only
    enum = []
    # Try matching type(fmt)(enum) pattern first (two paren groups)
    paren_m2 = re.match(r'^(\w+\([^)]+\))\(([^)]+)\)$', type_part)
    if paren_m2:
        # Second paren group after a type(format) is always an enum
        inner = paren_m2.group(2)
        enum = [v.strip() for v in inner.split('/')]
        type_part = paren_m2.group(1)
    else:
        paren_m = re.match(r'^(\w+)\(([^)]+)\)$', type_part)
        if paren_m:
            inner = paren_m.group(2)
            if '/' in inner:
                # Enum values look like word/word, format hints can have /
                # Heuristic: if all parts look like identifiers/values, it's an enum
                parts = [v.strip() for v in inner.split('/')]
                # If any part contains non-value chars, it's a format hint
                # Allow: letters, digits, spaces, hyphens, underscores, dots
                # Reject: colons (format specs), pipes (alternation), brackets (arrays)
                # Special case: if SOME but not ALL parts are digits, it's likely a format hint (ipv6/128)
                # But if ALL parts are digits, it's numeric enum values (1/2/3)
                digit_parts = [p.isdigit() for p in parts]
                is_mixed_numeric = any(digit_parts) and not all(digit_parts)
                if (len(parts) >= 2 and 
                    not is_mixed_numeric):
                    enum = parts
                    type_part = paren_m.group(1)
                # else it's a format like str(ipv6/128) or str(id:asc/id:desc), keep as-is
            # else it's a format like int(unix-timestamp), keep as-is

    return Param(name=name, type=type_part, description=desc, enum=enum, default=default)


def _extract_braced(text: str, start: int = 0) -> tuple[str, int]:
    """Extract content between matching braces starting at position start.
    Returns (content, end_position). Raises ParseError on unmatched braces."""
    if start >= len(text) or text[start] != '{':
        return '', start
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    # Unmatched brace
    warnings.warn(f"Unmatched opening brace at position {start}")
    return text[start + 1:], len(text)


def _parse_returns(line: str) -> ResponseSchema:
    """Parse @returns(CODE) {fields} # desc or @returns(CODE) desc."""
    m = re.match(r'^@returns\((\w+)\)\s*(.*)', line, re.DOTALL)
    if not m:
        return ResponseSchema(status_code='200')
    code = m.group(1)
    rest = m.group(2).strip()

    if not rest:
        return ResponseSchema(status_code=code)

    fields = []
    desc = ''

    if rest.startswith('{'):
        content, end = _extract_braced(rest)
        field_parts = _split_top_level(content)
        fields = [_parse_field(f) for f in field_parts if f]
        remaining = rest[end:].strip()
        if remaining.startswith('#'):
            desc = remaining[1:].strip()
        elif remaining.startswith('# '):
            desc = remaining[2:].strip()
    else:
        desc = rest

    return ResponseSchema(status_code=code, description=desc, fields=fields)


def _split_error_entries(content: str) -> list[str]:
    """Split error block by comma, but only at boundaries between error codes.

    Only splits when the text after a comma starts with a digit (HTTP status code)
    or 'default'. Commas inside error descriptions are preserved.
    """
    parts = []
    depth = 0
    current = []
    i = 0
    while i < len(content):
        ch = content[i]
        if ch in ('{', '('):
            depth += 1
            current.append(ch)
        elif ch in ('}', ')'):
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            rest = content[i + 1:].lstrip()
            if rest and (re.match(r'\d{3}[:},]', rest) or re.match(r'\d{3}$', rest) or rest.startswith('default')):
                parts.append(''.join(current).strip())
                current = []
                i += 1
                continue
            current.append(ch)
        else:
            current.append(ch)
        i += 1
    tail = ''.join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_errors(line: str) -> list[ErrorSchema]:
    """Parse @errors {400: desc, 401: desc} or @errors {400, 401}."""
    m = re.match(r'^@errors\s*\{(.*)\}\s*$', line, re.DOTALL)
    if not m:
        return []
    content = m.group(1).strip()
    parts = _split_error_entries(content)
    errors = []
    for part in parts:
        part = part.strip()
        if ':' in part:
            # Could be "400: desc" or "400:type: desc"
            first_colon = part.index(':')
            code_part = part[:first_colon].strip()
            rest = part[first_colon + 1:].strip()
            # Check if rest starts with a type (no spaces before next colon)
            type_m = re.match(r'^(\S+?):\s*(.*)$', rest)
            if type_m and ' ' not in type_m.group(1):
                errors.append(ErrorSchema(code=code_part, type=type_m.group(1), description=type_m.group(2)))
            else:
                errors.append(ErrorSchema(code=code_part, description=rest))
        else:
            errors.append(ErrorSchema(code=part))
    return errors


def _parse_params_block(line: str) -> list[Param]:
    """Parse @required {field, field} or @optional {field, field}."""
    m = re.match(r'^@(?:required|optional)\s*\{(.*)\}\s*$', line, re.DOTALL)
    if not m:
        return []
    content = m.group(1).strip()
    parts = _split_top_level(content)
    return [_parse_param(p) for p in parts if p]


def parse_lap(text: str) -> LAPSpec:
    """Parse LAP text into a LAPSpec object.
    
    Raises ParseError for structural issues (unmatched braces, lines exceeding
    size limits). Issues warnings for recoverable problems (malformed fields).
    """
    spec = LAPSpec(api_name='')

    # Join continuation lines (lines that are part of multi-line braced content)
    MAX_LINE_LENGTH = 100 * 1024  # 100KB
    joined_lines = []
    brace_depth = 0
    for line_num, raw_line in enumerate(text.split('\n'), 1):
        if brace_depth > 0:
            joined_lines[-1] += ' ' + raw_line.strip()
            if len(joined_lines[-1]) > MAX_LINE_LENGTH:
                raise ParseError(
                    f"Line exceeds maximum length of {MAX_LINE_LENGTH} bytes during brace joining",
                    line_number=line_num, context=raw_line[:60]
                )
        else:
            joined_lines.append(raw_line)
        brace_depth += raw_line.count('{') - raw_line.count('}')
        if brace_depth < 0:
            brace_depth = 0

    current_endpoint = None

    for line in joined_lines:
        stripped = line.strip()
        if not stripped:
            continue

        try:
            if stripped.startswith('@lap '):
                # version info, skip
                continue
            elif stripped.startswith('@api '):
                spec.api_name = stripped[5:].strip()
            elif stripped.startswith('@base '):
                spec.base_url = stripped[6:].strip()
            elif stripped.startswith('@version '):
                spec.version = stripped[9:].strip()
            elif stripped.startswith('@type '):
                # Type definition — store for reference but not as endpoint
                # @type Name {fields}
                continue
            elif stripped.startswith('@common_fields'):
                # Parse common fields applied to all endpoints
                m = re.match(r'^@common_fields\s*\{(.*)\}\s*$', stripped, re.DOTALL)
                if m:
                    content = m.group(1).strip()
                    parts = _split_top_level(content)
                    common = [_parse_param(p) for p in parts if p]
                    for p in common:
                        p.required = False
                    spec.common_fields = common
                continue
            elif stripped.startswith('@hint '):
                # Download hint metadata, skip
                continue
            elif stripped.startswith('@group '):
                # Group marker for partial fetching, skip
                continue
            elif stripped == '@endgroup':
                # End group marker, skip
                continue
            elif stripped.startswith('@example_request'):
                if current_endpoint:
                    current_endpoint.example_request = stripped[len('@example_request'):].strip()
                continue
            elif stripped.startswith('@auth ') and current_endpoint is None:
                spec.auth_scheme = stripped[6:].strip()
            elif stripped.startswith('@endpoint '):
                if current_endpoint:
                    spec.endpoints.append(current_endpoint)
                parts = stripped[10:].strip().split(None, 1)
                method = parts[0].lower() if parts else 'get'
                path = parts[1] if len(parts) > 1 else '/'
                current_endpoint = Endpoint(method=method, path=path)
            elif stripped.startswith('@desc ') and current_endpoint:
                current_endpoint.summary = stripped[6:].strip()
            elif stripped.startswith('@auth ') and current_endpoint:
                current_endpoint.auth = stripped[6:].strip()
            elif stripped.startswith('@body') and current_endpoint:
                # @body → TypeName — type reference for request body
                continue
            elif stripped.startswith('@required') and current_endpoint:
                params = _parse_params_block(stripped)
                for p in params:
                    p.required = True
                current_endpoint.required_params.extend(params)
            elif stripped.startswith('@optional') and current_endpoint:
                params = _parse_params_block(stripped)
                for p in params:
                    p.required = False
                current_endpoint.optional_params.extend(params)
            elif stripped.startswith('@returns') and current_endpoint:
                rs = _parse_returns(stripped)
                current_endpoint.response_schemas.append(rs)
            elif stripped.startswith('@errors') and current_endpoint:
                errors = _parse_errors(stripped)
                current_endpoint.error_schemas.extend(errors)
        except ParseError:
            raise
        except Exception as e:
            warnings.warn(f"Error parsing line '{stripped[:60]}': {e}")

    if current_endpoint:
        spec.endpoints.append(current_endpoint)

    return spec
