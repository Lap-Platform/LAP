# Contributing to LAP

## How to Add a New API Spec

1. **Find the OpenAPI spec** for the API you want to add. Good sources:
   - [APIs.guru](https://apis.guru/) — large directory of OpenAPI specs
   - The API provider's developer docs (often link to their spec)
   - GitHub repos (search `openapi.yaml` or `swagger.json`)

2. **Add it to `specs/`**:
   ```bash
   cp ~/downloaded-spec.yaml specs/my-api.yaml
   ```

3. **Compile and validate**:
   ```bash
   lapsh compile specs/my-api.yaml -o output/my-api.lap
   lapsh compile specs/my-api.yaml -o output/my-api.lean.lap --lean
   lapsh validate specs/my-api.yaml
   ```

4. **Fix any warnings** — if the compiler emits warnings about malformed fields, the source spec may need cleanup or the compiler may need a fix.

5. **Submit a PR** with:
   - The source spec in `specs/`
   - Both compiled outputs in `output/`
   - Validation passing

## How to Improve the Compiler

The compiler lives in `lap/core/` and consists of:

| File | Purpose |
|------|---------|
| `lap/core/compilers/openapi.py` | OpenAPI → LAP compilation |
| `lap/core/parser.py` | LAP text → AST parsing |
| `lap/core/formats/lap.py` | LAP data structures and serialization |
| `lap/core/converter.py` | LAP → OpenAPI conversion |
| `lap/core/differ.py` | LAP diff engine |
| `lap/core/utils.py` | Token counting, file I/O |

### Common improvements:

- **Better type inference** — improve how OpenAPI schemas map to LAP types
- **Handle edge cases** — polymorphic schemas (`oneOf`/`anyOf`), deeply nested objects
- **Parser robustness** — handle malformed input gracefully
- **New directives** — propose new `@directive` syntax for missing features

### Making changes:

```bash
# Run tests
pytest tests/ -v
pytest integrations/test_integrations.py -v

# Test compilation on all specs
lapsh benchmark-all specs/

# Validate a specific change
lapsh validate specs/stripe-charges.yaml
```

## How to Add a Framework Integration

Integrations live in `integrations/`:

| Path | Framework |
|------|-----------|
| `integrations/langchain/` | LangChain |
| `integrations/crewai/lap_tool.py` | CrewAI |
| `integrations/mcp/lap_mcp_server.py` | MCP |

### Adding a new integration:

1. Create `integrations/<framework>/` with:
   - `__init__.py`
   - Main integration file
   - Example usage

2. **Graceful degradation** — the integration must work without the framework installed (use try/except imports with stubs). See `integrations/crewai/lap_tool.py` for the pattern.

3. **Add tests** in `integrations/test_integrations.py`

4. **Document it** in `docs/guide-integrate.md`

### Integration pattern:

```python
"""<Framework> integration for LAP."""

from lap.core.parser import parse_lap
from lap.core.utils import read_file_safe

# Graceful degradation
try:
    from <framework> import SomeBase
    _HAS_FRAMEWORK = True
except ImportError:
    _HAS_FRAMEWORK = False
    class SomeBase:
        pass

class LAP<Framework>Tool(SomeBase):
    """LAP tool for <Framework>."""

    def __init__(self, specs_dir: str):
        self.specs_dir = Path(specs_dir)

    def _run(self, api_name: str, **kwargs) -> str:
        # Load and return LAP content
        ...
```

## Code Style and Testing

### Style

- Python 3.10+ with type hints
- Dataclasses for data structures
- No external dependencies in core (only `pyyaml`, `tiktoken`, `rich`)
- Framework dependencies are optional (extras)

### Testing

```bash
# All tests
pytest tests/ -v

# Integration tests
pytest integrations/test_integrations.py -v
```

### Test coverage expectations:

- **Compiler** — every spec in `specs/` should compile without errors
- **Parser** — round-trip: compile → parse → serialize should be stable
- **Validator** — 100% endpoint/parameter/error preservation
- **Integrations** — basic load/query tests, with and without framework installed

### PR checklist:

- [ ] Tests pass (`pytest tests/ -v`)
- [ ] All specs still compile (`lapsh benchmark-all specs/`)
- [ ] No new warnings on existing specs
- [ ] Documentation updated if adding features
- [ ] Type hints on public API
