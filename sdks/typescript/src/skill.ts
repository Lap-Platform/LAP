// LAP Skill Compiler -- Layer 1 (mechanical, no LLM)
// Generates Claude Code skill directories from LAPSpec objects.
// Port of lap/core/compilers/skill.py

import type { LAPSpec, Endpoint } from './parser';
import { toLap, groupName } from './serializer';
import * as fs from 'fs';
import * as path from 'path';

// ── Public interfaces ─────────────────────────────────────────────────────────

export const VALID_TARGETS = ['claude', 'codex', 'cursor'] as const;
export type SkillTarget = typeof VALID_TARGETS[number];

/**
 * Auto-detect IDE target from environment.
 *
 * Detection priority:
 * 1. TERM_PROGRAM env var (macOS/Linux -- set by IDE terminals)
 * 2. IDE-specific env vars (CURSOR_TRACE_ID, CURSOR_EDITOR, etc.)
 * 3. PATH entries containing IDE binary paths (cross-platform, esp. Windows)
 * 4. .cursor project directory (walk up to .git root)
 * 5. ~/.cursor/ in home directory (Cursor installed on this machine)
 * 6. Default: 'claude'
 */
export function detectTarget(): SkillTarget {
  // 1. TERM_PROGRAM (macOS/Linux)
  const term = (process.env.TERM_PROGRAM || '').toLowerCase();
  if (term.includes('cursor')) return 'cursor';

  // 2. IDE-specific env vars
  if (process.env.CURSOR_TRACE_ID || process.env.CURSOR_EDITOR) return 'cursor';

  // 3. PATH-based detection (Windows: TERM_PROGRAM often unset)
  const pathEnv = (process.env.PATH || '').toLowerCase();
  if (pathEnv.includes('cursor') && pathEnv.includes('codebin')) return 'cursor';

  // 4. Project directory walk
  let dir = process.cwd();
  while (true) {
    if (fs.existsSync(path.join(dir, '.cursor'))) return 'cursor';
    if (fs.existsSync(path.join(dir, '.git'))) break;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }

  // 5. Home directory check (Cursor config exists)
  const homeDir = process.env.HOME || process.env.USERPROFILE;
  if (homeDir && fs.existsSync(path.join(homeDir, '.cursor'))) return 'cursor';

  // 6. Codex CLI detection
  if (process.env.CODEX_SANDBOX || process.env.CODEX_SESSION_ID) return 'codex';
  if (pathEnv.includes('codex')) return 'codex';
  if (homeDir && fs.existsSync(path.join(homeDir, '.codex'))) return 'codex';

  return 'claude';
}

export interface SkillOptions {
  layer?: number;  // 1 = mechanical, 2 = LLM-enhanced
  lean?: boolean;
  clawhub?: boolean;  // include metadata.openclaw block
  version?: string;   // skill version in frontmatter (default: "1.0.0")
  target?: SkillTarget;  // "claude" | "cursor" | "codex" (default: "claude")
}

export interface SkillOutput {
  name: string;           // skill directory name (slugified API name)
  mainFile: string;       // key into fileMap for the main skill file
  fileMap: Record<string, string>;  // {relative_path: content_string}
  tokenCount: number;     // total tokens across all files
  endpointCount: number;
}

// ── Token counting ────────────────────────────────────────────────────────────

function countTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

// ── Helper functions (ported 1:1 from Python) ─────────────────────────────────

export function slugify(name: string): string {
  let slug = name.toLowerCase().replace(/ /g, '-').replace(/_/g, '-').replace(/\//g, '-').replace(/\./g, '-');
  slug = slug.split('').filter(c => /[a-z0-9-]/.test(c)).join('').replace(/^-+|-+$/g, '');
  slug = slug.replace(/-+/g, '-');
  return slug || 'api';
}

function getGroups(spec: LAPSpec): Map<string, Endpoint[]> {
  const groups = new Map<string, Endpoint[]>();
  for (const ep of spec.endpoints) {
    const gname = groupName(ep.path);
    if (!groups.has(gname)) {
      groups.set(gname, []);
    }
    groups.get(gname)!.push(ep);
  }
  return groups;
}

function findFirstEndpoint(spec: LAPSpec, method: string, isList = false): Endpoint | null {
  const m = method.toLowerCase();
  if (isList) {
    // First pass: prefer endpoints with NO path params at all
    for (const ep of spec.endpoints) {
      if (ep.method.toLowerCase() === m && !ep.path.includes('{')) {
        return ep;
      }
    }
    // Fall back: skip endpoints whose trailing segment is a path param
    for (const ep of spec.endpoints) {
      if (ep.method.toLowerCase() !== m) continue;
      if (/\{[^}]+\}$/.test(ep.path.replace(/\/$/, ''))) continue;
      return ep;
    }
    return null;
  }
  for (const ep of spec.endpoints) {
    if (ep.method.toLowerCase() === m) return ep;
  }
  return null;
}

function resourceFromPath(path: string): string {
  const parts = path.replace(/^\/|\/$/g, '').split('/').filter(p => p.length > 0);
  for (let i = parts.length - 1; i >= 0; i--) {
    const part = parts[i];
    if (!part.startsWith('{')) {
      if (/^v\d+$/.test(part)) continue;
      return part;
    }
  }
  return '';
}

function lastSegmentRaw(path: string): string {
  const parts = path.replace(/^\/|\/$/g, '').split('/').filter(p => p.length > 0);
  return parts.length > 0 ? parts[parts.length - 1] : '';
}

export function singularize(word: string): string {
  if (!word) return word;
  if (word.endsWith('ss') || word.endsWith('us') || word.endsWith('is')) return word;
  const EXCEPTIONS: Record<string, string> = {
    responses: 'response',
    databases: 'database',
    purchases: 'purchase',
    analyses: 'analysis',
    releases: 'release',
    licenses: 'license',
    resources: 'resource',
    expenses: 'expense',
    invoices: 'invoice',
    messages: 'message',
    courses: 'course',
  };
  if (word in EXCEPTIONS) return EXCEPTIONS[word];
  if (word.endsWith('ies') && word.length > 3) return word.slice(0, -3) + 'y';
  if (word.endsWith('oes') && word.length > 3) return word.slice(0, -2);
  if (word.endsWith('ses') && word.length > 3) {
    if (word.length > 3 && 'aeiou'.includes(word[word.length - 4])) {
      return word.slice(0, -1);
    }
    return word.slice(0, -2);
  }
  if (word.endsWith('s')) return word.slice(0, -1);
  return word;
}

// ── Content generators ────────────────────────────────────────────────────────

function generateCommonQuestions(spec: LAPSpec): string {
  const lines = ['## Common Questions'];
  lines.push('');
  lines.push('Match user requests to endpoints in api-spec.lap. Key patterns:');
  lines.push('- "List/get all X" -> Look for GET endpoints on collection paths');
  lines.push('- "Create/add X" -> Look for POST endpoints');
  lines.push('- "Update/modify X" -> Look for PUT/PATCH endpoints');
  lines.push('- "Delete/remove X" -> Look for DELETE endpoints');
  if (spec.auth) {
    lines.push('- "How to authenticate?" -> See Auth section above');
  }
  return lines.join('\n');
}

function generateResponseTips(_spec: LAPSpec): string {
  return '## Response Tips\n\nCheck response schemas in api-spec.lap for field details.';
}

function generateEndpointCatalog(spec: LAPSpec): string {
  const groups = getGroups(spec);
  const groupCount = groups.size;
  const epCount = spec.endpoints.length;
  const lines = ['## Endpoints'];
  lines.push('');
  lines.push(`${epCount} endpoints across ${groupCount} groups. See references/api-spec.lap for full details.`);

  // Collect key endpoints: first GET and first mutating method per group, max 10
  const keyEndpoints: string[] = [];
  for (const [, endpoints] of groups) {
    const firstGet = endpoints.find(ep => ep.method.toUpperCase() === 'GET');
    const firstMutate = endpoints.find(ep => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(ep.method.toUpperCase()));
    if (firstGet && keyEndpoints.length < 10) {
      keyEndpoints.push(`${firstGet.method.toUpperCase()} ${firstGet.path}`);
    }
    if (firstMutate && keyEndpoints.length < 10) {
      keyEndpoints.push(`${firstMutate.method.toUpperCase()} ${firstMutate.path}`);
    }
  }

  const remaining = epCount - keyEndpoints.length;
  let keyLine = `Key endpoints: ${keyEndpoints.join(', ')}`;
  if (remaining > 0) {
    keyLine += ` ... and ${remaining} more`;
  }
  lines.push('');
  lines.push(keyLine);

  return lines.join('\n');
}

function generateSetup(spec: LAPSpec): string {
  const lines = ['## Setup'];

  // Step 1: Auth
  if (spec.auth) {
    const authLower = spec.auth.toLowerCase();
    if (authLower.includes('bearer')) {
      lines.push('1. Set Authorization header with your Bearer token');
    } else if (
      authLower.includes('apikey') ||
      authLower.includes('api_key') ||
      authLower.includes('api-key')
    ) {
      lines.push('1. Set your API key in the appropriate header');
    } else {
      lines.push(`1. Configure auth: ${spec.auth}`);
    }
  } else {
    lines.push('1. No auth setup needed');
  }

  // Step 2: Find a list endpoint for verification
  const listEp = findFirstEndpoint(spec, 'get', true);
  if (listEp) {
    lines.push(`2. GET ${listEp.path} -- verify access`);
  } else {
    const getEp = findFirstEndpoint(spec, 'get');
    if (getEp) {
      lines.push(`2. GET ${getEp.path} -- verify access`);
    }
  }

  // Step 3: Find a create endpoint
  const createEp = findFirstEndpoint(spec, 'post');
  if (createEp) {
    const resource = resourceFromPath(createEp.path);
    const desc = resource ? `create first ${resource}` : 'create first resource';
    lines.push(`3. POST ${createEp.path} -- ${desc}`);
  }

  return lines.join('\n');
}

function buildDescription(spec: LAPSpec): string {
  const groups = getGroups(spec);
  const topGroups = [...groups.keys()].slice(0, 3);
  const groupText = topGroups.length > 0 ? topGroups.join(', ') : 'API operations';
  const epCount = spec.endpoints.length;

  // Strip trailing " API" to avoid "Stripe API API skill" doubling
  let displayName = spec.apiName;
  if (displayName.toUpperCase().endsWith(' API')) {
    displayName = displayName.slice(0, -4).trimEnd();
  }
  if (!displayName || displayName.toUpperCase() === 'API') {
    displayName = spec.apiName; // fallback: use original name as-is
  }

  let desc: string;
  if (displayName.toUpperCase() === 'API') {
    desc =
      `API skill. ` +
      `Use when working with this API for ${groupText}. ` +
      `Covers ${epCount} endpoint${epCount !== 1 ? 's' : ''}.`;
  } else {
    desc =
      `${displayName} API skill. ` +
      `Use when working with ${displayName} for ${groupText}. ` +
      `Covers ${epCount} endpoint${epCount !== 1 ? 's' : ''}.`;
  }
  return desc.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

function generateFrontmatter(spec: LAPSpec, options?: SkillOptions): string {
  const target = options?.target ?? 'claude';
  if (target === 'cursor') return generateCursorFrontmatter(spec);
  return generateClaudeFrontmatter(spec, options); // claude and codex use same frontmatter
}

function generateClaudeFrontmatter(spec: LAPSpec, options?: SkillOptions): string {
  const name = slugify(spec.apiName);
  const descEscaped = buildDescription(spec);
  const ver = options?.version ?? '1.0.0';
  let fm = `---\nname: ${name}\ndescription: "${descEscaped}"\nversion: ${ver}\ngenerator: lapsh`;

  if (options?.clawhub && spec.auth) {
    let envSlug = slugify(spec.apiName).toUpperCase().replace(/-/g, '_');
    if (envSlug.endsWith('_API')) envSlug = envSlug.slice(0, -4);
    const envVar = (envSlug || 'API') + '_API_KEY';
    fm += `\nmetadata:\n  openclaw:\n    requires:\n      env:\n        - ${envVar}`;
  }

  fm += '\n---';
  return fm;
}

function generateCursorFrontmatter(spec: LAPSpec): string {
  const descEscaped = buildDescription(spec);
  return `---\ndescription: "${descEscaped}"\nalwaysApply: false\n---`;
}

function generateSkillBody(spec: LAPSpec, target: SkillTarget = 'claude'): string {
  const sections: string[] = [];

  // Title
  sections.push(`# ${spec.apiName}`);
  if (spec.apiVersion) {
    sections.push(`API version: ${spec.apiVersion}`);
  }
  sections.push('');

  // Auth
  sections.push('## Auth');
  if (spec.auth) {
    sections.push(spec.auth);
  } else {
    sections.push('No authentication required.');
  }
  sections.push('');

  // Base URL
  sections.push('## Base URL');
  sections.push(spec.baseUrl || 'Not specified.');
  sections.push('');

  // Setup
  sections.push(generateSetup(spec));
  sections.push('');

  // Endpoints by group
  sections.push(generateEndpointCatalog(spec));
  sections.push('');

  // Common Questions
  sections.push(generateCommonQuestions(spec));
  sections.push('');

  // Response Tips
  sections.push(generateResponseTips(spec));
  sections.push('');

  // CLI
  sections.push(generateCliSection(spec, target));
  sections.push('');

  // References
  sections.push('## References');
  sections.push(
    '- Full spec: See references/api-spec.lap for complete endpoint details, parameter tables, and response schemas'
  );
  sections.push('');

  // Attribution
  sections.push('> Generated from the official API spec by [LAP](https://lap.sh)');
  sections.push('');

  return sections.join('\n');
}

function generateCliSection(spec: LAPSpec, target: SkillTarget = 'claude'): string {
  const slug = slugify(spec.apiName);
  if (target === 'codex') return generateCodexCliSection(slug);
  return [
    '## CLI',
    '',
    '```bash',
    '# Update this spec to the latest version',
    `npx @lap-platform/lapsh get ${slug} -o references/api-spec.lap`,
    '',
    '# Search for related APIs',
    `npx @lap-platform/lapsh search ${slug}`,
    '```',
  ].join('\n');
}

function generateCodexCliSection(slug: string): string {
  return [
    '## CLI',
    '',
    'Use curl to manage specs (instant in sandbox, no install needed):',
    '',
    '```bash',
    '# Update this spec to the latest version',
    `curl -sH 'Accept: text/lap' https://registry.lap.sh/v1/apis/${slug} -o references/api-spec.lap`,
    '',
    '# Search for related APIs',
    `curl -s 'https://registry.lap.sh/v1/search?q=${slug}'`,
    '',
    '# Check for updates (returns JSON with latest version)',
    `curl -sH 'Accept: application/json' https://registry.lap.sh/v1/apis/${slug}`,
    '```',
    '',
    '<details><summary>Alternative: npx (slower, downloads package first)</summary>',
    '',
    '```bash',
    `npx @lap-platform/lapsh get ${slug} -o references/api-spec.lap`,
    `npx @lap-platform/lapsh search ${slug}`,
    '```',
    '',
    '</details>',
  ].join('\n');
}

function generateSkillMd(spec: LAPSpec, options?: SkillOptions): string {
  const parts: string[] = [];
  parts.push(generateFrontmatter(spec, options));
  parts.push('');
  parts.push(generateSkillBody(spec, options?.target ?? 'claude'));
  return parts.join('\n');
}

// ── Main export ───────────────────────────────────────────────────────────────

export function generateSkill(spec: LAPSpec, options?: SkillOptions): SkillOutput {
  options = { layer: 1, lean: true, target: 'claude', ...options };
  const target = options.target ?? 'claude';

  if (!(VALID_TARGETS as readonly string[]).includes(target)) {
    throw new Error(`Unknown target '${target}'. Valid targets: ${[...VALID_TARGETS].sort().join(', ')}`);
  }
  if (!spec.endpoints || spec.endpoints.length === 0) {
    throw new Error('Cannot generate skill from spec with no endpoints.');
  }

  const name = slugify(spec.apiName);
  const mainFile = target === 'cursor' ? `${name}.mdc` : 'SKILL.md';
  const fileMap: Record<string, string> = {};
  fileMap[mainFile] = generateSkillMd(spec, options);
  const lean = options.lean ?? true;
  fileMap['references/api-spec.lap'] = toLap(spec, { lean });
  const totalTokens = Object.values(fileMap).reduce(
    (sum, content) => sum + countTokens(content),
    0
  );
  return {
    name,
    mainFile,
    fileMap,
    tokenCount: totalTokens,
    endpointCount: spec.endpoints.length,
  };
}
