# ToolLean Real-World Compilation Summary

## Stats
- **13 total tools compiled** (6 OpenClaw skills + 5 MCP server bundles + 2 pre-existing)
- **22 individual tool definitions** across MCP bundles (filesystem: 6, GitHub: 4, Slack: 4, Brave: 2, SQLite: 5, plus camera: 2)
- **Overall average compression: 6.6x** vs source format
  - OpenClaw SKILL.md files: **10.0x** average (best: discord at 24.6x)
  - MCP JSON manifests: **2.5x** average

## Compiled Sources

### OpenClaw Skills (from /app/skills/ and /data/workspace/skills/)
| Skill | Source | Compiled | Ratio |
|-------|--------|----------|-------|
| github | 1,674B | 424B | 4.0x |
| himalaya | 4,616B | 441B | 10.5x |
| camsnap | 1,089B | 120B | 9.1x |
| discord | 11,812B | 480B | 24.6x |
| garmin | 2,207B | 563B | 3.9x |
| table-image-generator | 3,588B | 454B | 7.9x |

### MCP Server Manifests (realistic definitions based on popular MCP servers)
| Server | Source JSON | Compiled | Ratio | Tools |
|--------|-----------|----------|-------|-------|
| filesystem | 2,328B | 909B | 2.6x | 6 |
| github-mcp | 2,729B | 1,061B | 2.6x | 4 |
| slack | 2,057B | 846B | 2.4x | 4 |
| brave-search | 1,434B | 645B | 2.2x | 2 |
| sqlite | 1,542B | 620B | 2.5x | 5 |

## Issues Found & Fixed

1. **YAML frontmatter not parsed**: OpenClaw SKILL.md files use YAML frontmatter for `name` and `description`. The compiler originally skipped this entirely, falling back to H1 parsing which often missed the structured metadata. **Fixed**: Added frontmatter extraction regex.

2. **No examples extracted without `## Examples` header**: Skills embed examples as code blocks throughout the document, not under a dedicated section. **Fixed**: Added fallback that extracts code blocks from body when no explicit examples section exists.

3. **SKILL.md examples are noisy**: The code-block fallback picks up some non-example content (config snippets, install commands). The first-line heuristic helps but isn't perfect. Could be improved with better heuristics.

4. **MCP compilation works cleanly**: JSON schema → ToolLean mapping handles types, enums, defaults, required/optional, and nested arrays well. No bugs found.

5. **Skills lack structured parameters**: Most OpenClaw skills are CLI-oriented prose docs, not structured API definitions. ToolLean captures the name/desc/examples but can't extract formal parameters. This is expected — these skills are instructions for an LLM, not API schemas.

## Observations

- **ToolLean shines most on structured data** (MCP manifests) where it preserves all semantic information at ~2.5x compression
- **For prose-heavy skills**, compression is higher (10x+) but information loss occurs — the full usage instructions are reduced to name + description + example snippets
- **The format is production-ready** for MCP tool discovery; skill compilation would benefit from richer SKILL.md structure
