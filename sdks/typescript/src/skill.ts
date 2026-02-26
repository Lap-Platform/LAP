// LAP Skill Compiler -- Layer 1 (mechanical, no LLM)
// Generates Claude Code skill directories from LAPSpec objects.
// Port of lap/core/compilers/skill.py

import type { LAPSpec, Endpoint } from './parser';
import { toLap, groupName } from './serializer';

// ── Public interfaces ─────────────────────────────────────────────────────────

export interface SkillOptions {
  layer?: number;  // 1 = mechanical, 2 = LLM-enhanced
  lean?: boolean;
  clawhub?: boolean;  // include metadata.openclaw block
  version?: string;   // skill version in frontmatter (default: "1.0.0")
}

export interface SkillOutput {
  name: string;           // skill directory name (slugified API name)
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
  let slug = name.toLowerCase().replace(/ /g, '-').replace(/_/g, '-');
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

function generateFrontmatter(spec: LAPSpec, options?: SkillOptions): string {
  const name = slugify(spec.apiName);
  const groups = getGroups(spec);
  const topGroups = [...groups.keys()].slice(0, 3);
  const groupText = topGroups.length > 0 ? topGroups.join(', ') : 'API operations';
  const epCount = spec.endpoints.length;

  const desc =
    `${spec.apiName} API skill. ` +
    `Use when working with ${spec.apiName} for ${groupText}. ` +
    `Covers ${epCount} endpoint${epCount !== 1 ? 's' : ''}.`;

  const descEscaped = desc.replace(/"/g, '\\"');

  const ver = options?.version ?? '1.0.0';
  let fm = `---\nname: ${name}\ndescription: "${descEscaped}"\nversion: ${ver}\ngenerator: lap-platform`;

  if (options?.clawhub && spec.auth) {
    const envVar = slugify(spec.apiName).toUpperCase().replace(/-/g, '_') + '_API_KEY';
    fm += `\nmetadata:\n  openclaw:\n    requires:\n      env:\n        - ${envVar}`;
  }

  fm += '\n---';
  return fm;
}

function generateSkillBody(spec: LAPSpec): string {
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

function generateSkillMd(spec: LAPSpec, options?: SkillOptions): string {
  const parts: string[] = [];
  parts.push(generateFrontmatter(spec, options));
  parts.push('');
  parts.push(generateSkillBody(spec));
  return parts.join('\n');
}

// ── Main export ───────────────────────────────────────────────────────────────

export function generateSkill(spec: LAPSpec, options?: SkillOptions): SkillOutput {
  options = { layer: 1, lean: true, ...options };
  if (!spec.endpoints || spec.endpoints.length === 0) {
    throw new Error('Cannot generate skill from spec with no endpoints.');
  }
  const name = slugify(spec.apiName);
  const fileMap: Record<string, string> = {};
  fileMap['SKILL.md'] = generateSkillMd(spec, options);
  const lean = options.lean ?? true;
  fileMap['references/api-spec.lap'] = toLap(spec, { lean });
  const totalTokens = Object.values(fileMap).reduce(
    (sum, content) => sum + countTokens(content),
    0
  );
  return {
    name,
    fileMap,
    tokenCount: totalTokens,
    endpointCount: spec.endpoints.length,
  };
}
