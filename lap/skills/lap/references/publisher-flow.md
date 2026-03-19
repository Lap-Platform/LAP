# Publisher Flow -- Compiling and Publishing APIs

This reference covers the full workflow for publishing API specs to the LAP registry.

---

## Step 1: Authenticate

### Login

```bash
lapsh login
```

Opens a browser for GitHub OAuth. After authorizing, the token is stored locally.

Name your token for identification (useful for CI):
```bash
lapsh login --name ci-github-actions
```

### Verify

```bash
lapsh whoami
# Output: logged in as <username>
```

### Logout

```bash
lapsh logout
# Revokes the token
```

---

## Step 2: Compile Your Spec

### Basic Compilation

```bash
lapsh compile api.yaml -o api.lap
```

### Lean Mode

Strips descriptions and non-essential metadata for maximum compression:

```bash
lapsh compile api.yaml -o api.lean.lap --lean
```

### Format Override

If auto-detection fails or you want to be explicit:

```bash
lapsh compile spec.json -f openapi -o spec.lap
lapsh compile schema.graphql -f graphql -o schema.lap
lapsh compile collection.json -f postman -o collection.lap
```

### Supported Source Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| OpenAPI 3.x | `.yaml`, `.yml`, `.json` | Most common |
| GraphQL | `.graphql`, `.gql` | SDL format |
| AsyncAPI | `.yaml`, `.yml`, `.json` | Event-driven APIs |
| Protobuf | `.proto` | gRPC services |
| Postman | `.json` | Collection v2.x |
| Smithy | `.smithy` | AWS-style models |

### Validate Output

Read the compiled LAP file to verify:

```bash
# Check it starts with @api and has expected endpoints
head -20 api.lap
```

---

## Step 3: Generate a Skill

Skills make APIs immediately usable in Claude Code and OpenClaw.

### Layer 1 -- Mechanical

Generates a skill from the spec structure alone. Fast, no external dependencies.

```bash
lapsh skill api.yaml -o skills/ --no-ai
```

### Layer 2 -- AI-Enhanced

Uses Claude CLI to generate richer descriptions, better examples, and smarter organization. Requires `claude` CLI installed.

```bash
lapsh skill api.yaml -o skills/ --ai
```

**Auto-detection**: If `claude` CLI is on PATH, Layer 2 is used automatically. Use `--no-ai` to force Layer 1.

### Skill Options

```bash
# Include full spec instead of lean (larger but more descriptive)
lapsh skill api.yaml -o skills/ --full-spec

# Set skill version
lapsh skill api.yaml -o skills/ --version 2.0.0

# Install directly to Claude Code skills directory
lapsh skill api.yaml --install
```

### Skill Output Structure

```
skills/<api-name>/
  SKILL.md          # Skill metadata and usage
  references/
    <name>.lap      # Compiled spec (lean by default)
```

---

## Step 4: Publish

### Basic Publish

```bash
lapsh publish api.yaml --provider example.com
```

The `--provider` flag is required. Use the provider's domain (e.g., `stripe.com`, `twilio.com`).

### With Metadata

```bash
lapsh publish api.yaml \
  --provider stripe.com \
  --name charges \
  --source-url https://raw.githubusercontent.com/stripe/openapi/master/spec3.yaml
```

- `--name` overrides the API name (auto-detected from `@api` if omitted)
- `--source-url` links to the upstream spec for reference

### With Skill

```bash
# Include a mechanical skill
lapsh publish api.yaml --provider example.com --skill

# Include an AI-enhanced skill
lapsh publish api.yaml --provider example.com --skill --skill-ai

# Include skill without AI enhancement
lapsh publish api.yaml --provider example.com --skill --no-skill-ai
```

---

## Step 5: Verify

### Search for Your Published Spec

```bash
lapsh search <name>
```

### Download and Verify

```bash
lapsh get <name> -o verify.lap
diff api.lap verify.lap
```

---

## Step 6: Batch Operations

### Batch Skill Generation

Generate skills for all specs in a directory:

```bash
lapsh skill-batch specs/ -o skills/
lapsh skill-batch specs/ -o skills/ --ai
lapsh skill-batch specs/ -o skills/ --verbose  # show errors
```

Processes all `.yaml`, `.yml`, and `.json` files in the directory.

---

## End-to-End Example

**Scenario**: Publish a new API with a skill

```bash
# 1. Authenticate
lapsh login
lapsh whoami

# 2. Compile to verify
lapsh compile api.yaml -o api.lap
lapsh compile api.yaml -o api.lean.lap --lean

# 3. Generate and review skill locally
lapsh skill api.yaml -o ./skills/ --ai

# 4. Publish with skill
lapsh publish api.yaml --provider mycompany.com --skill --skill-ai

# 5. Verify it's live
lapsh search mycompany

# 6. Test the full loop -- install your own skill
lapsh skill-install mycompany --target claude
```

**Scenario**: Batch publish multiple APIs

```bash
# 1. Authenticate
lapsh login

# 2. Generate all skills
lapsh skill-batch specs/ -o skills/ --ai --verbose

# 3. Publish each spec
for f in specs/*.yaml; do
  name=$(basename "$f" .yaml)
  lapsh publish "$f" --provider mycompany.com --name "$name" --skill
done

```

**Scenario**: Update a published API

```bash
# 1. Compile new version
lapsh compile api-v2.yaml -o api-v2.lap

# 2. Regenerate skill
lapsh skill api-v2.yaml --install

# 3. Re-publish (overwrites previous version)
lapsh publish api-v2.yaml --provider mycompany.com --skill --skill-ai
```

---

## Tips

- Always `lapsh whoami` before publishing to confirm you're authenticated
- Use `--source-url` to link back to the canonical spec -- helps consumers find updates
- Generate skills with `--ai` for better quality if `claude` CLI is available
- Lean specs are typically 2-3x smaller than standard -- use lean for agent consumption
- Published specs are immutable per version -- publish a new version to update
