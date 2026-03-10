# Changelog

All notable changes to LAP (Lean API Platform) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2] - 2026-03-10

### Fixed
- Add User-Agent header to registry API requests to prevent blocked skill installs

## [0.4.1] - 2026-03-09

### Changed
- Default skill generation no longer auto-detects L2 (AI-enhanced). Defaults to L1 (mechanical). Use `--ai` to opt in.

## [0.4.0] - 2026-03-04

### Added
- **AWS SDK JSON compiler**: Compile AWS SDK service definitions (~300 AWS services)
  - Auto-detection integrated into `detect_format()` and `compile()` pipeline
  - Maps operations, shapes, auth, and metadata to LAP format
- **Skill generation** (Layer 1 + Layer 2)
  - `lapsh skill <spec>` -- generate a Claude Code skill from any API spec
  - `lapsh skill-batch <dir>` -- batch generate skills from a directory
  - `lapsh benchmark-skill` / `benchmark-skill-all` -- token usage benchmarks
  - Layer 1: mechanical generation (no LLM), Layer 2: optional LLM enhancement
  - 3000-token budget per skill, generates SKILL.md + embedded LAP spec
- **TypeScript SDK expansion**: OpenAPI compiler, serializer, and skill compiler ported to TypeScript
- **YAML compatibility module** (`yaml_compat.py`): handles bare `=` tags, restricts booleans to true/false, tolerates unknown tags
- **Auth inference from descriptions**: last-resort auth detection by scanning `info.description` for auth keywords

### Changed
- Consolidated shared code to `utils.py` -- `AUTH_PARAM_NAMES`, `AUTH_DESC_KEYWORDS`, `resolve_ref()` extracted from duplicate implementations across compilers
- Removed dead `main()` / `if __name__` blocks from compiler modules
- `graphql-core` promoted from optional to required dependency
- Response schema depth increased from 2 to 3 levels, inline depth from 1 to 2
- Auth param set updated: removed false-positive-prone bare "key", added Azure subscription-key variants and `x-auth-token`
- All asset images updated to 300 DPI

### Fixed
- Swagger 2.0 `securityDefinitions` not recognized; `host`/`basePath` extraction for base URL
- HTTP auth scheme "basic" producing "Bearer basic" instead of "Basic"
- HTML tags leaking into compiled descriptions (now stripped)
- `tiktoken` errors on special tokens (`disallowed_special=()`)
- "API API" doubling in skill descriptions when api_name ends with "API"
- Hardened all compilers (OpenAPI, AsyncAPI, Postman, Skill) against malformed specs: type arrays, missing param names, cycle detection in $ref resolution
- YAML 1.1 edge cases: bare `=` value tag, YES/NO/ON/OFF boolean false positives

## [0.3.0] - 2026-02-27

### Added
- Skill version override and API version surfaced in body
- GitHub Actions workflows for PyPI and npm publishing
- TypeScript SDK published as `@lap-platform/lapsh`
- Expanded README with concrete compression examples

### Changed
- CLI entry point renamed to `lapsh`
- All package versions aligned to 0.3.0

### Fixed
- Parser roundtrip failures for complex specs
- CLI unicode output on Windows (cp1255)

## [0.2.0] - 2026-02-13

### Added
- **AWS Smithy support**: Complete implementation of Smithy IDL compiler
  - Accepts Smithy JSON AST files (`.json`)
  - Accepts Smithy IDL files (`.smithy`) via Smithy CLI
  - Accepts Smithy project directories with `smithy-build.json`
  - Format auto-detection for Smithy specs
  - Full HTTP binding extraction (@http, @httpLabel, @httpQuery, @httpHeader)
  - Complete type system support (scalars, collections, structures, enums, maps)
  - Auth scheme mapping (AWS SigV4, Bearer, ApiKey, HTTP Basic)
  - Response and error schema generation
  - 60 comprehensive tests with 100% pass rate
- Example Weather service in Smithy format (`examples/verbose/smithy/weather.json`)
- Smithy implementation documentation (`docs/smithy-implementation-summary.md`)

### Changed
- Updated format detection in `core/compilers/__init__.py` to include Smithy
- Updated CLI format choices to include "smithy"
- Enhanced compiler infrastructure to support protocol-agnostic IDLs

### Technical Details
- No new dependencies required (uses stdlib only)
- Optional Smithy CLI for `.smithy` file conversion
- Maintains backward compatibility with all existing formats
- Compression ratio: ~2.3x (standard), ~2.9x (lean) for Smithy specs

## [0.1.0] - 2025-01-15

### Added
- Initial release of LAP (Lean API Platform)
- Support for OpenAPI/Swagger specs
- Support for GraphQL schemas (SDL and introspection JSON)
- Support for AsyncAPI specs
- Support for Protocol Buffers (.proto files)
- Support for Postman collections
- CLI with compile, validate, convert, diff, and benchmark commands
- LAP format v0.3 with @common_fields directive
- Token counting and compression metrics
- Integration with LangChain, CrewAI, OpenAI
- Python SDK
- Comprehensive test suite (800+ tests)
