/**
 * GraphQL SDL + Introspection JSON -> LAPSpec.
 * Maps Query fields to GET, Mutation fields to POST, Subscription fields to GET with prefix.
 *
 * Ported from the registry compiler (TypeScript) and Python compiler.
 */

import * as fs from 'fs';
import * as path from 'path';
import type {
  LAPSpec,
  Endpoint,
  Param,
  ResponseSchema,
  ResponseField,
} from '../parser';

type Obj = Record<string, unknown>;

// ---- GraphQL type mapping ----

const GQL_SCALAR_MAP: Record<string, string> = {
  String: 'str',
  Int: 'int',
  Float: 'num',
  Boolean: 'bool',
  ID: 'str(id)',
};

function gqlScalarToLap(name: string): string {
  return GQL_SCALAR_MAP[name] || 'map';
}

/** Convert a GraphQL SDL type reference to LAP type string. */
function gqlTypeToLap(raw: string): string {
  const s = raw.trim().replace(/!$/g, '');

  // List type: [Type] or [Type!]
  const listMatch = s.match(/^\[(.+)\]$/);
  if (listMatch) {
    return `[${gqlTypeToLap(listMatch[1])}]`;
  }

  // Remove trailing ! for inner types
  const clean = s.replace(/!$/, '');
  return GQL_SCALAR_MAP[clean] || clean.toLowerCase();
}

// ---- SDL Path ----

interface GqlTypeField {
  name: string;
  args: { name: string; type: string; required: boolean }[];
  returnType: string;
  description: string;
}

type TypeMap = Map<string, GqlTypeField[]>;

/** Split comma-separated args, respecting bracket nesting. */
function splitArgs(s: string): string[] {
  const parts: string[] = [];
  let current = '';
  let depth = 0;

  for (const ch of s) {
    if (ch === '[' || ch === '(') depth++;
    else if (ch === ']' || ch === ')') depth--;
    else if (ch === ',' && depth === 0) {
      parts.push(current);
      current = '';
      continue;
    }
    current += ch;
  }
  if (current.trim()) parts.push(current);
  return parts;
}

function parseFieldArgs(argsStr: string): { name: string; type: string; required: boolean }[] {
  if (!argsStr.trim()) return [];

  const args: { name: string; type: string; required: boolean }[] = [];
  const parts = splitArgs(argsStr);

  for (const part of parts) {
    const m = part.trim().match(/^(\w+)\s*:\s*(.+?)(?:\s*=\s*.*)?$/);
    if (!m) continue;

    const name = m[1];
    const rawType = m[2].trim();
    const required = rawType.endsWith('!');
    const type = gqlTypeToLap(rawType);

    args.push({ name, type, required });
  }

  return args;
}

function parseSdlFields(body: string): GqlTypeField[] {
  const fields: GqlTypeField[] = [];
  const lines = body.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;

    // Parse: fieldName(arg1: Type!, arg2: Type): ReturnType!
    const fieldMatch = trimmed.match(/^(\w+)\s*(?:\(([^)]*)\))?\s*:\s*(.+?)$/);
    if (!fieldMatch) continue;

    const name = fieldMatch[1];
    const argsStr = fieldMatch[2] || '';
    const returnTypeStr = fieldMatch[3].trim().replace(/#.*$/, '').trim();

    const args = parseFieldArgs(argsStr);
    const returnType = gqlTypeToLap(returnTypeStr);

    fields.push({
      name,
      args,
      returnType,
      description: name,
    });
  }

  return fields;
}

function parseSdlTypes(src: string): TypeMap {
  const typeMap: TypeMap = new Map();

  // Match type/input blocks: `type Name {` or `input Name {`
  const typeRegex = /(?:type|input)\s+(\w+)(?:\s+implements\s+[^{]*)?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/g;
  let match: RegExpExecArray | null;

  while ((match = typeRegex.exec(src)) !== null) {
    const typeName = match[1];
    const body = match[2];
    const fields = parseSdlFields(body);
    typeMap.set(typeName, fields);
  }

  return typeMap;
}

function makeParam(name: string, type: string, required: boolean, description: string): Param {
  return {
    name,
    type,
    required,
    description,
    nullable: !required,
    enumValues: undefined,
    defaultValue: undefined,
    format: undefined,
    isArray: type.startsWith('['),
    nested: undefined,
  };
}

function fieldToEndpoint(
  method: string,
  field: GqlTypeField,
  typeMap: TypeMap,
): Endpoint {
  const requiredParams: Param[] = [];
  const optionalParams: Param[] = [];

  for (const arg of field.args) {
    const param = makeParam(arg.name, arg.type, arg.required, '');
    if (arg.required) requiredParams.push(param);
    else optionalParams.push(param);
  }

  // Response fields from return type
  const responses = resolveReturnType(field.returnType, typeMap);

  return {
    method,
    path: `/graphql/${field.name}`,
    description: field.description,
    requiredParams,
    optionalParams,
    allParams: [...requiredParams, ...optionalParams],
    responses,
    errors: [],
  };
}

function resolveReturnType(lapType: string, typeMap: TypeMap): ResponseSchema[] {
  // Extract the base type name from LAP type (strip [], !, etc)
  const baseName = lapType.replace(/^\[+/, '').replace(/]+$/, '').replace(/[!?]/g, '');

  // Check if this is a known object type
  const fields = typeMap.get(baseName);
  if (!fields || !fields.length) return [];

  const responseFields: ResponseField[] = fields.map((f) => ({
    name: f.name,
    type: f.returnType,
    nullable: false,
  }));

  return [{
    statusCode: '200',
    description: undefined,
    fields: responseFields,
  }];
}

function compileSdl(content: string, fallbackName?: string): LAPSpec {
  // Strip triple-quote block descriptions
  let src = content.replace(/"""[\s\S]*?"""/g, '');
  // Strip single-line string descriptions (before type definitions)
  src = src.replace(/"[^"]*"\s*\n/g, '\n');
  // Strip directives like @deprecated(reason: "...") but not @-keywords we care about
  src = src.replace(/@\w+\([^)]*\)/g, '');
  src = src.replace(/@\w+/g, '');

  // Determine root type names from schema block or use defaults
  let queryTypeName = 'Query';
  let mutationTypeName = 'Mutation';
  let subscriptionTypeName = 'Subscription';

  const schemaMatch = src.match(/schema\s*\{([^}]*)\}/);
  if (schemaMatch) {
    const schemaBody = schemaMatch[1];
    const qm = schemaBody.match(/query\s*:\s*(\w+)/);
    const mm = schemaBody.match(/mutation\s*:\s*(\w+)/);
    const sm = schemaBody.match(/subscription\s*:\s*(\w+)/);
    if (qm) queryTypeName = qm[1];
    if (mm) mutationTypeName = mm[1];
    if (sm) subscriptionTypeName = sm[1];
  }

  // Parse all type and input blocks
  const typeMap = parseSdlTypes(src);

  // Build endpoints
  const endpoints: Endpoint[] = [];

  const queryFields = typeMap.get(queryTypeName) || [];
  for (const f of queryFields) {
    endpoints.push(fieldToEndpoint('GET', f, typeMap));
  }

  const mutationFields = typeMap.get(mutationTypeName) || [];
  for (const f of mutationFields) {
    endpoints.push(fieldToEndpoint('POST', f, typeMap));
  }

  const subFields = typeMap.get(subscriptionTypeName) || [];
  for (const f of subFields) {
    const ep = fieldToEndpoint('GET', f, typeMap);
    ep.description = `[SUBSCRIPTION] ${ep.description || ''}`.trim();
    endpoints.push(ep);
  }

  const apiName = fallbackName || 'GraphQL API';

  return {
    version: 'v0.3',
    apiName,
    baseUrl: '/graphql',
    endpoints,
    getEndpoint(method: string, p: string): Endpoint | undefined {
      return this.endpoints.find((e) => e.method === method && e.path === p);
    },
  };
}

// ---- Introspection JSON Path ----

function introspectionTypeToLap(typeObj: Obj | undefined): string {
  if (!typeObj) return 'any';
  const kind = typeObj['kind'] as string;

  if (kind === 'NON_NULL') {
    return introspectionTypeToLap(typeObj['ofType'] as Obj);
  }
  if (kind === 'LIST') {
    return `[${introspectionTypeToLap(typeObj['ofType'] as Obj)}]`;
  }

  const name = (typeObj['name'] as string) || 'any';
  return gqlScalarToLap(name);
}

function resolveIntrospectionReturn(
  typeObj: Obj | undefined,
  typeFieldMap: Map<string, Obj[]>,
): ResponseSchema[] {
  if (!typeObj) return [];

  // Unwrap NON_NULL and LIST to get the base type name
  let base = typeObj;
  while (base['ofType']) base = base['ofType'] as Obj;
  const baseName = (base['name'] as string) || '';

  const fields = typeFieldMap.get(baseName);
  if (!fields || !fields.length) return [];

  const responseFields: ResponseField[] = fields.map((f) => ({
    name: (f['name'] as string) || '',
    type: introspectionTypeToLap(f['type'] as Obj),
    nullable: (f['type'] as Obj)?.['kind'] !== 'NON_NULL',
  }));

  return [{
    statusCode: '200',
    description: undefined,
    fields: responseFields,
  }];
}

function introspectionFieldToEndpoint(
  method: string,
  field: Obj,
  typeFieldMap: Map<string, Obj[]>,
): Endpoint {
  const name = (field['name'] as string) || '';
  const desc = (field['description'] as string) || name;
  const args = (field['args'] as Obj[]) || [];

  const requiredParams: Param[] = [];
  const optionalParams: Param[] = [];

  for (const arg of args) {
    const argName = (arg['name'] as string) || '';
    const argType = introspectionTypeToLap(arg['type'] as Obj);
    const isRequired = (arg['type'] as Obj)?.['kind'] === 'NON_NULL';

    const param = makeParam(
      argName,
      argType,
      isRequired,
      ((arg['description'] as string) || '').replace(/\n/g, ' ').trim(),
    );
    if (isRequired) requiredParams.push(param);
    else optionalParams.push(param);
  }

  // Response from return type
  const returnType = field['type'] as Obj;
  const responses = resolveIntrospectionReturn(returnType, typeFieldMap);

  return {
    method,
    path: `/graphql/${name}`,
    description: desc.replace(/\n/g, ' ').trim().split('\n')[0].trim(),
    requiredParams,
    optionalParams,
    allParams: [...requiredParams, ...optionalParams],
    responses,
    errors: [],
  };
}

function compileIntrospection(data: Obj, fallbackName?: string): LAPSpec {
  const schema = (data['__schema'] as Obj) || ((data['data'] as Obj)?.__schema as Obj) || {};

  const queryTypeName = ((schema['queryType'] as Obj)?.['name'] as string) || 'Query';
  const mutationTypeName = ((schema['mutationType'] as Obj)?.['name'] as string) || null;
  const subscriptionTypeName = ((schema['subscriptionType'] as Obj)?.['name'] as string) || null;

  // Build a map of type name -> fields
  const types = (schema['types'] as Obj[]) || [];
  const typeFieldMap = new Map<string, Obj[]>();
  for (const t of types) {
    const name = t['name'] as string;
    const fields = (t['fields'] as Obj[]) || [];
    if (name && fields.length) typeFieldMap.set(name, fields);
  }

  const endpoints: Endpoint[] = [];

  // Query fields -> GET
  const queryFields = typeFieldMap.get(queryTypeName) || [];
  for (const f of queryFields) {
    endpoints.push(introspectionFieldToEndpoint('GET', f, typeFieldMap));
  }

  // Mutation fields -> POST
  if (mutationTypeName) {
    const mutFields = typeFieldMap.get(mutationTypeName) || [];
    for (const f of mutFields) {
      endpoints.push(introspectionFieldToEndpoint('POST', f, typeFieldMap));
    }
  }

  // Subscription fields -> GET with prefix
  if (subscriptionTypeName) {
    const subFields = typeFieldMap.get(subscriptionTypeName) || [];
    for (const f of subFields) {
      const ep = introspectionFieldToEndpoint('GET', f, typeFieldMap);
      ep.description = `[SUBSCRIPTION] ${ep.description || ''}`.trim();
      endpoints.push(ep);
    }
  }

  return {
    version: 'v0.3',
    apiName: fallbackName || 'GraphQL API',
    baseUrl: '/graphql',
    endpoints,
    getEndpoint(method: string, p: string): Endpoint | undefined {
      return this.endpoints.find((e) => e.method === method && e.path === p);
    },
  };
}

// ---- Detection ----

/** Detect GraphQL SDL text. */
function isGraphqlSdl(content: string): boolean {
  return /\btype\s+(Query|Mutation|Subscription)\s*\{/.test(content) ||
    /\bschema\s*\{/.test(content);
}

/** Detect GraphQL Introspection JSON. */
function isGraphqlIntrospection(data: Obj): boolean {
  if (data['__schema']) return true;
  const d = data['data'] as Obj | undefined;
  return !!(d && d['__schema']);
}

// ---- Main entry ----

/**
 * Compile a GraphQL spec file (SDL or introspection JSON) to a LAPSpec.
 *
 * @param specPath - Path to a .graphql, .gql, or .json introspection file.
 */
export function compileGraphql(specPath: string): LAPSpec {
  const filePath = path.resolve(specPath);
  const content = fs.readFileSync(filePath, 'utf-8');
  const ext = path.extname(filePath).toLowerCase();
  const fallbackName = path.basename(filePath, ext)
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

  // JSON path: try introspection
  if (ext === '.json') {
    let data: Obj;
    try {
      data = JSON.parse(content) as Obj;
    } catch {
      throw new Error(`Cannot parse '${specPath}' as JSON.`);
    }
    if (isGraphqlIntrospection(data)) {
      return compileIntrospection(data, fallbackName);
    }
    throw new Error(
      `JSON file '${specPath}' does not appear to be a GraphQL introspection result.`,
    );
  }

  // SDL path
  if (!isGraphqlSdl(content)) {
    throw new Error(
      `File '${specPath}' does not appear to contain GraphQL SDL (no type Query/Mutation/Subscription or schema block found).`,
    );
  }
  return compileSdl(content, fallbackName);
}
