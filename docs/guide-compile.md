# Compiling OpenAPI Specs

## Basic Compilation

Convert any OpenAPI 3.x YAML or JSON spec to DocLean:

```bash
lap compile specs/stripe-charges.yaml -o output/stripe.doclean
```

```
✓ Compiled stripe-charges.yaml → output/stripe.doclean
✓ 5 endpoints | 4,291 chars | standard mode
```

## Standard vs Lean Mode

### Standard Mode (default)

Keeps descriptions and comments. Good for debugging and human review.

```bash
lap compile specs/github-core.yaml -o github.doclean
```

```
@endpoint GET /repos/{owner}/{repo}
@desc Get a repository
@required {owner: str # The account owner of the repository., repo: str # The name of the repository.}
@returns(200) {id: int, name: str, full_name: str, ...}
```

### Lean Mode (`--lean`)

Strips all descriptions for maximum token compression. Use in production when agents already know the API semantics.

```bash
lap compile specs/github-core.yaml -o github.lean.doclean --lean
```

```
@endpoint GET /repos/{owner}/{repo}
@required {owner: str, repo: str}
@returns(200) {id: int, name: str, full_name: str, ...}
```

### When to Use Which

| Scenario | Mode | Why |
|----------|------|-----|
| Agent development & debugging | Standard | See what the agent sees |
| Production agent systems | Lean | Minimize tokens |
| New API integration | Standard | Agent needs context |
| Well-known APIs (Stripe, GitHub) | Lean | LLM already knows semantics |
| Documentation / sharing | Standard | Human-readable |

## Handling Large Specs

Large OpenAPI specs (1000+ endpoints) compile fine — the compiler processes endpoints sequentially:

```bash
lap compile specs/stripe-full.yaml -o stripe-full.doclean
```

For very large specs, the output file may be substantial. Tips:

1. **Filter endpoints at the agent level** — load the full spec but only inject relevant endpoints into context
2. **Use lean mode** — strips ~40% of tokens from large specs
3. **Split by domain** — compile separate specs for different API areas (charges, customers, subscriptions)

## Batch Compilation

Compile all specs in a directory:

```bash
lap benchmark-all specs/
```

This processes every `.yaml` file in the directory and produces both standard and lean outputs in `output/`.

To compile individually with control over output:

```bash
for spec in specs/*.yaml; do
  name=$(basename "$spec" .yaml)
  lap compile "$spec" -o "output/${name}.doclean"
  lap compile "$spec" -o "output/${name}.lean.doclean" --lean
done
```

### Available Pre-built Specs

LAP ships with 30+ popular API specs ready to compile:

```
asana        box          circleci     cloudflare   digitalocean
discord      github-core  gitlab       google-maps  hetzner
jira         launchdarkly linode       netlify      notion
openai-core  petstore     plaid        resend       sendgrid
slack        snyk         spotify      stripe       twilio-core
twitter      vercel       vonage       zoom
```

## Validating Output

Always validate that compilation preserved all information:

```bash
lap validate specs/stripe-charges.yaml
```

```
  Check               Result   Status
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoints       5/5 (100%)     ✅
  Parameters    32/32 (100%)     ✅
  Error Codes     8/8 (100%)     ✅

PASS — Zero information loss!
```

The validator round-trips: compiles to DocLean, then checks that every endpoint, parameter, and error code from the original spec is present.

## Converting Back to OpenAPI

DocLean is not a one-way street. Convert back to OpenAPI:

```bash
lap convert output/stripe-charges.doclean -f openapi -o stripe-roundtrip.yaml
```

This is useful for:
- Verifying compilation fidelity
- Generating OpenAPI from hand-written DocLean
- Interoperability with OpenAPI tooling
