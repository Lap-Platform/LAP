# LAP Security Audit Report

**Date:** 2026-02-08  
**Auditor:** Automated Security Review  
**Scope:** All Python files in src/, benchmarks/, sdk/, cli.py, demo.py, tests/

---

## Executive Summary

The LAP project is a **read-only data transformation pipeline** (OpenAPI ↔ LAP ↔ structured data). It has no network servers, no authentication handling, no database, and no user-facing web interface. The attack surface is therefore **relatively narrow** — primarily limited to malicious input files and path manipulation.

**Critical issues found: 0**  
**High issues found: 2**  
**Medium issues found: 5**  
**Low issues found: 6**

---

## Findings

### HIGH-1: Path Traversal in CLI File Operations

**Severity:** HIGH  
**Files:** `cli.py` (cmd_compile, cmd_convert, cmd_inspect, cmd_registry_list, cmd_registry_search), `src/converter.py` (convert_file), `src/compiler.py` (compile_openapi)  

**Description:** User-supplied file paths from CLI arguments are passed directly to `Path().read_text()` and `Path().write_text()` without any sanitization or containment. While this is a CLI tool (where the user already has shell access), if the CLI is ever wrapped in a web service or used as a library, arbitrary file read/write is possible.

Key patterns:
```python
# cli.py
Path(args.output).write_text(result)  # writes anywhere
Path(spec_path).read_text()           # reads anywhere

# converter.py
Path(input_path).read_text()
Path(output_path).write_text(result)
```

The `cmd_compile` function creates parent directories for output: `Path(args.output).parent.mkdir(parents=True, exist_ok=True)` — an attacker could write to arbitrary locations like `/etc/cron.d/evil`.

**Recommendation:** If ever used outside direct CLI context, add path validation/sandboxing. For a CLI-only tool, this is acceptable but should be documented.

---

### HIGH-2: ReDoS and Unbounded Recursion in Parser

**Severity:** HIGH  
**Files:** `src/parser.py`, `src/compiler.py`

**Description:** Several attack vectors via malicious LAP or OpenAPI input:

1. **`_split_top_level` in parser.py** — O(n²) behavior on deeply nested braces. A string with thousands of nested `{{{...}}}` will cause excessive CPU usage.

2. **`extract_response_fields` in compiler.py** — Recursive with `max_depth=2`, which limits depth but does NOT limit breadth. A schema with 100,000 properties at depth 0 will be fully processed.

3. **`resolve_ref` in compiler.py** — Follows `$ref` pointers without cycle detection. A circular `$ref` chain (`A → B → A`) will cause infinite recursion and stack overflow:
   ```yaml
   components:
     schemas:
       A:
         $ref: '#/components/schemas/B'
       B:
         $ref: '#/components/schemas/A'
   ```

4. **Brace joining in `parse_lap`** — The line-joining loop that tracks `brace_depth` will concatenate an entire file into one line if braces never balance, causing memory issues.

**Recommendation:**
- Add cycle detection to `resolve_ref` (track visited refs)
- Add maximum property count limits in `extract_response_fields`
- Add maximum line length limits in the parser's brace-joining loop

---

### MEDIUM-1: `__import__()` Usage in Converter

**Severity:** MEDIUM  
**Files:** `src/converter.py` (lines 25, 100)

**Description:** Uses `__import__('re')` inline instead of a top-level import. While not exploitable (the module name is hardcoded), this is an anti-pattern that obscures dependencies and could mask import-injection in a compromised environment.

```python
m = __import__('re').match(r'^(\w+)\(([^)]+)\)$', type_str)
```

**Recommendation:** Replace with top-level `import re`.

---

### MEDIUM-2: Unvalidated YAML Deserialization

**Severity:** MEDIUM  
**Files:** `src/compiler.py`, `benchmarks/validate.py`, `benchmarks/agent_test.py`, `benchmarks/benchmark.py`

**Description:** All YAML loading uses `yaml.safe_load()` — **this is correct and good**. However, there is no validation of the loaded structure. A YAML file that parses as a string or integer instead of a dict will cause `AttributeError` crashes:

```python
spec = yaml.safe_load(raw)
# If spec is a string, next line crashes:
info = spec.get("info", {})  
```

No `yaml.load()` (unsafe) was found anywhere. ✅

**Recommendation:** Add type checking after YAML load: `if not isinstance(spec, dict): raise ValueError(...)`.

---

### MEDIUM-3: Information Leakage via OpenAI API Key

**Severity:** MEDIUM  
**Files:** `benchmarks/validate.py` (validate_agent_task), `benchmarks/agent_test.py` (call_llm)

**Description:** The `OPENAI_API_KEY` is read from environment and passed directly to API calls. In `agent_test.py`, it's also accepted as a CLI argument (`--api-key`), which means it appears in process listings (`ps aux`).

```python
# validate.py
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# agent_test.py  
parser.add_argument("--api-key", help="OpenAI API key")
headers={"Authorization": f"Bearer {api_key}", ...}
```

Additionally, `agent_test.py` saves full LLM responses to `output/agent_results.json` which could contain sensitive data from the API responses.

**Recommendation:** Remove `--api-key` CLI flag, use env vars only. Add warning about sensitive data in output files.

---

### MEDIUM-4: Subprocess Calls Without Shell=False Verification

**Severity:** MEDIUM  
**File:** `tests/test_integration.py`

**Description:** Uses `subprocess.run()` with list arguments (not shell=True), which is the safe pattern. However, file paths from `SPECS_DIR` and `CLI` are interpolated without sanitization. Since these are test files with hardcoded paths, risk is low.

```python
result = subprocess.run(
    [sys.executable, CLI, 'compile', str(SPECS_DIR / 'stripe-charges.yaml')],
    capture_output=True, text=True
)
```

**Recommendation:** No action needed — pattern is already safe (list args, no shell=True).

---

### MEDIUM-5: A2A-Lean Execute Intent Passes Through Arbitrary Commands

**Severity:** MEDIUM  
**File:** `src/a2a_lean.py`

**Description:** The A2A-Lean compiler parses natural language into structured intents, including an `execute` intent that captures arbitrary command strings:

```python
@_pat(r"(?:run|execute)\s+(?:the\s+)?(?:command\s+)?['\"](.+?)['\"]\s*(?:on\s+(\S+))?")
def _execute(m):
    params = {"command": m.group(1)}
```

While this module only **compiles** NL to structured data (it never executes anything), any downstream consumer that blindly executes the `command` field would be vulnerable to command injection. The decompiler also faithfully reconstructs: `Run the command "{command}"`.

**Recommendation:** Document that consumers MUST NOT execute the `command` parameter without sanitization. Consider adding a warning field or validation.

---

### LOW-1: sys.path Manipulation Throughout Codebase

**Severity:** LOW  
**Files:** `cli.py`, `demo.py`, `benchmarks/*.py`, `sdk/python/lap/client.py`, `sdk/python/examples/*.py`

**Description:** Extensive use of `sys.path.insert(0, ...)` to resolve imports. While functional, this can be exploited if an attacker can place a malicious Python file in one of the inserted paths (e.g., a `compiler.py` in the current directory).

```python
sys.path.insert(0, str(Path(__file__).parent / "src"))
```

**Recommendation:** Use proper package structure with `setup.py`/`pyproject.toml` and relative imports.

---

### LOW-2: No Input Size Limits

**Severity:** LOW  
**Files:** All file-reading code

**Description:** No limits on input file sizes. A 10GB YAML file will be read entirely into memory:

```python
raw = path.read_text()  # unbounded
```

**Recommendation:** Add file size checks before reading (e.g., `if path.stat().st_size > MAX_SIZE: raise`).

---

### LOW-3: Regex Complexity in A2A-Lean Patterns

**Severity:** LOW  
**File:** `src/a2a_lean.py`

**Description:** The `compile_nl` function iterates through all registered regex patterns on every input. With 15+ patterns using `re.DOTALL` and `re.IGNORECASE`, a carefully crafted input could cause polynomial-time matching (ReDoS). The patterns use `(.+?)` which is generally safe, but combined with alternation and backtracking could be slow on adversarial input.

**Recommendation:** Add timeout or input length limits for NL compilation.

---

### LOW-4: Error Messages May Leak File Paths

**Severity:** LOW  
**File:** `cli.py`

**Description:** Error messages include full file paths which could reveal directory structure:

```python
error(f"File not found: {spec_path}")
```

**Recommendation:** Acceptable for a CLI tool. If wrapped in a service, sanitize error messages.

---

### LOW-5: No Integrity Verification of LAP Files

**Severity:** LOW  
**Files:** `sdk/python/lap/client.py`, `src/parser.py`

**Description:** LAP files are loaded and parsed without any integrity verification (checksums, signatures). A tampered LAP file could provide incorrect API documentation to agents, causing them to make wrong API calls (parameter injection, wrong endpoints, etc.).

**Recommendation:** Consider adding an optional `@checksum` directive to LAP format for integrity verification.

---

### LOW-6: Demo Hardcodes Model Pricing

**Severity:** LOW  
**Files:** `demo.py`, `benchmarks/benchmark.py`, `benchmarks/report.py`

**Description:** Model pricing is hardcoded and will become stale. Not a security issue per se, but misleading data could affect business decisions.

**Recommendation:** Load pricing from a config file or add last-updated dates.

---

## Positive Findings ✅

1. **YAML deserialization is safe** — `yaml.safe_load()` used consistently everywhere. No `yaml.load()` found.
2. **No eval/exec** — No use of `eval()` or `exec()` in any production code.
3. **No network listeners** — The project has no HTTP servers, WebSocket endpoints, or network services.
4. **No database** — No SQL injection surface.
5. **No secrets in code** — API keys read from environment only (except the `--api-key` CLI flag noted above).
6. **subprocess usage is safe** — Uses list arguments, never `shell=True`.
7. **No pickle/marshal** — No unsafe deserialization.
8. **Compiler has max_depth limit** — `extract_response_fields` limits recursion to depth 2.

---

## Risk Summary

| ID | Severity | Category | Description |
|----|----------|----------|-------------|
| HIGH-1 | HIGH | Path Traversal | CLI accepts arbitrary file paths for read/write |
| HIGH-2 | HIGH | DoS | Circular $ref, unbounded breadth, brace-joining DoS |
| MEDIUM-1 | MEDIUM | Code Quality | `__import__()` usage |
| MEDIUM-2 | MEDIUM | Input Validation | No type check after YAML parse |
| MEDIUM-3 | MEDIUM | Info Leakage | API key in CLI args, sensitive data in output |
| MEDIUM-4 | MEDIUM | Subprocess | Safe pattern, no action needed |
| MEDIUM-5 | MEDIUM | Protocol | Execute intent passes arbitrary commands |
| LOW-1 | LOW | Code Quality | sys.path manipulation |
| LOW-2 | LOW | DoS | No file size limits |
| LOW-3 | LOW | DoS | Regex complexity in NL patterns |
| LOW-4 | LOW | Info Leakage | File paths in error messages |
| LOW-5 | LOW | Integrity | No LAP file verification |
| LOW-6 | LOW | Data Quality | Hardcoded pricing |

---

## Overall Assessment

**Risk Level: LOW-MODERATE**

This is a well-structured CLI/library tool with a narrow attack surface. The main risks are:
1. **If used as a library in a web service** — path traversal and DoS via malicious input become real concerns
2. **Circular $ref in OpenAPI specs** — the most exploitable bug, causing stack overflow
3. **Unbounded input processing** — no size limits anywhere

For its current use case (developer CLI tool), the codebase is reasonably secure. The recommendations above are primarily defensive hardening for future use cases.
