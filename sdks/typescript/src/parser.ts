// LAP Parser - TypeScript implementation

export interface ResponseField {
  name: string;
  type: string;
  nullable: boolean;
  description?: string;
  enumValues?: string[];
  format?: string;
  nested?: ResponseField[];
}

export interface ResponseSchema {
  statusCode: number;
  description?: string;
  fields: ResponseField[];
}

export interface ErrorSchema {
  statusCode: number;
  description?: string;
}

export interface Param {
  name: string;
  type: string;
  required: boolean;
  description?: string;
  nullable: boolean;
  enumValues?: string[];
  defaultValue?: string;
  format?: string;
  isArray: boolean;
  nested?: ResponseField[];
}

export interface Endpoint {
  method: string;
  path: string;
  description?: string;
  requiredParams: Param[];
  optionalParams: Param[];
  allParams: Param[];
  responses: ResponseSchema[];
  errors: ErrorSchema[];
}

export interface LAPSpec {
  version: string;
  apiName: string;
  baseUrl: string;
  apiVersion?: string;
  auth?: string;
  endpoints: Endpoint[];

  getEndpoint(method: string, path: string): Endpoint | undefined;
}

/** @deprecated Use LAPSpec instead */
export type DocLeanSpec = LAPSpec;

// ── Internal parsing helpers ──

function parseTypeExpr(raw: string): {
  type: string;
  nullable: boolean;
  enumValues?: string[];
  format?: string;
  isArray: boolean;
  nested?: ResponseField[];
} {
  let s = raw.trim();
  let nullable = false;
  let isArray = false;
  let enumValues: string[] | undefined;
  let format: string | undefined;
  let nested: ResponseField[] | undefined;

  // nullable: str?
  if (s.endsWith('?')) {
    nullable = true;
    s = s.slice(0, -1);
  }

  // array: [str]
  if (s.startsWith('[') && s.endsWith(']')) {
    isArray = true;
    s = s.slice(1, -1);
  }

  // map with nested fields: map{field: type, ...}
  if (s.startsWith('map{')) {
    const inner = s.slice(4, -1);
    nested = parseFieldList(inner);
    return { type: 'map', nullable, isArray, nested };
  }

  // enum: str(a/b/c)
  const enumMatch = s.match(/^(\w+)\(([^)]+)\)$/);
  if (enumMatch) {
    const baseType = enumMatch[1];
    const enumContent = enumMatch[2];
    // Check if it's a format hint (like date-time, unix-timestamp) vs enum
    if (!enumContent.includes('/')) {
      format = enumContent;
    } else {
      enumValues = enumContent.split('/');
    }
    return { type: baseType, nullable, enumValues, format, isArray };
  }

  return { type: s, nullable, isArray };
}

/** Parse a balanced brace-delimited block starting at `text[start]` which should be '{'. */
function findMatchingBrace(text: string, start: number): number {
  let depth = 0;
  for (let i = start; i < text.length; i++) {
    if (text[i] === '{') depth++;
    else if (text[i] === '}') { depth--; if (depth === 0) return i; }
  }
  return text.length - 1;
}

/** Split top-level comma-separated items (respecting nested braces, parens, brackets). */
function splitTopLevel(text: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let current = '';
  for (const ch of text) {
    if (ch === '{' || ch === '(' || ch === '[') depth++;
    else if (ch === '}' || ch === ')' || ch === ']') depth--;
    if (ch === ',' && depth === 0) {
      parts.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  if (current.trim()) parts.push(current.trim());
  return parts;
}

function parseFieldList(inner: string): ResponseField[] {
  const items = splitTopLevel(inner);
  const fields: ResponseField[] = [];
  for (const item of items) {
    const colonIdx = item.indexOf(':');
    if (colonIdx === -1) continue;
    const name = item.slice(0, colonIdx).trim();
    let rest = item.slice(colonIdx + 1).trim();

    // Strip trailing comment
    let description: string | undefined;
    const commentIdx = rest.indexOf('#');
    if (commentIdx !== -1) {
      // But only if # is not inside parens
      let d = 0;
      for (let i = 0; i < rest.length; i++) {
        if (rest[i] === '(' || rest[i] === '{' || rest[i] === '[') d++;
        else if (rest[i] === ')' || rest[i] === '}' || rest[i] === ']') d--;
        else if (rest[i] === '#' && d === 0) {
          description = rest.slice(i + 1).trim();
          rest = rest.slice(0, i).trim();
          break;
        }
      }
    }

    const typeInfo = parseTypeExpr(rest);
    fields.push({
      name,
      type: typeInfo.type,
      nullable: typeInfo.nullable,
      description,
      enumValues: typeInfo.enumValues,
      format: typeInfo.format,
      nested: typeInfo.nested,
    });
  }
  return fields;
}

function parseParams(inner: string, required: boolean): Param[] {
  const items = splitTopLevel(inner);
  const params: Param[] = [];
  for (const item of items) {
    const colonIdx = item.indexOf(':');
    if (colonIdx === -1) continue;
    const name = item.slice(0, colonIdx).trim();
    let rest = item.slice(colonIdx + 1).trim();

    let description: string | undefined;
    // Extract comment
    {
      let d = 0;
      for (let i = 0; i < rest.length; i++) {
        if (rest[i] === '(' || rest[i] === '{' || rest[i] === '[') d++;
        else if (rest[i] === ')' || rest[i] === '}' || rest[i] === ']') d--;
        else if (rest[i] === '#' && d === 0) {
          description = rest.slice(i + 1).trim();
          rest = rest.slice(0, i).trim();
          break;
        }
      }
    }

    // Extract default value
    let defaultValue: string | undefined;
    const eqMatch = rest.match(/^([^=]+)=(.+)$/);
    if (eqMatch) {
      // Make sure = is not inside parens
      let d = 0;
      let eqIdx = -1;
      for (let i = 0; i < rest.length; i++) {
        if (rest[i] === '(' || rest[i] === '{' || rest[i] === '[') d++;
        else if (rest[i] === ')' || rest[i] === '}' || rest[i] === ']') d--;
        else if (rest[i] === '=' && d === 0) { eqIdx = i; break; }
      }
      if (eqIdx !== -1) {
        defaultValue = rest.slice(eqIdx + 1).trim();
        rest = rest.slice(0, eqIdx).trim();
      }
    }

    const typeInfo = parseTypeExpr(rest);
    params.push({
      name,
      type: typeInfo.type,
      required,
      description,
      nullable: typeInfo.nullable,
      enumValues: typeInfo.enumValues,
      defaultValue,
      format: typeInfo.format,
      isArray: typeInfo.isArray,
      nested: typeInfo.nested,
    });
  }
  return params;
}

function parseBraceContent(line: string): string | null {
  const open = line.indexOf('{');
  if (open === -1) return null;
  const close = findMatchingBrace(line, open);
  return line.slice(open + 1, close);
}

function parseReturns(line: string): ResponseSchema {
  // @returns(200) {fields} # description  OR  @returns(200) description text
  const m = line.match(/^@returns\((\d+)\)\s*(.*)/);
  if (!m) return { statusCode: 200, fields: [] };
  const statusCode = parseInt(m[1]);
  let rest = m[2].trim();

  let description: string | undefined;
  if (rest.startsWith('{')) {
    const close = findMatchingBrace(rest, 0);
    const inner = rest.slice(1, close);
    const after = rest.slice(close + 1).trim();
    if (after.startsWith('#')) description = after.slice(1).trim();
    else if (after) description = after;
    const fields = parseFieldList(inner);
    return { statusCode, description, fields };
  } else {
    // Plain text description
    if (rest) description = rest;
    return { statusCode, description, fields: [] };
  }
}

function parseErrors(line: string): ErrorSchema[] {
  // @errors {400: msg, 401: msg} or @errors {400, 401}
  const inner = parseBraceContent(line);
  if (!inner) return [];
  const items = splitTopLevel(inner);
  return items.map(item => {
    const colonIdx = item.indexOf(':');
    if (colonIdx !== -1) {
      return {
        statusCode: parseInt(item.slice(0, colonIdx).trim()),
        description: item.slice(colonIdx + 1).trim(),
      };
    }
    return { statusCode: parseInt(item.trim()) };
  });
}

export function parse(text: string): LAPSpec {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('//'));

  let version = '';
  let apiName = '';
  let baseUrl = '';
  let apiVersion: string | undefined;
  let auth: string | undefined;
  const endpoints: Endpoint[] = [];

  let current: Endpoint | null = null;

  function flush() {
    if (current) {
      current.allParams = [...current.requiredParams, ...current.optionalParams];
      endpoints.push(current);
    }
  }

  for (const line of lines) {
    if (line.startsWith('@lap ') || line.startsWith('@doclean')) {
      version = line.replace(/^@(?:lap|doclean)\s*/, '').trim();
    } else if (line.startsWith('@api ')) {
      apiName = line.slice(5).trim();
    } else if (line.startsWith('@base ')) {
      baseUrl = line.slice(6).trim();
    } else if (line.startsWith('@version ')) {
      apiVersion = line.slice(9).trim();
    } else if (line.startsWith('@auth ')) {
      auth = line.slice(6).trim();
    } else if (line.startsWith('@endpoint ')) {
      flush();
      const parts = line.slice(10).trim().split(/\s+/);
      current = {
        method: parts[0],
        path: parts[1],
        requiredParams: [],
        optionalParams: [],
        allParams: [],
        responses: [],
        errors: [],
      };
    } else if (line.startsWith('@desc ') && current) {
      current.description = line.slice(6).trim();
    } else if (line.startsWith('@required') && current) {
      const inner = parseBraceContent(line);
      if (inner) current.requiredParams = parseParams(inner, true);
    } else if (line.startsWith('@optional') && current) {
      const inner = parseBraceContent(line);
      if (inner) current.optionalParams = parseParams(inner, false);
    } else if (line.startsWith('@returns') && current) {
      current.responses.push(parseReturns(line));
    } else if (line.startsWith('@errors') && current) {
      current.errors = parseErrors(line);
    }
  }
  flush();

  return {
    version,
    apiName,
    baseUrl,
    apiVersion,
    auth,
    endpoints,
    getEndpoint(method: string, path: string) {
      return this.endpoints.find(e => e.method === method && e.path === path);
    },
  };
}
