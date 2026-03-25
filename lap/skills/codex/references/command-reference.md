# LAP CLI -- Command Reference

Complete reference for all LAP CLI commands and flags.

All commands are available via `npx @lap-platform/lapsh` or a global `lapsh` install.

---

## Core Commands

### compile

Compile any API spec to LAP format. Auto-detects input format.

```
lapsh compile <spec> [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `-o, --output <path>` | string | Output file path (default: stdout) |
| `-f, --format <fmt>` | string | Force input format: `openapi`, `graphql`, `asyncapi`, `protobuf`, `postman`, `smithy` |
| `--lean` | boolean | Maximum compression -- strips descriptions |

**Examples:**

```bash
# Auto-detect format, write to file
lapsh compile petstore.yaml -o petstore.lap

# Lean mode
lapsh compile petstore.yaml -o petstore.lean.lap --lean

# Force format
lapsh compile spec.json -f openapi -o spec.lap
```

---

## Registry Commands

### search

Search the LAP registry for APIs. No authentication required.

```
lapsh search <query> [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `--tag <tag>` | string | Filter by tag |
| `--sort <field>` | string | Sort by: `relevance`, `popularity`, `date` |
| `--limit <n>` | number | Maximum results (default: 50) |
| `--offset <n>` | number | Pagination offset |
| `--json` | boolean | Output raw JSON |

**Examples:**

```bash
lapsh search payment
lapsh search stripe --sort popularity
lapsh search api --tag fintech --limit 10
lapsh search payment --json | jq '.results[].name'
```

---

### get

Download a LAP spec from the registry.

```
lapsh get <name> [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `-o, --output <path>` | string | Output file path (default: stdout) |
| `--lean` | boolean | Download lean variant |

**Examples:**

```bash
lapsh get stripe -o stripe.lap
lapsh get stripe --lean -o stripe.lean.lap
```

---

### publish

Compile and publish a spec to the LAP registry. Requires authentication.

```
lapsh publish <spec> --provider <slug> [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `--provider <slug>` | string | **Required.** Provider domain or slug (e.g., `stripe.com`) |
| `--name <name>` | string | Override spec name (auto-detected from `@api` if omitted) |
| `--source-url <url>` | string | Upstream spec URL |
| `--skill` | boolean | Generate and include Codex CLI skill |
| `--skill-ai` | boolean | Force AI enhancement for included skill |
| `--no-skill-ai` | boolean | Skip AI enhancement for included skill |

**Examples:**

```bash
lapsh publish petstore.yaml --provider petstore.io
lapsh publish stripe.yaml --provider stripe.com --skill --skill-ai
lapsh publish api.yaml --provider example.com --name my-api --source-url https://example.com/spec.yaml
```

---

### login

Authenticate with the LAP registry via GitHub OAuth.

```
lapsh login [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `--name <token-name>` | string | Name for the API token (e.g., `ci-github-actions`) |

---

### logout

Log out and revoke the API token.

```
lapsh logout
```

No flags.

---

### whoami

Show the currently authenticated user.

```
lapsh whoami
```

No flags.

---

## Skill Commands

### skill

Generate a Codex CLI skill from an API spec.

```
lapsh skill <spec> [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `-o, --output <dir>` | string | Output parent directory (default: same directory as spec) |
| `-f, --format <fmt>` | string | Force spec format |
| `--ai` | boolean | Force AI enhancement (requires `claude` CLI) |
| `--no-ai` | boolean | Skip AI enhancement |
| `--full-spec` | boolean | Include full spec instead of lean |
| `--install` | boolean | Install skill directly to `~/.codex/skills/` |
| `--version <ver>` | string | Skill version (default: `1.0.0`) |

**Layer behavior:**
- If `claude` CLI is installed, defaults to AI-enhanced (Layer 2)
- Without `claude` CLI, defaults to mechanical (Layer 1)
- Use `--ai` / `--no-ai` to override

**Examples:**

```bash
# Basic skill
lapsh skill petstore.yaml -o skills/

# AI-enhanced skill
lapsh skill petstore.yaml -o skills/ --ai

# Generate and install
lapsh skill petstore.yaml --install
```

---

### skill-batch

Batch generate skills for all specs in a directory.

```
lapsh skill-batch <dir> -o <outdir> [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `-o, --output <dir>` | string | **Required.** Output directory for all skills |
| `--ai` | boolean | Force AI enhancement |
| `--no-ai` | boolean | Skip AI enhancement |
| `-v, --verbose` | boolean | Print full tracebacks on failure |

**Examples:**

```bash
lapsh skill-batch specs/ -o skills/
lapsh skill-batch specs/ -o skills/ --ai --verbose
```

---

### init

Set up LAP in your IDE (installs skill and config).

```
lapsh init [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `--target <ide>` | `codex\|claude\|cursor` | Target IDE (default: auto-detect) |

**Examples:**

```bash
lapsh init --target codex
lapsh init --target cursor
```

---

### skill-install

Install a skill from the LAP registry.

```
lapsh skill-install <name> [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `--dir <path>` | string | Custom install directory (default: `~/.codex/skills/<name>`) |

**Examples:**

```bash
lapsh skill-install stripe --target codex
lapsh skill-install stripe --target codex --dir ./my-skills/stripe
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LAP_REGISTRY` | Override registry URL | `https://registry.lap.sh` |

---

## Notes

- **Format auto-detection**: Works for OpenAPI (YAML/JSON), GraphQL (SDL), AsyncAPI, Protobuf, Postman collections, and Smithy
- **Lean mode**: Strips descriptions and non-essential metadata for maximum compression. Use for agent consumption where context window is tight
- **Standard mode**: Preserves descriptions and documentation. Use when human readability matters
- **Credentials**: Stored locally after `lapsh login`. Token is revoked on `lapsh logout`
- **User-Agent**: The CLI sends `lapsh/<version>` as User-Agent for registry requests
