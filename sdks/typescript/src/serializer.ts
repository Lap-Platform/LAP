// LAP Serializer - TypeScript port of Python LAPSpec.to_lap()

import type { LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema } from './parser';

const LAP_VERSION = 'v0.3';

// ── Helpers ──

/**
 * Derives the group name from an endpoint path.
 * Skips leading version segments (e.g. /v1/) and returns the first meaningful segment.
 * Exported for use by skill.ts.
 */
export function groupName(path: string): string {
  const parts = path.split('/').filter(p => p.length > 0);
  if (parts.length === 0) return 'root';
  let i = 0;
  while (i < parts.length && /^v\d+$/.test(parts[i])) {
    i++;
  }
  return i < parts.length ? parts[i] : parts[0];
}

// ── Per-type serializers ──

function serializeParam(param: Param, lean = false): string {
  let typeStr = param.type || 'any';

  if (param.isArray && !typeStr.startsWith('[')) {
    typeStr = `[${typeStr}]`;
  }

  if (param.enumValues && param.enumValues.length > 1) {
    typeStr += `(${param.enumValues.join('/')})`;
  }

  if (param.defaultValue !== undefined) {
    typeStr += `=${param.defaultValue}`;
  }

  const parts = [`${param.name}: ${typeStr}`];

  if (param.description && !lean) {
    parts.push(`# ${param.description}`);
  }

  return parts.join(' ');
}

function serializeResponseField(field: ResponseField, lean = false, depth = 0): string {
  const nullable = field.nullable ? '?' : '';

  if (field.nested && field.nested.length > 0) {
    const childStr = field.nested
      .map(c => serializeResponseField(c, lean, depth + 1))
      .join(', ');
    return `${field.name}: ${field.type}${nullable}{${childStr}}`;
  }

  return `${field.name}: ${field.type}${nullable}`;
}

function serializeResponseSchema(rs: ResponseSchema, lean = false): string {
  if (!rs.fields || rs.fields.length === 0) {
    if (lean && rs.description && !rs.description.startsWith('\u2192') && !rs.description.startsWith('->')) {
      return `@returns(${rs.statusCode})`;
    }
    if (rs.description) {
      return `@returns(${rs.statusCode}) ${rs.description}`;
    }
    return `@returns(${rs.statusCode})`;
  }

  const fieldsStr = rs.fields.map(f => serializeResponseField(f, lean)).join(', ');
  let line = `@returns(${rs.statusCode}) {${fieldsStr}}`;

  if (rs.description && !lean) {
    line += ` # ${rs.description}`;
  }

  return line;
}

function serializeErrorSchema(err: ErrorSchema, lean = false): string {
  const code = err.type ? `${err.statusCode}:${err.type}` : `${err.statusCode}`;
  if (err.description && !lean) {
    return `${code}: ${err.description}`;
  }
  return code;
}

function serializeEndpoint(ep: Endpoint, lean = false): string {
  const lines: string[] = [];

  lines.push(`@endpoint ${ep.method.toUpperCase()} ${ep.path}`);

  if (ep.description && !lean) {
    lines.push(`@desc ${ep.description}`);
  }

  if (ep.auth) {
    lines.push(`@auth ${ep.auth}`);
  }

  // Merge request body params at serialization time (Python pattern)
  const reqParams = [...(ep.requiredParams || [])];
  const optParams = [...(ep.optionalParams || [])];

  if (ep.requestBody) {
    for (const p of ep.requestBody) {
      if (p.required) reqParams.push(p);
      else optParams.push(p);
    }
  }

  if (reqParams.length > 0) {
    const fields = reqParams.map(p => serializeParam(p, lean)).join(', ');
    lines.push(`@required {${fields}}`);
  }

  if (optParams.length > 0) {
    const fields = optParams.map(p => serializeParam(p, lean)).join(', ');
    lines.push(`@optional {${fields}}`);
  }

  for (const rs of ep.responses) {
    lines.push(serializeResponseSchema(rs, lean));
  }

  if (ep.errors.length > 0) {
    const errStr = ep.errors.map(e => serializeErrorSchema(e, lean)).join(', ');
    lines.push(`@errors {${errStr}}`);
  }

  if (!lean && ep.exampleRequest) {
    lines.push(`@example_request ${ep.exampleRequest}`);
  }

  return lines.join('\n');
}

// ── Main export ──

/**
 * Serializes a LAPSpec object back to LAP text format.
 *
 * @param spec   - The parsed LAPSpec object
 * @param options.lean - When true, omits descriptions and comments for maximum token efficiency
 */
export function toLap(spec: LAPSpec, options?: { lean?: boolean }): string {
  const lean = options?.lean ?? false;
  const lines: string[] = [];

  lines.push(`@lap ${LAP_VERSION}`);
  lines.push('# Machine-readable API spec. Each @endpoint block is one API call.');
  lines.push(`@api ${spec.apiName}`);

  if (spec.baseUrl) {
    lines.push(`@base ${spec.baseUrl}`);
  }

  if (spec.apiVersion) {
    lines.push(`@version ${spec.apiVersion}`);
  }

  if (spec.auth) {
    lines.push(`@auth ${spec.auth}`);
  }

  // Common fields -- params that repeat across nearly all endpoints
  if (spec.commonFields && spec.commonFields.length > 0) {
    const fields = spec.commonFields.map(p => serializeParam(p, lean)).join(', ');
    lines.push(`@common_fields {${fields}}`);
  }

  lines.push(`@endpoints ${spec.endpoints.length}`);

  if (spec.endpoints.length > 20) {
    lines.push('@hint download_for_search');
  }

  // Table of contents
  if (spec.endpoints.length > 0) {
    const groups = new Map<string, number>();
    for (const ep of spec.endpoints) {
      const gname = groupName(ep.path);
      groups.set(gname, (groups.get(gname) ?? 0) + 1);
    }
    const tocEntries = Array.from(groups.entries()).map(([name, count]) => `${name}(${count})`);
    lines.push(`@toc ${tocEntries.join(', ')}`);
  }

  // Emit @type blocks for reused types
  if (spec.typeDefs && spec.typeDefs.length > 0) {
    lines.push('');
    for (const td of spec.typeDefs) {
      const fields = td.fields.map(f => serializeResponseField(f)).join(', ');
      lines.push(`@type ${td.name} {${fields}}`);
    }
  }

  lines.push('');

  // Determine whether to use @group/@endgroup markers
  const distinctGroups = new Set<string>();
  for (const ep of spec.endpoints) {
    distinctGroups.add(groupName(ep.path));
  }
  const useGroups = distinctGroups.size > 1;

  let currentGroup: string | null = null;

  for (const ep of spec.endpoints) {
    const gname = groupName(ep.path);

    if (useGroups && gname !== currentGroup) {
      if (currentGroup !== null) {
        lines.push('@endgroup');
        lines.push('');
      }
      lines.push(`@group ${gname}`);
      currentGroup = gname;
    }

    lines.push(serializeEndpoint(ep, lean));
    lines.push('');
  }

  if (useGroups && currentGroup !== null) {
    lines.push('@endgroup');
    lines.push('');
  }

  lines.push('@end');
  lines.push('');

  return lines.join('\n');
}
