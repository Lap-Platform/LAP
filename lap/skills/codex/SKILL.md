---
name: lap
description: "LAP CLI -- compile, search, and manage API specs for AI agents. Use when working with API specifications (OpenAPI, GraphQL, AsyncAPI, Protobuf, Postman), compiling specs to LAP format, searching the LAP registry, generating skills from API specs, or publishing APIs. Commands: init, compile, search, get, skill, skill-install, skill-batch, publish, login, logout, whoami."
user-invocable: true
version: 1.0.0
metadata:
  openclaw:
    emoji: "\u26A1"
    requires:
      anyBins: ["curl", "npx", "lapsh"]
    install:
      - id: node
        kind: node
        package: "@lap-platform/lapsh"
        bins: ["lapsh"]
        label: "Install LAP CLI (npm)"
---

# LAP CLI

Compile, search, and manage API specs for AI agents.

## Command Resolution

IMPORTANT: Always use curl for registry operations (search, get, check). Do NOT use npx for these -- it downloads the package every time and takes minutes. curl is instant.

```bash
# Search the registry
curl -s 'https://registry.lap.sh/v1/search?q=<query>'

# Download a spec
curl -sH 'Accept: text/lap' https://registry.lap.sh/v1/apis/<name> -o <name>.lap

# Get API metadata (version, endpoint count)
curl -sH 'Accept: application/json' https://registry.lap.sh/v1/apis/<name>
```

Only use the CLI (`lapsh` or `npx @lap-platform/lapsh`) for operations that require it: compile, publish, skill-install, init.

---

## Agent Flow -- Consuming APIs

Use this flow when a user needs to find, download, or work with an API.

### 1. Discover

**Option A -- curl (fastest)**:
```bash
curl -s 'https://registry.lap.sh/v1/search?q=<query>'
```

**Option B -- CLI**:
```bash
lapsh search <query> [--tag <tag>] [--sort relevance|popularity|date] [--limit <n>]
```

Results show name, endpoint count, compression ratio, and a `[skill]` marker for installable skills.

### 2. Acquire

**Option A -- curl (fastest)**:
```bash
curl -sH 'Accept: text/lap' https://registry.lap.sh/v1/apis/<name> -o <name>.lap
```

**Option B -- Install a skill** (if `[skill]` marker present):
```bash
lapsh skill-install <name> --target codex
# Installs to ~/.codex/skills/<name>/
```

**Option C -- Download via CLI**:
```bash
lapsh get <name> -o <name>.lap
lapsh get <name> --lean -o <name>.lean.lap
```

**Option D -- Compile a local spec**:
```bash
lapsh compile <spec-file> -o output.lap
lapsh compile <spec-file> -o output.lean.lap --lean
```

Supported formats: OpenAPI (YAML/JSON), GraphQL (SDL), AsyncAPI, Protobuf, Postman, Smithy. Format is auto-detected.

### 3. Use

Once you have a `.lap` file, read it directly -- LAP is designed for AI consumption. Key markers:

| Marker | Meaning |
|--------|---------|
| `@api` | API name, version, base URL |
| `@endpoint` | HTTP method + path |
| `@param` | Parameter (query, path, header) |
| `@body` | Request body schema |
| `@response` | Response status + schema |
| `@required` | Required fields |
| `@error` | Error response |

---

## Publisher Flow -- Publishing APIs

Use this flow when a user wants to compile, package, and publish an API spec.

### 1. Authenticate

```bash
lapsh login
lapsh whoami        # verify
```

### 2. Compile

```bash
lapsh compile spec.yaml -o spec.lap
lapsh compile spec.yaml -o spec.lean.lap --lean
```

### 3. Generate Skill

```bash
# Basic skill (Layer 1 -- mechanical)
lapsh skill spec.yaml -o skills/ --no-ai

# AI-enhanced skill (Layer 2 -- requires claude CLI)
lapsh skill spec.yaml -o skills/ --ai

# Generate and install directly
lapsh skill spec.yaml --install
```

### 4. Publish

```bash
lapsh publish spec.yaml --provider stripe.com
lapsh publish spec.yaml --provider stripe.com --name charges --source-url https://...
lapsh publish spec.yaml --provider stripe.com --skill          # include skill
lapsh publish spec.yaml --provider stripe.com --skill --skill-ai  # with AI skill
```

### 5. Verify

```bash
lapsh search <name>   # confirm it appears in registry
```

### 6. Batch Operations

```bash
# Generate skills for all specs in a directory
lapsh skill-batch specs/ -o skills/

```

---

## Quick Reference

### Core Commands

| Command | Description |
|---------|-------------|
| `compile <spec>` | Compile API spec to LAP format |

### Registry Commands

| Command | Description |
|---------|-------------|
| `search <query>` | Search the LAP registry |
| `get <name>` | Download a LAP spec |
| `publish <spec>` | Compile and publish to registry |
| `login` | Authenticate via GitHub OAuth |
| `logout` | Revoke token |
| `whoami` | Show authenticated user |

### Setup

| Command | Description |
|---------|-------------|
| `init --target codex` | Set up LAP for Codex CLI |
| `init --target cursor` | Set up LAP for Cursor |

### Skill Commands

| Command | Description |
|---------|-------------|
| `skill <spec>` | Generate Codex CLI skill from spec |
| `skill-batch <dir>` | Batch generate skills |
| `skill-install <name> --target codex` | Install skill from registry to Codex CLI |

---

## Error Recovery

| Problem | Fix |
|---------|-----|
| `command not found: lapsh` | `npm install -g @lap-platform/lapsh` or use `npx @lap-platform/lapsh` |
| `Not authenticated` | Run `lapsh login` first |
| `Format detection failed` | Pass `-f openapi` (or graphql, asyncapi, protobuf, postman, smithy) |
| `403 Forbidden` on get | Spec may be private or registry may block without User-Agent -- update lapsh |
| `YAML parse error` | Check spec is valid YAML/JSON -- use a linter first |
| `Layer 2 requires claude` | Install Claude CLI or use `--no-ai` for Layer 1 skills |
| `Provider required` | `publish` needs `--provider <domain>` (e.g., `--provider stripe.com`) |

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LAP_REGISTRY` | Override registry URL | `https://registry.lap.sh` |

---

## References

- [{baseDir}/references/agent-flow.md](references/agent-flow.md) -- Extended agent workflow with examples
- [{baseDir}/references/publisher-flow.md](references/publisher-flow.md) -- Extended publisher workflow with examples
- [{baseDir}/references/command-reference.md](references/command-reference.md) -- Complete command reference with all flags
