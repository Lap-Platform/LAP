# LAP - Lean API Platform

## What This Is

LAP compiles API specs (OpenAPI, GraphQL, AsyncAPI, Protobuf, Postman) into LAP -- a token-efficient format for AI agents. Median 2.8x compression across 162 real-world specs.

## Quick Reference

```bash
# Install
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -q

# CLI entry point
lapsh compile examples/verbose/openapi/petstore.yaml -o petstore.lap
```

## Project Structure

- `lap/` -- Top-level Python package (installed as `lap-platform`)
  - `lap/core/compilers/` -- Format-specific compilers (openapi, graphql, asyncapi, protobuf, postman, lap)
  - `lap/core/formats/` -- Data models (LAP v0.2, LAP v0.1)
  - `lap/core/parser.py` -- LAP text to Python objects (proves losslessness)
  - `lap/core/converter.py` -- LAP to OpenAPI roundtrip
  - `lap/core/differ.py` -- Semantic API diff engine
  - `lap/core/utils.py` -- Shared utilities (token counting, file reading)
  - `lap/cli/main.py` -- CLI with 15+ subcommands
- `integrations/` -- LangChain, CrewAI, OpenAI, MCP bridges
- `sdks/python/` -- Python SDK (thin wrapper around lap.core)
- `sdks/typescript/` -- TypeScript/npm SDK (@lap-platform/sdk)
- `tests/` -- pytest suite (11 test files)
- `benchmarks/` -- Skill token benchmarks
- `assets/` -- Chart PNGs for docs
- `examples/verbose/` -- 162 real-world API specs (36MB corpus), organized by format
- `examples/lap/` -- Pre-compiled LAP output, organized by format

## Architecture

```
API Spec (YAML/JSON/SDL/proto)
  -> Format compiler (lap/core/compilers/*.py)
  -> LAP data model (lap/core/formats/*.py)
  -> .to_lap(lean=True/False) text output
  -> Parser (lap/core/parser.py) for roundtrip validation
  -> Converter/Differ for analysis
```

## Tech Stack

- Python 3.10+
- Dependencies: pyyaml, tiktoken, rich (dev)
- Tests: pytest
- Package: setuptools (pyproject.toml)
- License: Apache 2.0

## Key Conventions

- All imports use the `lap` package namespace (e.g., `from lap.core.formats.lap import LAPSpec`)
- Framework integrations handle ImportError gracefully -- no hard deps on LangChain/CrewAI/etc.
- Token counting uses tiktoken with `gpt-4o` model, falls back to `len(text)//4`
- CLI entry point: `lap.cli.main:main`
- Tests run from project root: `python -m pytest tests/ -q`
- All compilers follow the same pattern: take spec input, return format-specific data model, call `.to_lap()`
- All file reads use `encoding='utf-8'` (Windows cp1255 fix)

## Rules

- Run `python -m pytest tests/ -q` and confirm all tests pass before committing
- Keep compression ratios honest -- never discard semantically meaningful information
- LAP format is line-oriented and deterministic -- no ambiguous output
- New compilers must follow existing patterns in `lap/core/compilers/`
- No long dashes in micro-copy (use -- or -)
