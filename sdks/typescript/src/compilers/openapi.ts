import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import {
  LAPSpec,
  Endpoint,
  Param,
  ResponseSchema,
  ResponseField,
  ErrorSchema,
} from '../parser';

function stripHtml(text: string): string {
  return text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/<[^>]+>/g, '');
}

// ── $ref resolution ──────────────────────────────────────────────────────────

function resolveRef(spec: Record<string, unknown>, ref: string, _visited?: Set<string>): Record<string, unknown> {
  if (_visited === undefined) _visited = new Set();
  if (_visited.has(ref)) throw new Error(`Circular $ref detected: ${ref}`);
  _visited.add(ref);

  const parts = ref.replace(/^#\//, '').split('/');
  let node: unknown = spec;
  for (const part of parts) {
    if (node === null || typeof node !== 'object') {
      node = {};
      break;
    }
    node = (node as Record<string, unknown>)[part] ?? {};
  }

  if (node !== null && typeof node === 'object' && '$ref' in (node as Record<string, unknown>)) {
    return resolveRef(spec, (node as Record<string, unknown>)['$ref'] as string, _visited);
  }
  return (node as Record<string, unknown>) ?? {};
}

// ── Type extraction ───────────────────────────────────────────────────────────

function extractType(schema: Record<string, unknown>, spec: Record<string, unknown>): string {
  if ('$ref' in schema) {
    schema = resolveRef(spec, schema['$ref'] as string);
  }

  let t: string = (schema['type'] as string) ?? 'any';

  // OpenAPI 3.1 allows type as an array, e.g. ["integer", "null"]
  if (Array.isArray(t)) {
    const nonNull = (t as string[]).filter((x) => x !== 'null');
    t = nonNull[0] ?? 'any';
  }

  const fmt = (schema['format'] as string) ?? '';

  if (t === 'string' && fmt) return `str(${fmt})`;
  if (t === 'string') return 'str';
  if (t === 'integer') return fmt ? `int(${fmt})` : 'int';
  if (t === 'number') return fmt ? `num(${fmt})` : 'num';
  if (t === 'boolean') return 'bool';
  if (t === 'array') {
    const items = (schema['items'] as Record<string, unknown>) ?? {};
    return `[${extractType(items, spec)}]`;
  }
  if (t === 'object') return 'map';
  return t;
}

function extractTypeInline(
  schema: Record<string, unknown>,
  spec: Record<string, unknown>,
  depth = 0,
  maxDepth = 1,
): string {
  if ('$ref' in schema) {
    schema = resolveRef(spec, schema['$ref'] as string);
  }

  let t: string = (schema['type'] as string) ?? 'any';
  if (Array.isArray(t)) {
    const nonNull = (t as string[]).filter((x) => x !== 'null');
    t = nonNull[0] ?? 'any';
  }

  if (t === 'object' && schema['properties'] && depth < maxDepth) {
    const props = (schema['properties'] as Record<string, unknown>) ?? {};
    const requiredNames = new Set<string>((schema['required'] as string[]) ?? []);
    const parts: string[] = [];

    for (const [propName, propSchemaRaw] of Object.entries(props)) {
      let propSchema = propSchemaRaw as Record<string, unknown>;
      if ('$ref' in propSchema) {
        propSchema = resolveRef(spec, propSchema['$ref'] as string);
      }
      const propType = extractTypeInline(propSchema, spec, depth + 1, maxDepth);
      const reqMarker = requiredNames.has(propName) ? '!' : '';
      parts.push(`${propName}${reqMarker}: ${propType}`);
    }
    return `map{${parts.join(', ')}}`;
  }

  if (t === 'array') {
    const itemsSchema = (schema['items'] as Record<string, unknown>) ?? {};
    const itemsType = extractTypeInline(itemsSchema, spec, depth, maxDepth);
    return `[${itemsType}]`;
  }

  // Fall back to scalar extraction for primitives or objects at max depth
  return extractType(schema, spec);
}

// ── Parameter extraction ──────────────────────────────────────────────────────

function extractParams(paramList: unknown[], spec: Record<string, unknown>): [Param[], Param[]] {
  const required: Param[] = [];
  const optional: Param[] = [];

  for (let p of paramList as Record<string, unknown>[]) {
    if ('$ref' in p) {
      p = resolveRef(spec, p['$ref'] as string);
    }

    const name = (p['name'] as string) ?? '';
    if (!name.trim()) continue; // skip malformed params

    const schema = (p['schema'] as Record<string, unknown>) ?? {};
    const rawEnum = (schema['enum'] as unknown[]) ?? [];
    const enumVals = rawEnum.filter((v) => v !== null).map(String);

    const isReq = Boolean(p['required']);
    const rawDefault = schema['default'];
    const defaultValue = rawDefault !== undefined ? String(rawDefault) : undefined;

    const typeStr = extractType(schema, spec);
    const isArray = typeStr.startsWith('[');

    const nullable = Boolean(schema['nullable']) ||
      (Array.isArray(schema['type']) && (schema['type'] as string[]).includes('null'));

    const param: Param = {
      name,
      type: typeStr,
      required: isReq,
      description: stripHtml(((p['description'] as string) ?? '')).replace(/\n/g, ' ').trim() || undefined,
      nullable,
      enumValues: enumVals.length > 0 ? enumVals : undefined,
      defaultValue,
      isArray,
    };

    if (isReq) {
      required.push(param);
    } else {
      optional.push(param);
    }
  }

  return [required, optional];
}

// ── Request body extraction ───────────────────────────────────────────────────

function extractRequestBody(body: Record<string, unknown>, spec: Record<string, unknown>): Param[] {
  if (!body || Object.keys(body).length === 0) return [];

  if ('$ref' in body) {
    body = resolveRef(spec, body['$ref'] as string);
  }

  const content = (body['content'] as Record<string, unknown>) ?? {};
  let jsonSchema = ((content['application/json'] as Record<string, unknown>) ?? {})['schema'] as
    | Record<string, unknown>
    | undefined;
  if (!jsonSchema) return [];

  if ('$ref' in jsonSchema) {
    jsonSchema = resolveRef(spec, jsonSchema['$ref'] as string);
  }

  const params: Param[] = [];
  const requiredNames = new Set<string>((jsonSchema['required'] as string[]) ?? []);
  const properties = (jsonSchema['properties'] as Record<string, unknown>) ?? {};

  for (const [name, schemaRaw] of Object.entries(properties)) {
    if (!name.trim()) continue;

    let schema = schemaRaw as Record<string, unknown>;
    if ('$ref' in schema) {
      schema = resolveRef(spec, schema['$ref'] as string);
    }

    // Use inline expansion for object-type params to avoid bare 'map'
    const typeStr = extractTypeInline(schema, spec, 0, 1);
    const isArray = typeStr.startsWith('[');

    const rawEnum = (schema['enum'] as unknown[]) ?? [];
    const enumVals = rawEnum.filter((v) => v !== null).map(String);

    const rawDefault = schema['default'];
    const defaultValue = rawDefault !== undefined ? String(rawDefault) : undefined;

    const isReq = requiredNames.has(name);

    const nullable = Boolean(schema['nullable']) ||
      (Array.isArray(schema['type']) && (schema['type'] as string[]).includes('null'));

    params.push({
      name,
      type: typeStr,
      required: isReq,
      description: stripHtml(((schema['description'] as string) ?? '')).replace(/\n/g, ' ').trim() || undefined,
      nullable,
      enumValues: enumVals.length > 0 ? enumVals : undefined,
      defaultValue,
      isArray,
    });
  }

  return params;
}

// ── Response field extraction ─────────────────────────────────────────────────

function extractResponseFields(
  schema: Record<string, unknown>,
  spec: Record<string, unknown>,
  depth = 0,
  maxDepth = 2,
  maxProperties = 500,
): ResponseField[] {
  if ('$ref' in schema) {
    schema = resolveRef(spec, schema['$ref'] as string);
  }

  const fields: ResponseField[] = [];
  const properties = (schema['properties'] as Record<string, unknown>) ?? {};
  let count = 0;

  for (const [name, propRaw] of Object.entries(properties)) {
    if (count >= maxProperties) break;
    count++;

    let prop = propRaw as Record<string, unknown>;
    if ('$ref' in prop) {
      prop = resolveRef(spec, prop['$ref'] as string);
    }

    const typeStr = extractType(prop, spec);
    const propTypeVal = prop['type'];
    const typeList = Array.isArray(propTypeVal) ? (propTypeVal as string[]) : [propTypeVal as string];
    const nullable = Boolean(prop['nullable']) || typeList.includes('null');

    let nested: ResponseField[] | undefined;
    if (prop['type'] === 'object' && depth < maxDepth && prop['properties']) {
      const children = extractResponseFields(prop, spec, depth + 1, maxDepth, maxProperties);
      if (children.length > 0) nested = children;
    }

    fields.push({
      name,
      type: typeStr,
      nullable,
      nested,
    });
  }

  return fields;
}

// ── Response schema extraction ────────────────────────────────────────────────

function extractResponseSchemas(
  responses: Record<string, unknown>,
  spec: Record<string, unknown>,
): [ResponseSchema[], ErrorSchema[]] {
  const responseSchemas: ResponseSchema[] = [];
  const errorSchemas: ErrorSchema[] = [];

  for (const [code, respRaw] of Object.entries(responses)) {
    let resp = respRaw as Record<string, unknown>;
    if ('$ref' in resp) {
      resp = resolveRef(spec, resp['$ref'] as string);
    }

    const desc = stripHtml(((resp['description'] as string) ?? '')).replace(/\n/g, ' ').trim() || undefined;

    const content = (resp['content'] as Record<string, unknown>) ?? {};
    const jsonContent = (content['application/json'] as Record<string, unknown>) ?? {};
    let schema = (jsonContent['schema'] as Record<string, unknown>) ?? {};

    if ('$ref' in schema) {
      schema = resolveRef(spec, schema['$ref'] as string);
    }

    if (code.startsWith('2')) {
      const fields = schema['properties'] ? extractResponseFields(schema, spec) : [];
      // Keep status code as string to support non-numeric codes like "2XX"
      const statusCode = code;
      responseSchemas.push({
        statusCode,
        description: desc,
        fields,
      });
    } else if (code !== 'default') {
      errorSchemas.push({
        statusCode: code,
        description: desc,
      });
    }
  }

  return [responseSchemas, errorSchemas];
}

// ── Auth extraction ───────────────────────────────────────────────────────────

function extractAuth(spec: Record<string, unknown>): string {
  const components = (spec['components'] as Record<string, unknown>) ?? {};
  const schemes = (components['securitySchemes'] as Record<string, unknown>) ?? {};

  if (Object.keys(schemes).length === 0) return '';

  const parts: string[] = [];
  for (const [_schemeName, schemeRaw] of Object.entries(schemes)) {
    const scheme = schemeRaw as Record<string, unknown>;
    const t = (scheme['type'] as string) ?? '';

    if (t === 'http') {
      parts.push(`Bearer ${(scheme['scheme'] as string) ?? 'token'}`);
    } else if (t === 'apiKey') {
      parts.push(`ApiKey ${(scheme['name'] as string) ?? 'key'} in ${(scheme['in'] as string) ?? 'header'}`);
    } else if (t === 'oauth2') {
      parts.push('OAuth2');
    } else if (t) {
      parts.push(t);
    }
  }

  return parts.join(' | ');
}

// ── Constants ─────────────────────────────────────────────────────────────────

const validMethods = new Set(['get', 'post', 'put', 'patch', 'delete', 'head', 'options']);
const COMMON_FIELD_THRESHOLD = 0.95;

// ── Request example extraction ────────────────────────────────────────────────

function extractRequestExample(
  body: Record<string, unknown>,
  spec: Record<string, unknown>,
  visited?: Set<string>,
): string | undefined {
  if (!body || Object.keys(body).length === 0) return undefined;

  if ('$ref' in body) {
    body = resolveRef(spec, body['$ref'] as string, visited);
  }

  const content = (body['content'] as Record<string, unknown>) ?? {};
  const jsonContent = (content['application/json'] as Record<string, unknown>) ?? {};

  const example = jsonContent['example'];
  if (example) {
    return JSON.stringify(example);
  }

  const examples = (jsonContent['examples'] as Record<string, unknown>) ?? {};
  for (const [, exVal] of Object.entries(examples)) {
    const ex = exVal as Record<string, unknown>;
    if (ex['$ref']) {
      const resolved = resolveRef(spec, ex['$ref'] as string, visited);
      if (resolved['value']) return JSON.stringify(resolved['value']);
    }
    if (ex['value']) return JSON.stringify(ex['value']);
  }
  return undefined;
}

// ── Main compiler ─────────────────────────────────────────────────────────────

export function compileOpenapi(specPath: string): LAPSpec {
  const filePath = path.resolve(specPath);
  const stat = fs.statSync(filePath);

  if (stat.size > 50 * 1024 * 1024) {
    throw new Error(`OpenAPI spec too large: ${stat.size} bytes (max 50MB)`);
  }

  const raw = fs.readFileSync(filePath, 'utf-8');
  const ext = path.extname(filePath).toLowerCase();

  let spec: Record<string, unknown>;

  if (ext === '.yaml' || ext === '.yml') {
    try {
      spec = yaml.load(raw) as Record<string, unknown>;
    } catch {
      // Strip unknown YAML tags and retry
      const cleaned = raw.replace(/![a-zA-Z_][\w-]*/g, '');
      spec = yaml.load(cleaned) as Record<string, unknown>;
    }
  } else {
    spec = JSON.parse(raw) as Record<string, unknown>;
  }

  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) {
    throw new Error('Invalid OpenAPI spec: expected a YAML/JSON mapping');
  }

  const info = (spec['info'] as Record<string, unknown>) ?? {};
  const servers = (spec['servers'] as Record<string, unknown>[]) ?? [];
  const baseUrl = servers.length > 0 ? (servers[0]['url'] as string) ?? '' : '';
  const apiName = (info['title'] as string) ?? path.basename(filePath, ext);
  const apiVersion = (info['version'] as string) ?? undefined;
  const auth = extractAuth(spec) || undefined;

  const result: LAPSpec = {
    version: 'v0.3',
    apiName,
    baseUrl,
    apiVersion,
    auth,
    endpoints: [],
    getEndpoint(method: string, p: string): Endpoint | undefined {
      return this.endpoints.find((e) => e.method === method && e.path === p);
    },
  };

  const paths = (spec['paths'] as Record<string, unknown>) ?? {};

  for (const [pathStr, methodsRaw] of Object.entries(paths)) {
    const methods = methodsRaw as Record<string, unknown>;
    for (const [method, detailsRaw] of Object.entries(methods)) {
      if (!validMethods.has(method)) continue;

      const details = detailsRaw as Record<string, unknown>;
      const paramList = (details['parameters'] as unknown[]) ?? [];
      const [reqParams, optParams] = extractParams(paramList, spec);
      const requestBodyRaw = (details['requestBody'] as Record<string, unknown>) ?? {};
      const bodyParams = extractRequestBody(requestBodyRaw, spec);
      const [responseSchemas, errorSchemas] = extractResponseSchemas(
        (details['responses'] as Record<string, unknown>) ?? {},
        spec,
      );

      // Extract request example from requestBody
      const exampleRequest = extractRequestExample(requestBodyRaw, spec);

      const summary = stripHtml(
        (details['summary'] as string) ??
        (details['description'] as string) ??
        ''
      )
        .trim()
        .split('\n')[0]
        .trim();

      // Store body params separately for common-field deduplication
      const endpoint: Endpoint = {
        method,
        path: pathStr,
        description: summary || undefined,
        requiredParams: reqParams,
        optionalParams: optParams,
        allParams: [...reqParams, ...optParams, ...bodyParams],
        requestBody: bodyParams.length > 0 ? bodyParams : undefined,
        responses: responseSchemas,
        errors: errorSchemas,
        exampleRequest,
      };

      result.endpoints.push(endpoint);
    }
  }

  // ── Common field deduplication ──────────────────────────────────────────────
  // Any param (body, query, path, header) appearing in >95% of all endpoints
  // gets extracted into commonFields.
  if (result.endpoints.length > 5) {
    const nameCounts = new Map<string, number>();
    for (const ep of result.endpoints) {
      const seen = new Set<string>();
      const allParams = [
        ...(ep.requestBody || []),
        ...ep.requiredParams,
        ...ep.optionalParams,
      ];
      for (const p of allParams) {
        if (!seen.has(p.name)) {
          nameCounts.set(p.name, (nameCounts.get(p.name) || 0) + 1);
          seen.add(p.name);
        }
      }
    }

    const threshold = result.endpoints.length * COMMON_FIELD_THRESHOLD;
    const commonNames = new Set<string>();
    for (const [name, count] of nameCounts) {
      if (count >= threshold) commonNames.add(name);
    }

    if (commonNames.size > 0) {
      // Extract representative params for common fields
      const commonParams: Param[] = [];
      const addedNames = new Set<string>();
      for (const ep of result.endpoints) {
        const allParams = [
          ...(ep.requestBody || []),
          ...ep.requiredParams,
          ...ep.optionalParams,
        ];
        for (const p of allParams) {
          if (commonNames.has(p.name) && !addedNames.has(p.name)) {
            commonParams.push(p);
            addedNames.add(p.name);
          }
        }
      }

      // Strip common fields from individual endpoints
      for (const ep of result.endpoints) {
        ep.requiredParams = ep.requiredParams.filter(p => !commonNames.has(p.name));
        ep.optionalParams = ep.optionalParams.filter(p => !commonNames.has(p.name));
        if (ep.requestBody) {
          ep.requestBody = ep.requestBody.filter(p => !commonNames.has(p.name));
          if (ep.requestBody.length === 0) ep.requestBody = undefined;
        }
        // Rebuild allParams after stripping
        ep.allParams = [
          ...ep.requiredParams,
          ...ep.optionalParams,
          ...(ep.requestBody || []),
        ];
      }

      result.commonFields = commonParams;
    }
  }

  return result;
}
