// LAP Skill Compiler -- Layer 2 (LLM enhancement)
// Port of lap/core/compilers/skill_llm.py
//
// Primary path: claude CLI subprocess (uses existing Claude Code subscription).
// Fallback path: @anthropic-ai/sdk (for CI environments).

import { execFileSync, execSync } from 'child_process';
import type { LAPSpec } from './parser';
import type { SkillOutput } from './skill';
import { toLap } from './serializer';

// ── Prompt template ───────────────────────────────────────────────────────────

const ENHANCE_PROMPT = `You are enhancing a Claude Code skill for an API. Given the LAP spec below,
generate the following sections in markdown:

1. **Question Mapping** (10-15 entries): Natural language questions mapped to API endpoints.
   Format each as: - "Question?" -> METHOD /path
   Cover common use cases, edge cases, and multi-step workflows.

2. **Response Tips** (one line per endpoint category): How to interpret responses.
   Focus on pagination, error patterns, and nested objects.

3. **Anomaly Flags**: What should an agent surface proactively?
   (e.g., rate limits approaching, deprecated fields, unusual status codes)

4. **Playbook** (3-5 common workflows): Step-by-step guides for typical tasks.
   Format as numbered lists under descriptive headings.

Return ONLY the markdown content -- no preamble, no code fences.

LAP Spec:
{spec_text}`;

// ── Public API ────────────────────────────────────────────────────────────────

export function hasClaudeCli(): boolean {
  try {
    execSync('claude --version', { stdio: 'pipe', timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

export function replaceSection(md: string, sectionName: string, newContent: string): string {
  const escaped = sectionName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`(## ${escaped}\\n)[\\s\\S]*?(?=\\n## |$)`);
  return md.replace(pattern, `## ${sectionName}\n${newContent}\n`);
}

export function enhanceSkill(spec: LAPSpec, skill: SkillOutput, apiKey?: string): SkillOutput {
  const specText = toLap(spec, { lean: true });

  // Guard against oversized prompts
  const promptTokens = Math.ceil(specText.length / 4);
  if (promptTokens > 80000) {
    console.error(
      `Warning: spec is ${promptTokens.toLocaleString()} tokens, exceeding 80k limit. Returning Layer 1 skill unchanged.`
    );
    return skill;
  }

  const prompt = ENHANCE_PROMPT.replace('{spec_text}', specText);

  let enhancedContent: string;

  if (hasClaudeCli()) {
    enhancedContent = enhanceViaCli(prompt);
  } else {
    enhancedContent = enhanceViaSdk(prompt, apiKey);
  }

  let skillMd = skill.fileMap[skill.mainFile];
  skillMd = replaceSection(skillMd, 'Common Questions', enhancedContent);

  const newFileMap = { ...skill.fileMap, [skill.mainFile]: skillMd };
  const totalTokens = Object.values(newFileMap).reduce(
    (sum, c) => sum + Math.ceil(c.length / 4),
    0
  );

  return {
    name: skill.name,
    mainFile: skill.mainFile,
    fileMap: newFileMap,
    tokenCount: totalTokens,
    endpointCount: skill.endpointCount,
  };
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function enhanceViaCli(prompt: string): string {
  try {
    const result = execFileSync(
      'claude',
      ['-p', '--model', 'opus', '--output-format', 'text', '--verbose'],
      {
        input: prompt,
        timeout: 300000, // 5 minutes
        encoding: 'utf-8',
        maxBuffer: 10 * 1024 * 1024,
        shell: true, // needed for Windows .cmd wrappers
      }
    );
    return result;
  } catch (err: unknown) {
    if (err && typeof err === 'object' && 'killed' in err && (err as { killed: boolean }).killed) {
      throw new Error('claude CLI timed out after 5 minutes.');
    }
    const msg = err instanceof Error ? err.message : String(err);
    throw new Error(`claude CLI failed: ${msg}`);
  }
}

function enhanceViaSdk(prompt: string, apiKey?: string): string {
  let Anthropic: any;
  try {
    Anthropic = require('@anthropic-ai/sdk');
  } catch {
    throw new Error(
      "Layer 2 requires either the claude CLI or the '@anthropic-ai/sdk' package. " +
        'Install the CLI (https://docs.anthropic.com/en/docs/claude-code) ' +
        'or run: npm install @anthropic-ai/sdk'
    );
  }

  const clientOpts: Record<string, unknown> = {};
  if (apiKey) clientOpts.apiKey = apiKey;

  // Note: SDK calls are async, but we need sync here. This is a deferred implementation.
  throw new Error(
    'SDK-based enhancement is not yet implemented in the TypeScript SDK. Install the Claude CLI instead: npm install -g @anthropic-ai/sdk'
  );
}
