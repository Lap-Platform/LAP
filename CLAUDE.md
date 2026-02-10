# LAP - Lean Agent Protocol

## What This Is

LAP compiles API specs (OpenAPI, GraphQL, AsyncAPI, Protobuf, Postman) into DocLean -- a token-efficient format for AI agents. Median 2.8x compression across 162 real-world specs.

## Quick Reference

```bash
# Install
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -q

# CLI entry point
lap compile examples/verbose/openapi/petstore.yaml -o petstore.doclean
```

## Project Structure

- `core/compilers/` -- Format-specific compilers (openapi, graphql, asyncapi, protobuf, postman, toollean)
- `core/formats/` -- Data models (DocLean v0.2, ToolLean v0.1)
- `core/parser.py` -- DocLean text to Python objects (proves losslessness)
- `core/converter.py` -- DocLean to OpenAPI roundtrip
- `core/differ.py` -- Semantic API diff engine
- `core/utils.py` -- Shared utilities (token counting, file reading)
- `cli/main.py` -- CLI with 15+ subcommands
- `integrations/` -- LangChain, CrewAI, OpenAI, MCP bridges
- `sdks/python/` -- Python SDK
- `tests/` -- pytest suite (11 test files)
- `benchmarks/` -- Compression validation
- `examples/verbose/` -- 162 real-world API specs (36MB corpus), organized by format
- `examples/doclean/` -- Pre-compiled DocLean output, organized by format

## Architecture

```
API Spec (YAML/JSON/SDL/proto)
  -> Format compiler (core/compilers/*.py)
  -> DocLean/ToolLean data model (core/formats/*.py)
  -> .to_doclean(lean=True/False) text output
  -> Parser (core/parser.py) for roundtrip validation
  -> Converter/Differ for analysis
```

## Tech Stack

- Python 3.10+
- Dependencies: pyyaml, tiktoken, rich (dev)
- Tests: pytest
- Package: setuptools (pyproject.toml)
- License: Apache 2.0

## Key Conventions

- All imports are relative to project root (e.g., `from core.formats.doclean import DocLeanSpec`)
- Framework integrations handle ImportError gracefully -- no hard deps on LangChain/CrewAI/etc.
- Token counting uses tiktoken with `gpt-4o` model, falls back to `len(text)//4`
- CLI entry point: `cli.main:main`
- Tests run from project root: `python -m pytest tests/ -q`
- All compilers follow the same pattern: take spec input, return format-specific data model, call `.to_doclean()`

## Rules

- Run `python -m pytest tests/ -q` and confirm all tests pass before committing
- Keep compression ratios honest -- never discard semantically meaningful information
- DocLean format is line-oriented and deterministic -- no ambiguous output
- New compilers must follow existing patterns in `core/compilers/`
- No long dashes in micro-copy (use -- or -)
