/**
 * AsyncAPI v2.x / v3.x -> LAPSpec.
 * Maps publish/send operations to PUB and subscribe/receive to SUB.
 * Supports channel parameters, message payloads, headers, protocol bindings,
 * and security scheme extraction.
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  LAPSpec,
  Endpoint,
  Param,
  ResponseSchema,
  ResponseField,
} from '../parser';

type Obj = Record<string, unknown>;

function stripHtml(text: string): string {
  return text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/<[^>]+>/g, '');
}

// ── $ref resolution ───────────────────────────────────────────────────────────

function resolveRef(spec: Obj, ref: string, _visited?: Set<string>): Obj {
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
    node = (node as Obj)[part] ?? {};
  }

  if (node !== null && typeof node === 'object' && '$ref' in (node as Obj)) {
    return resolveRef(spec, (node as Obj)['$ref'] as string, _visited);
  }
  return (node as Obj) ?? {};
}

function maybeResolve(spec: Obj, obj: unknown): Obj {
  if (!obj || typeof obj !== 'object') return {} as Obj;
  const o = obj as Obj;
  if ('$ref' in o && typeof o['$ref'] === 'string') {
    return resolveRef(spec, o['$ref'] as string);
  }
  return o;
}

// ── Type extraction ───────────────────────────────────────────────────────────

function extractType(schema: Obj, spec: Obj): string {
  if (!schema || typeof schema !== 'object') return 'any';
  schema = maybeResolve(spec, schema);

  let t: string | string[] = (schema['type'] as string | string[]) ?? 'any';
  if (Array.isArray(t)) {
    const nonNull = t.filter((x) => x !== 'null');
    t = nonNull[0] ?? 'any';
  }
  const fmt = (schema['format'] as string) || '';

  if (t === 'string' && fmt) return `str(${fmt})`;
  if (t === 'string') return 'str';
  if (t === 'integer') return fmt ? `int(${fmt})` : 'int';
  if (t === 'number') return fmt ? `num(${fmt})` : 'num';
  if (t === 'boolean') return 'bool';
  if (t === 'array') {
    const items = (schema['items'] as Obj) ?? {};
    return `[${extractType(items, spec)}]`;
  }
  if (t === 'object') return 'map';
  return t as string;
}

function extractTypeInline(
  schema: Obj,
  spec: Obj,
  depth = 0,
  maxDepth = 1,
): string {
  schema = maybeResolve(spec, schema);

  let t: string | string[] = (schema['type'] as string | string[]) ?? 'any';
  if (Array.isArray(t)) {
    const nonNull = t.filter((x) => x !== 'null');
    t = nonNull[0] ?? 'any';
  }

  if (t === 'object' && schema['properties'] && depth < maxDepth) {
    const props = (schema['properties'] as Obj) ?? {};
    const requiredNames = new Set<string>((schema['required'] as string[]) ?? []);
    const parts: string[] = [];
    for (const [propName, propSchemaRaw] of Object.entries(props)) {
      let propSchema = maybeResolve(spec, propSchemaRaw);
      const propType = extractTypeInline(propSchema, spec, depth + 1, maxDepth);
      const reqMarker = requiredNames.has(propName) ? '!' : '';
      parts.push(`${propName}${reqMarker}: ${propType}`);
    }
    return `map{${parts.join(', ')}}`;
  }

  if (t === 'array') {
    const itemsSchema = (schema['items'] as Obj) ?? {};
    const itemsType = extractTypeInline(itemsSchema, spec, depth, maxDepth);
    return `[${itemsType}]`;
  }

  return extractType(schema, spec);
}

// ── Schema-based param/field extraction ───────────────────────────────────────

function extractParamsFromSchema(schema: Obj, spec: Obj): Param[] {
  schema = maybeResolve(spec, schema);
  if (!schema || schema['type'] !== 'object') return [];

  const params: Param[] = [];
  const requiredNames = new Set<string>((schema['required'] as string[]) ?? []);
  const properties = (schema['properties'] as Obj) ?? {};

  for (const [name, propRaw] of Object.entries(properties)) {
    const prop = maybeResolve(spec, propRaw);
    const typeStr = extractTypeInline(prop, spec, 0, 1);
    const rawEnum = (prop['enum'] as unknown[]) ?? [];
    const enumVals = rawEnum.filter((v) => v !== null).map(String);
    const rawDefault = prop['default'];

    params.push({
      name,
      type: typeStr,
      required: requiredNames.has(name),
      description: ((prop['description'] as string) ?? '').replace(/\n/g, ' ').trim() || undefined,
      nullable: Boolean(prop['nullable']),
      enumValues: enumVals.length > 0 ? enumVals : undefined,
      defaultValue: rawDefault !== undefined ? String(rawDefault) : undefined,
      isArray: typeStr.startsWith('['),
    });
  }

  return params;
}

function extractFieldsFromSchema(schema: Obj, spec: Obj, depth = 0, maxDepth = 2): ResponseField[] {
  schema = maybeResolve(spec, schema);
  const fields: ResponseField[] = [];
  const properties = (schema['properties'] as Obj) ?? {};

  for (const [name, propRaw] of Object.entries(properties)) {
    const prop = maybeResolve(spec, propRaw);
    const typeStr = extractType(prop, spec);
    const nullable = Boolean(prop['nullable']);
    let nested: ResponseField[] | undefined;

    if (prop['type'] === 'object' && depth < maxDepth && prop['properties']) {
      const children = extractFieldsFromSchema(prop, spec, depth + 1, maxDepth);
      if (children.length > 0) nested = children;
    }

    fields.push({ name, type: typeStr, nullable, nested });
  }

  return fields;
}

// ── Auth extraction ───────────────────────────────────────────────────────────

// Parameter names that strongly suggest authentication
const AUTH_PARAM_NAMES = new Set([
  'api_key', 'apikey', 'api-key',
  'token', 'access_token', 'x-api-key',
  'authorization', 'auth_token', 'secret',
  'api_secret', 'app_key', 'appkey', 'client_secret',
  'subscription-key', 'ocp-apim-subscription-key',
  'x-auth-token', 'api_token',
]);

const AUTH_DESC_KEYWORDS = [
  'api key', 'authentication', 'auth token',
  'access token', 'your key', 'your token',
];

function extractSecuritySchemes(spec: Obj): string {
  const components = (spec['components'] as Obj) ?? {};
  const schemes = (components['securitySchemes'] as Obj) ?? {};
  if (Object.keys(schemes).length === 0) return '';

  const parts: string[] = [];
  for (const schemeRaw of Object.values(schemes)) {
    const scheme = maybeResolve(spec, schemeRaw);
    const t = (scheme['type'] as string) || '';
    if (t === 'http' || t === 'httpApiKey') {
      parts.push(`Bearer ${(scheme['scheme'] as string) || 'token'}`);
    } else if (t === 'apiKey') {
      parts.push(`ApiKey ${(scheme['name'] as string) || 'key'} in ${(scheme['in'] as string) || 'header'}`);
    } else if (t === 'oauth2') {
      parts.push('OAuth2');
    } else if (t === 'userPassword') {
      parts.push('Basic');
    } else if (t) {
      parts.push(t);
    }
  }

  return parts.join(' | ');
}

function inferAuthFromAsyncParams(spec: Obj): string {
  const channels = (spec['channels'] as Obj) ?? {};

  for (const channelDefRaw of Object.values(channels)) {
    const channelDef = maybeResolve(spec, channelDefRaw);

    // Check channel-level parameters
    const channelParams = (channelDef['parameters'] as Obj) ?? {};
    for (const [pname, pdefRaw] of Object.entries(channelParams)) {
      const pdef = maybeResolve(spec, pdefRaw);
      const nameLower = pname.toLowerCase();
      const desc = ((pdef['description'] as string) || '').toLowerCase();
      if (AUTH_PARAM_NAMES.has(nameLower)) return `ApiKey ${pname} in channel`;
      if (AUTH_DESC_KEYWORDS.some((kw) => desc.includes(kw))) return `ApiKey ${pname} in channel`;
    }

    // Check message headers for publish and subscribe operations
    for (const opKey of ['publish', 'subscribe'] as const) {
      const op = channelDef[opKey] as Obj | undefined;
      if (!op || typeof op !== 'object') continue;
      const opResolved = maybeResolve(spec, op);

      const message = maybeResolve(spec, opResolved['message']);
      if (!message || typeof message !== 'object') continue;

      // Handle oneOf
      const msgs: Obj[] = message['oneOf']
        ? (message['oneOf'] as Obj[])
        : [message];

      for (const m of msgs) {
        const resolved = maybeResolve(spec, m);
        const headers = maybeResolve(spec, resolved['headers']);
        const properties = (headers['properties'] as Obj) ?? {};
        for (const [hname, hpropRaw] of Object.entries(properties)) {
          const hprop = maybeResolve(spec, hpropRaw);
          const nameLower = hname.toLowerCase();
          const desc = ((hprop['description'] as string) || '').toLowerCase();
          if (AUTH_PARAM_NAMES.has(nameLower)) return `ApiKey ${hname} in header`;
          if (AUTH_DESC_KEYWORDS.some((kw) => desc.includes(kw))) return `ApiKey ${hname} in header`;
        }
      }
    }

    // v3-style messages dict on the channel itself
    const chMessages = (channelDef['messages'] as Obj) ?? {};
    for (const msgRaw of Object.values(chMessages)) {
      const msg = maybeResolve(spec, msgRaw);
      const headers = maybeResolve(spec, msg['headers']);
      const properties = (headers['properties'] as Obj) ?? {};
      for (const [hname, hpropRaw] of Object.entries(properties)) {
        const hprop = maybeResolve(spec, hpropRaw);
        const nameLower = hname.toLowerCase();
        const desc = ((hprop['description'] as string) || '').toLowerCase();
        if (AUTH_PARAM_NAMES.has(nameLower)) return `ApiKey ${hname} in header`;
        if (AUTH_DESC_KEYWORDS.some((kw) => desc.includes(kw))) return `ApiKey ${hname} in header`;
      }
    }
  }

  return '';
}

// ── Server URL extraction ─────────────────────────────────────────────────────

function getServersUrl(spec: Obj): string {
  const servers = (spec['servers'] as Obj) ?? {};
  if (typeof servers !== 'object') return '';

  for (const srvRaw of Object.values(servers)) {
    const srv = maybeResolve(spec, srvRaw);
    const url = (srv['url'] as string) || '';
    const protocol = (srv['protocol'] as string) || '';
    if (url) {
      if (!url.includes('://') && protocol) return `${protocol}://${url}`;
      return url;
    }
  }
  return '';
}

// ── Protocol binding extraction ───────────────────────────────────────────────

function extractProtocolBinding(bindings: Obj | undefined, spec: Obj): string {
  if (!bindings) return '';
  bindings = maybeResolve(spec, bindings);
  const parts: string[] = [];

  for (const proto of ['mqtt', 'kafka', 'ws', 'amqp', 'http'] as const) {
    if (proto in bindings) {
      const b = maybeResolve(spec, bindings[proto]);
      const details: string[] = [];
      for (const key of [
        'qos', 'retain', 'groupId', 'clientId', 'acks', 'key',
        'topic', 'exchange', 'queue', 'method', 'type', 'is', 'durable',
      ]) {
        if (key in b) {
          let val = b[key];
          if (val && typeof val === 'object') val = (val as Obj)['type'] ?? val;
          details.push(`${key}=${val}`);
        }
      }
      const detailStr = details.length ? `(${details.join(', ')})` : '';
      parts.push(`${proto}${detailStr}`);
    }
  }

  return parts.join('; ');
}

// ── Message compilation ───────────────────────────────────────────────────────

interface CompiledMessage {
  payloadParams: Param[];
  headerParams: Param[];
  summary: string;
  responseFields: ResponseField[];
}

function compileMessage(msg: unknown, spec: Obj): CompiledMessage {
  const resolved = maybeResolve(spec, msg);
  let summary = (
    (resolved['summary'] as string) ||
    (resolved['name'] as string) ||
    (resolved['description'] as string) ||
    ''
  ).trim();
  if (summary) summary = summary.split('\n')[0].trim();

  // Payload
  const payload = maybeResolve(spec, resolved['payload']);
  const payloadParams = extractParamsFromSchema(payload, spec);
  const responseFields = extractFieldsFromSchema(payload, spec);

  // Headers
  const headers = maybeResolve(spec, resolved['headers']);
  const headerParams = extractParamsFromSchema(headers, spec);

  return { payloadParams, headerParams, summary, responseFields };
}

// ── Version detection ─────────────────────────────────────────────────────────

function detectVersion(spec: Obj): number {
  const ver = spec['asyncapi'] ?? '2.0.0';
  return parseInt(String(ver).split('.')[0], 10);
}

// ── v2 compilation ────────────────────────────────────────────────────────────

function compileV2(spec: Obj, apiName: string, baseUrl: string, apiVersion: string | undefined, authScheme: string): LAPSpec {
  const channels = (spec['channels'] as Obj) ?? {};
  const endpoints: Endpoint[] = [];

  for (const [channelName, channelDefRaw] of Object.entries(channels)) {
    const channelDef = maybeResolve(spec, channelDefRaw);
    const bindingsStr = extractProtocolBinding(channelDef['bindings'] as Obj | undefined, spec);

    // Channel parameters -> path params
    const channelParams: Param[] = [];
    const paramDefs = (channelDef['parameters'] as Obj) ?? {};
    for (const [pname, pdefRaw] of Object.entries(paramDefs)) {
      const pdef = maybeResolve(spec, pdefRaw);
      const schema = (pdef['schema'] as Obj) ?? {};
      channelParams.push({
        name: pname,
        type: extractType(schema, spec),
        required: true,
        description: ((pdef['description'] as string) ?? '').replace(/\n/g, ' ').trim() || undefined,
        nullable: false,
        isArray: false,
      });
    }

    for (const operation of ['subscribe', 'publish'] as const) {
      const opDefRaw = channelDef[operation];
      if (!opDefRaw || typeof opDefRaw !== 'object') continue;
      const opDef = maybeResolve(spec, opDefRaw);

      const method = operation === 'subscribe' ? 'SUB' : 'PUB';
      const opSummary = (
        (opDef['summary'] as string) ||
        (opDef['description'] as string) ||
        ''
      ).trim().split('\n')[0];

      const opBindingsStr = extractProtocolBinding(opDef['bindings'] as Obj | undefined, spec);
      const combinedBindings = bindingsStr || opBindingsStr;

      // Message (may have oneOf)
      const message = opDef['message'] as Obj | undefined;
      const msgs: unknown[] = message && (message['oneOf'] as unknown[])
        ? (message['oneOf'] as unknown[])
        : message ? [message] : [{}];

      for (const msg of msgs) {
        const { payloadParams, headerParams, summary: msgSummary, responseFields } = compileMessage(msg, spec);
        const summary = opSummary || msgSummary;

        const required = [
          ...payloadParams.filter((p) => p.required),
          ...channelParams,
        ];
        const optional = [
          ...payloadParams.filter((p) => !p.required),
        ];

        // Headers as optional params with header: prefix
        for (const hp of headerParams) {
          optional.push({ ...hp, name: `header:${hp.name}` });
        }

        const responseSchemas: ResponseSchema[] = [];
        if (responseFields.length > 0) {
          responseSchemas.push({
            statusCode: method,
            description: 'message payload',
            fields: responseFields,
          });
        }

        const descParts = summary ? [summary] : [];
        if (combinedBindings) descParts.push(`[${combinedBindings}]`);

        endpoints.push({
          method,
          path: channelName,
          description: descParts.join(' ') || undefined,
          requiredParams: required,
          optionalParams: optional,
          allParams: [...required, ...optional],
          responses: responseSchemas,
          errors: [],
        });
      }
    }
  }

  return {
    version: 'v0.3',
    apiName,
    baseUrl,
    apiVersion,
    auth: authScheme || undefined,
    endpoints,
    getEndpoint(m: string, p: string): Endpoint | undefined {
      return this.endpoints.find((e) => e.method === m && e.path === p);
    },
  };
}

// ── v3 compilation ────────────────────────────────────────────────────────────

function compileV3(spec: Obj, apiName: string, baseUrl: string, apiVersion: string | undefined, authScheme: string): LAPSpec {
  const channels = (spec['channels'] as Obj) ?? {};
  const operations = (spec['operations'] as Obj) ?? {};
  const endpoints: Endpoint[] = [];

  if (Object.keys(operations).length > 0) {
    for (const [opId, opDefRaw] of Object.entries(operations)) {
      const opDef = maybeResolve(spec, opDefRaw);
      const action = (opDef['action'] as string) || 'send';
      const method = action === 'send' ? 'PUB' : 'SUB';

      // Resolve channel reference
      const channelRef = opDef['channel'] as Obj | string | undefined;
      let channelName: string;
      let channelDef: Obj;

      if (channelRef && typeof channelRef === 'object' && '$ref' in channelRef) {
        const refPath = channelRef['$ref'] as string;
        channelName = refPath.split('/').pop() || opId;
        channelDef = resolveRef(spec, refPath);
      } else if (typeof channelRef === 'string') {
        channelName = channelRef;
        channelDef = (channels[channelRef] as Obj) ?? {};
      } else {
        channelName = opId;
        channelDef = {};
      }

      channelDef = maybeResolve(spec, channelDef);
      const bindingsStr = extractProtocolBinding(
        { ...(channelDef['bindings'] as Obj ?? {}), ...(opDef['bindings'] as Obj ?? {}) },
        spec,
      );

      const opSummary = (
        (opDef['summary'] as string) || (opDef['description'] as string) || ''
      ).trim().split('\n')[0];
      const address = (channelDef['address'] as string) || channelName;

      // Messages from operation or channel
      let opMessages: Obj | unknown[] = (opDef['messages'] as Obj) ?? {};
      if (typeof opMessages === 'object' && !Array.isArray(opMessages) && Object.keys(opMessages).length === 0) {
        opMessages = (channelDef['messages'] as Obj) ?? {};
      }

      let msgList: unknown[];
      if (Array.isArray(opMessages)) {
        msgList = opMessages;
      } else if (typeof opMessages === 'object') {
        msgList = Object.values(opMessages);
      } else {
        msgList = opMessages ? [opMessages] : [];
      }
      if (msgList.length === 0) msgList = [{}];

      for (const msg of msgList) {
        const { payloadParams, headerParams, summary: msgSummary, responseFields } = compileMessage(msg, spec);
        const summary = opSummary || msgSummary;

        const required = payloadParams.filter((p) => p.required);
        const optional = payloadParams.filter((p) => !p.required);

        for (const hp of headerParams) {
          optional.push({ ...hp, name: `header:${hp.name}` });
        }

        const responseSchemas: ResponseSchema[] = [];
        if (responseFields.length > 0) {
          responseSchemas.push({
            statusCode: method,
            description: 'message payload',
            fields: responseFields,
          });
        }

        const descParts = summary ? [summary] : [];
        if (bindingsStr) descParts.push(`[${bindingsStr}]`);

        endpoints.push({
          method,
          path: address,
          description: descParts.join(' ') || undefined,
          requiredParams: required,
          optionalParams: optional,
          allParams: [...required, ...optional],
          responses: responseSchemas,
          errors: [],
        });
      }
    }
  } else {
    // Fallback: v3 without operations block, just channels with messages
    for (const [channelName, channelDefRaw] of Object.entries(channels)) {
      const channelDef = maybeResolve(spec, channelDefRaw);
      const address = (channelDef['address'] as string) || channelName;
      const messages = (channelDef['messages'] as Obj) ?? {};

      for (const [, msgRaw] of Object.entries(messages)) {
        const { payloadParams, headerParams, summary: msgSummary, responseFields } = compileMessage(msgRaw, spec);

        const required = payloadParams.filter((p) => p.required);
        const optional = payloadParams.filter((p) => !p.required);

        for (const hp of headerParams) {
          optional.push({ ...hp, name: `header:${hp.name}` });
        }

        const responseSchemas: ResponseSchema[] = [];
        if (responseFields.length > 0) {
          responseSchemas.push({
            statusCode: 'MSG',
            description: 'message payload',
            fields: responseFields,
          });
        }

        endpoints.push({
          method: 'MSG',
          path: address,
          description: msgSummary || undefined,
          requiredParams: required,
          optionalParams: optional,
          allParams: [...required, ...optional],
          responses: responseSchemas,
          errors: [],
        });
      }
    }
  }

  return {
    version: 'v0.3',
    apiName,
    baseUrl,
    apiVersion,
    auth: authScheme || undefined,
    endpoints,
    getEndpoint(m: string, p: string): Endpoint | undefined {
      return this.endpoints.find((e) => e.method === m && e.path === p);
    },
  };
}

// Exported for testing
export { resolveRef, extractType };

// ── Main compiler ─────────────────────────────────────────────────────────────

export function compileAsyncApi(specPath: string): LAPSpec {
  const filePath = path.resolve(specPath);
  const stat = fs.statSync(filePath);

  if (stat.size > 50 * 1024 * 1024) {
    throw new Error(`AsyncAPI spec too large: ${stat.size} bytes (max 50MB)`);
  }

  const raw = fs.readFileSync(filePath, 'utf-8');
  const ext = path.extname(filePath).toLowerCase();

  let spec: Obj;
  if (ext === '.yaml' || ext === '.yml') {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const yaml = require('js-yaml') as typeof import('js-yaml');
    spec = yaml.load(raw) as Obj;
  } else {
    spec = JSON.parse(raw) as Obj;
  }

  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) {
    throw new Error('Invalid AsyncAPI spec: expected a YAML/JSON mapping');
  }

  const info = (spec['info'] as Obj) ?? {};
  const apiName = (info['title'] as string) || path.basename(filePath, ext);
  const apiVersion = (info['version'] as string) || undefined;
  const baseUrl = getServersUrl(spec);
  const authScheme = extractSecuritySchemes(spec) || inferAuthFromAsyncParams(spec);

  const version = detectVersion(spec);
  if (version >= 3) {
    return compileV3(spec, apiName, baseUrl, apiVersion, authScheme);
  }
  return compileV2(spec, apiName, baseUrl, apiVersion, authScheme);
}
