# Changelog

All notable changes to LAP (Lean API Platform) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2026-03-19

### Fixed
- **Hook instruction clarity** -- CLAUDE.md and Cursor rule now explicitly tell agents to include diff and pin commands in skill update notifications
- **Cursor rule instruction** -- aligned with CLAUDE.md instruction wording

## [0.6.0] - 2026-03-19

### Added
- **Automatic skill update checking** -- SessionStart hook runs `lapsh check` on every new conversation, notifying users of available skill updates
- **Hook installation** -- `lapsh init` registers a SessionStart hook in `.claude/settings.json` or `.cursor/hooks.json` (idempotent, preserves existing hooks)
- **CLAUDE.md instruction injection** -- `lapsh init` adds a marker-based instruction block to `~/.claude/CLAUDE.md` telling agents to present update notifications
- **Cursor update rule** -- `lapsh init --target cursor` creates an always-apply rule in `~/.cursor/rules/lap-updates.mdc`

## [0.5.3] - 2026-03-18

### Added
- **`lapsh check` command** -- check installed skills for available updates via batch registry API
- **`lapsh pin/unpin` commands** -- pin skills to skip update checks, unpin to resume
- **`lapsh diff` command** -- diff installed spec vs registry latest, or two local LAP files
- **`[community]` badge** in CLI search output for community-contributed specs (Python and TypeScript)
- **TypeScript SDK CI** -- added Node 18/20 test matrix in GitHub Actions, npm publish now requires tests to pass

### Changed
- **Search scoring** -- registry now scores against provider_slug and provider_domain fields, fixing queries like `discord.com` that previously returned no results
- **Search weights** -- tuned scoring: name 1.0, provider slug 0.85, provider domain 0.7, description 0.7, threshold raised from 0.2 to 0.3
- **fuzzyScore** -- added empty-string guard to avoid unnecessary computation on specs with missing provider fields

## [0.5.0] - 2026-03-18

### Added
- **`lapsh init` command** -- set up LAP in your IDE with one command. Auto-installs the bundled LAP skill to the correct directory
- **Cursor IDE support** -- `--target cursor` flag for `skill`, `skill-batch`, `skill-install`, and `init` commands. Generates `.mdc` files with Cursor-specific frontmatter
- **IDE auto-detection** -- `detect_target()` checks TERM_PROGRAM, CURSOR_TRACE_ID, PATH, project directories, and home directory to auto-detect Claude vs Cursor
- **`--version` flag** for both Python and TypeScript CLIs
- **Full TypeScript SDK compiler parity** -- all 6 compilers (AsyncAPI, GraphQL, Postman, Protobuf, AWS SDK, Smithy) now available in TypeScript with comprehensive tests
- **Cursor skill rule** (`skills/cursor/lap.mdc`) -- dedicated skill file for Cursor with `skill-install --target cursor` instructions
- **CLI section in generated skills** -- every generated skill now includes a `## CLI` section with npx commands for updating and searching

### Changed
- `skill-install` now fetches LAP spec from registry and generates skills locally (instead of downloading pre-built bundles), enabling target-aware output
- `SkillOutput` now includes `main_file` field -- callers use `skill.file_map[skill.main_file]` instead of hardcoded `"SKILL.md"`
- Improved `_slugify()` to handle `/` and `.` characters
- Reduced integration test corpus from 29 to 8 representative specs (test suite runs 4x faster)
- `replaceSection()` in TypeScript now preserves original section name instead of hardcoding "Enhanced Skill Content"

### Fixed
- **HTML tag leakage in @desc fields** -- descriptions from upstream API specs were leaking raw HTML tags and entities into compiled LAP output
- **Missing `Path` import** in `skill.py` -- `detect_target()` would crash at runtime
- **Home directory validation** -- Cursor target path in TypeScript `cmdInit` no longer silently uses empty string when HOME/USERPROFILE are unset
- **Security**: Smithy compiler uses `execFileSync` instead of `execSync` to prevent command injection

## [0.4.8] - 2026-03-16

### Fixed
- **HTML tag leakage in @desc fields**: Descriptions from upstream API specs (Etsy, eBay, AWS, Stripe, Azure, etc.) were leaking raw HTML tags and entities into compiled LAP output
- Move `_strip_html` to shared `strip_html` in `utils.py` with `html.unescape()` to handle both raw tags and HTML entities (`&lt;`, `&gt;`, etc.)
- Apply HTML stripping to all compilers: TypeScript OpenAPI, Python Postman, and Python Smithy (previously only Python OpenAPI had it)

### Added
- HTML entity decoding tests for the shared `strip_html` utility
- Postman compiler HTML stripping tests
- TypeScript OpenAPI HTML stripping tests (params, summaries, responses, request body, entities)

## [0.4.7] - 2026-03-12

### Added
- **`lapsh get <name>`**: Download a LAP spec from the registry by name
  - Supports `-o` for file output and `--lean` for lean variant
  - Available in both Python and TypeScript CLIs
- **Provider domain in search output**: Text search results now show the provider domain (e.g. `stripe.com`) as a column between name and endpoints
- **`url` field in JSON search results**: Each result now includes the full registry URL for fetching the spec

### Fixed
- Add `User-Agent` header to `get` command to prevent Cloudflare 403 errors

## [0.4.6] - 2026-03-12

### Fixed
- Wire up `search` command in TypeScript CLI (was missing from dispatcher)
- TS CLI now supports: `lapsh search <query> [--tag] [--sort] [--limit] [--offset] [--json]`

## [0.4.5] - 2026-03-12

### Added
- **Registry search**: `lapsh search <query>` -- search the LAP registry for APIs
  - Supports `--tag`, `--sort`, `--limit`, `--offset`, `--json` flags
  - Output sanitization against ANSI injection from server responses
  - Pagination hints when more results available
- **TypeScript SDK search**: `LAPClient.search()` method for registry search
- **Search test coverage**: 64 Python tests + 6 TypeScript tests

### Fixed
- TS SDK `fromRegistry()` used wrong URL path (`/specs/` -> `/v1/apis/`)
- TypeScript SDK `SearchResponse` type and parser exports

## [0.4.3] - 2026-03-10

_Skipped -- internal build number consumed during development; no public release._

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
