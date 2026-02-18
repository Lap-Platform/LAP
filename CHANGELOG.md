# Changelog

All notable changes to LAP (Lean Agent Protocol) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Initial release of LAP (Lean Agent Protocol)
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
