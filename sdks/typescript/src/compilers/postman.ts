/**
 * Postman Collection v2.x -> LAPSpec.
 * Handles nested folders, variable interpolation, body parsing,
 * auth detection (explicit + heuristic), and response examples.
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  LAPSpec,
  Endpoint,
  Param,
  ResponseSchema,
  ResponseField,
  ErrorSchema,
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

// Parameter names that strongly suggest authentication
const AUTH_PARAM_NAMES = new Set([
  'api_key', 'apikey', 'api-key',
  'token', 'access_token', 'x-api-key',
  'authorization', 'auth_token', 'secret',
  'api_secret', 'app_key', 'appkey', 'client_secret',
  'subscription-key', 'ocp-apim-subscription-key',
  'x-auth-token', 'api_token',
]);

// Description keywords that suggest an auth parameter
const AUTH_DESC_KEYWORDS = [
  'api key', 'authentication', 'auth token',
  'access token', 'your key', 'your token',
];

// Common auto-headers to skip when extracting header params
const SKIP_HEADERS = new Set([
  'content-type', 'accept', 'authorization', 'user-agent', 'host',
]);

// ── Variable resolution ───────────────────────────────────────────────────────

function collectVariables(collection: Obj): Record<string, string> {
  const variables: Record<string, string> = {};
  const vars = (collection['variable'] as Obj[]) || [];
  for (const v of vars) {
    if (v && typeof v === 'object' && 'key' in v) {
      variables[v['key'] as string] = (v['value'] as string) || '';
    }
  }
  return variables;
}

function resolveVariables(text: string, variables: Record<string, string>): string {
  if (!text) return text;
  return text.replace(/\{\{(\w+)\}\}/g, (_match, key) => {
    return variables[key] !== undefined ? variables[key] : `{{${key}}}`;
  });
}

// ── URL helpers ───────────────────────────────────────────────────────────────

function getUrlString(url: unknown): string {
  if (typeof url === 'string') return url;
  if (url && typeof url === 'object') {
    const u = url as Obj;
    const raw = (u['raw'] as string) || '';
    if (raw) return raw;
    // Build from parts
    const protocol = (u['protocol'] as string) || 'https';
    const hostParts = (u['host'] as string[]) || [];
    const host = hostParts.join('.');
    const pathParts = (u['path'] as string[]) || [];
    const pathStr = pathParts.map(String).join('/');
    return `${protocol}://${host}/${pathStr}`;
  }
  return '';
}

/** Replace {{var}} with :var for LAP path convention. */
function replaceVars(segment: string): string {
  return segment.replace(/\{\{(\w+)\}\}/g, ':$1');
}

/** Extract path portion from a URL string, stripping the base. */
function extractPath(url: unknown, variables: Record<string, string>, baseUrl: string): string {
  const urlStr = resolveVariables(getUrlString(url), variables);

  let pathStr: string;
  if (baseUrl && urlStr.startsWith(baseUrl)) {
    pathStr = urlStr.slice(baseUrl.length);
  } else {
    // Strip protocol + host
    const m = urlStr.match(/^https?:\/\/[^/]+(\/.*)?$/);
    pathStr = m ? (m[1] || '/') : urlStr;
  }

  // Remove query string
  pathStr = pathStr.split('?')[0];

  // Replace {{var}} -> :var
  pathStr = pathStr.replace(/\{\{(\w+)\}\}/g, ':$1');

  if (!pathStr.startsWith('/')) pathStr = '/' + pathStr;
  return pathStr || '/';
}

/** Extract base URL from collection variables or first request URL. */
function extractBaseUrl(collection: Obj, variables: Record<string, string>): string {
  // Check collection variables for baseUrl
  if (variables['baseUrl']) return variables['baseUrl'];
  if (variables['base_url']) return variables['base_url'];
  if (variables['BASE_URL']) return variables['BASE_URL'];

  // Try to find from first request
  const items = flattenItems((collection['item'] as unknown[]) || []);
  for (const item of items) {
    const req = (item as Obj)['request'] as Obj | undefined;
    if (!req || typeof req !== 'object') continue;
    const urlStr = resolveVariables(getUrlString(req['url']), variables);
    const m = urlStr.match(/^(https?:\/\/[^/]+)/);
    if (m) return m[1];
  }

  return '';
}

// ── Item flattening ───────────────────────────────────────────────────────────

/** Flatten nested folder items into a flat list of request items. */
function flattenItems(items: unknown[], depth = 0): Obj[] {
  if (depth > 10) return [];
  const result: Obj[] = [];
  for (const raw of items) {
    if (!raw || typeof raw !== 'object') continue;
    const item = raw as Obj;
    if (Array.isArray(item['item'])) {
      result.push(...flattenItems(item['item'] as unknown[], depth + 1));
    } else if (item['request']) {
      result.push(item);
    }
  }
  return result;
}

// ── Auth extraction ───────────────────────────────────────────────────────────

function extractPostmanAuth(auth: Obj | undefined): string {
  if (!auth) return '';
  const t = (auth['type'] as string) || '';

  if (t === 'bearer') return 'Bearer token';
  if (t === 'basic') return 'Basic username:password';
  if (t === 'apikey') {
    // Extract details from apikey array
    const apikeyItems = (auth['apikey'] as Obj[]) || [];
    let keyName = 'key';
    let keyIn = 'header';
    for (const item of apikeyItems) {
      if (item && typeof item === 'object') {
        if (item['key'] === 'key') keyName = (item['value'] as string) || 'key';
        else if (item['key'] === 'in') keyIn = (item['value'] as string) || 'header';
      }
    }
    return `ApiKey ${keyName} in ${keyIn}`;
  }
  if (t === 'oauth2') return 'OAuth2';
  if (t === 'noauth') return '';
  if (t) return t;
  return '';
}

/** Heuristic: scan all collection items for query/header params that suggest auth. */
function inferAuthFromPostmanParams(collection: Obj): string {
  const items = flattenItems((collection['item'] as unknown[]) || []);

  for (const item of items) {
    const req = item['request'] as Obj | undefined;
    if (!req || typeof req !== 'object') continue;

    // Check query params from URL object
    const urlObj = req['url'];
    if (urlObj && typeof urlObj === 'object') {
      const queries = ((urlObj as Obj)['query'] as Obj[]) || [];
      for (const q of queries) {
        if (!q || typeof q !== 'object') continue;
        const name = ((q['key'] as string) || '').trim();
        const nameLower = name.toLowerCase();
        const desc = ((q['description'] as string) || '').toLowerCase();
        if (AUTH_PARAM_NAMES.has(nameLower)) return `ApiKey ${name} in query`;
        if (AUTH_DESC_KEYWORDS.some((kw) => desc.includes(kw))) return `ApiKey ${name} in query`;
      }
    }

    // Check header params
    const headers = (req['header'] as Obj[]) || [];
    for (const h of headers) {
      if (!h || typeof h !== 'object') continue;
      const name = ((h['key'] as string) || '').trim();
      const nameLower = name.toLowerCase();
      const desc = ((h['description'] as string) || '').toLowerCase();
      if (AUTH_PARAM_NAMES.has(nameLower)) return `ApiKey ${name} in header`;
      if (AUTH_DESC_KEYWORDS.some((kw) => desc.includes(kw))) return `ApiKey ${name} in header`;
    }
  }

  return '';
}

// ── Parameter extraction ──────────────────────────────────────────────────────

function extractPathParams(url: unknown): Param[] {
  if (!url || typeof url !== 'object') return [];
  const vars = ((url as Obj)['variable'] as Obj[]) || [];
  const params: Param[] = [];

  for (const v of vars) {
    if (!v || typeof v !== 'object') continue;
    const name = (v['key'] as string) || '';
    if (!name) continue;
    params.push({
      name,
      type: 'str',
      required: true,
      description: v['description']
        ? stripHtml((v['description'] as string)).replace(/\n/g, ' ').trim()
        : undefined,
      nullable: false,
      isArray: false,
    });
  }

  return params;
}

function extractQueryParams(url: unknown): Param[] {
  if (!url || typeof url !== 'object') return [];
  const queries = ((url as Obj)['query'] as Obj[]) || [];
  const params: Param[] = [];

  for (const q of queries) {
    if (!q || typeof q !== 'object') continue;
    const name = (q['key'] as string) || '';
    if (!name) continue;
    const disabled = Boolean(q['disabled']);
    params.push({
      name,
      type: 'str',
      required: !disabled,
      description: q['description']
        ? stripHtml((q['description'] as string)).replace(/\n/g, ' ').trim()
        : undefined,
      nullable: false,
      isArray: false,
    });
  }

  return params;
}

function extractHeaderParams(request: Obj): Param[] {
  const headers = (request['header'] as Obj[]) || [];
  const params: Param[] = [];

  for (const h of headers) {
    if (!h || typeof h !== 'object') continue;
    const name = (h['key'] as string) || '';
    if (!name || SKIP_HEADERS.has(name.toLowerCase())) continue;
    const disabled = Boolean(h['disabled']);
    params.push({
      name,
      type: 'str',
      required: !disabled,
      description: h['description']
        ? stripHtml((h['description'] as string)).replace(/\n/g, ' ').trim()
        : undefined,
      nullable: false,
      isArray: false,
    });
  }

  return params;
}

// ── Body extraction ───────────────────────────────────────────────────────────

function guessType(val: unknown): string {
  if (val === null) return 'any';
  if (typeof val === 'boolean') return 'bool';
  if (typeof val === 'number') return Number.isInteger(val) ? 'int' : 'num';
  if (typeof val === 'string') return 'str';
  if (Array.isArray(val)) return `[${val.length ? guessType(val[0]) : 'any'}]`;
  if (typeof val === 'object') return 'map';
  return 'any';
}

function isLikelyOptional(_key: string, value: unknown): boolean {
  if (value === null) return true;
  if (typeof value === 'string' && value.trim() === '') return true;
  if (typeof value === 'string' && value.startsWith('{{') && value.endsWith('}}')) return false;
  if (Array.isArray(value) && value.length === 0) return true;
  return false;
}

function extractBodyParams(body: Obj | undefined): Param[] {
  if (!body) return [];
  const mode = (body['mode'] as string) || '';
  const params: Param[] = [];

  if (mode === 'raw') {
    const raw = (body['raw'] as string) || '';
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        for (const [name, val] of Object.entries(parsed as Obj)) {
          params.push({
            name,
            type: guessType(val),
            required: !isLikelyOptional(name, val),
            description: undefined,
            nullable: val === null,
            isArray: guessType(val).startsWith('['),
          });
        }
      }
    } catch {
      // not JSON, ignore
    }
  } else if (mode === 'urlencoded' || mode === 'formdata') {
    const fields = (body[mode] as Obj[]) || [];
    for (const f of fields) {
      if (!f || typeof f !== 'object') continue;
      const name = (f['key'] as string) || '';
      if (!name) continue;
      const disabled = Boolean(f['disabled']);
      const itemType = (f['type'] as string) || 'text';
      const paramType = itemType === 'file' ? 'file' : 'str';
      params.push({
        name,
        type: paramType,
        required: !disabled,
        description: f['description']
          ? stripHtml((f['description'] as string)).replace(/\n/g, ' ').trim()
          : undefined,
        nullable: false,
        isArray: false,
      });
    }
  }

  return params;
}

// ── Response extraction ───────────────────────────────────────────────────────

function fieldsFromDict(data: Obj, depth = 0, maxDepth = 2): ResponseField[] {
  const fields: ResponseField[] = [];
  for (const [key, val] of Object.entries(data)) {
    let nested: ResponseField[] | undefined;
    if (val && typeof val === 'object' && !Array.isArray(val) && depth < maxDepth) {
      const children = fieldsFromDict(val as Obj, depth + 1, maxDepth);
      if (children.length > 0) nested = children;
    }
    fields.push({
      name: key,
      type: guessType(val),
      nullable: val === null,
      nested,
    });
  }
  return fields;
}

function extractResponseSchemas(item: Obj): [ResponseSchema[], ErrorSchema[]] {
  const responses = (item['response'] as unknown[]) || [];
  if (!responses.length) return [[], []];

  const responseSchemas: ResponseSchema[] = [];
  const errorSchemas: ErrorSchema[] = [];

  for (const raw of responses) {
    if (!raw || typeof raw !== 'object') continue;
    const resp = raw as Obj;
    const code = String(resp['code'] ?? resp['status'] ?? '200');
    const name = (resp['name'] as string) || '';
    const bodyStr = (resp['body'] as string) || '';

    let fields: ResponseField[] = [];
    if (bodyStr) {
      try {
        const parsed = JSON.parse(bodyStr);
        if (parsed && typeof parsed === 'object') {
          if (Array.isArray(parsed)) {
            if (parsed.length > 0 && typeof parsed[0] === 'object' && parsed[0] !== null) {
              fields = fieldsFromDict(parsed[0] as Obj);
            }
          } else {
            fields = fieldsFromDict(parsed as Obj);
          }
        }
      } catch {
        // not JSON
      }
    }

    if (code.startsWith('2') || code.startsWith('1')) {
      if (fields.length > 0) {
        responseSchemas.push({
          statusCode: code,
          description: name || undefined,
          fields,
        });
      }
    } else {
      errorSchemas.push({
        statusCode: code,
        description: name || undefined,
      });
    }
  }

  return [responseSchemas, errorSchemas];
}

// ── Common prefix for baseUrl fallback ────────────────────────────────────────

function findCommonPrefix(urls: string[]): string {
  const cleaned = urls
    .map((u) => u.replace(/\{\{[^}]+\}\}/g, '').split('?')[0])
    .filter((u) => u.startsWith('http'));
  if (!cleaned.length) return '';

  let prefix = cleaned[0];
  for (let i = 1; i < cleaned.length; i++) {
    while (!cleaned[i].startsWith(prefix)) {
      const slash = prefix.lastIndexOf('/');
      if (slash <= 8) return ''; // past protocol://
      prefix = prefix.slice(0, slash);
    }
  }

  try {
    const u = new URL(prefix);
    return u.origin + (u.pathname === '/' ? '' : u.pathname);
  } catch {
    return '';
  }
}

// ── Main compiler ─────────────────────────────────────────────────────────────

export function compilePostman(specPath: string): LAPSpec {
  const filePath = path.resolve(specPath);
  const stat = fs.statSync(filePath);

  if (stat.size > 50 * 1024 * 1024) {
    throw new Error(`Postman collection too large: ${stat.size} bytes (max 50MB)`);
  }

  const raw = fs.readFileSync(filePath, 'utf-8');
  const parsed = JSON.parse(raw) as Obj;

  // Handle both wrapped {"collection": {...}} and direct format
  let collection: Obj;
  if (parsed['collection'] && typeof parsed['collection'] === 'object' && !Array.isArray(parsed['collection'])) {
    collection = parsed['collection'] as Obj;
  } else if (parsed['info']) {
    collection = parsed;
  } else {
    throw new Error("Invalid Postman Collection: missing 'info' or 'collection' key");
  }

  const info = (collection['info'] as Obj) || {};
  const variables = collectVariables(collection);
  const collectionBaseUrl = extractBaseUrl(collection, variables);

  // Auth -- explicit first, then heuristic
  const authScheme =
    extractPostmanAuth(collection['auth'] as Obj | undefined) ||
    inferAuthFromPostmanParams(collection);

  // Flatten items recursively
  const items = flattenItems((collection['item'] as unknown[]) || []);
  const urls: string[] = [];
  const endpoints: Endpoint[] = [];

  for (const item of items) {
    const req = item['request'] as Obj | undefined;
    if (!req || typeof req !== 'object') continue;

    // Simple string request (just a URL) -- skip
    if (typeof item['request'] === 'string') continue;

    const method = ((req['method'] as string) || 'GET').toUpperCase();
    const urlObj = req['url'];
    const urlStr = getUrlString(urlObj);
    urls.push(urlStr);

    const epPath = extractPath(urlObj, variables, collectionBaseUrl);

    // Collect params
    const pathParams = extractPathParams(urlObj);
    const queryParams = extractQueryParams(urlObj);
    const headerParams = extractHeaderParams(req);
    const bodyParams = extractBodyParams(req['body'] as Obj | undefined);

    const requiredParams = [
      ...pathParams,
      ...queryParams.filter((p) => p.required),
    ];
    const optionalParams = [
      ...queryParams.filter((p) => !p.required),
      ...headerParams,
    ];

    const [responseSchemas, errorSchemas] = extractResponseSchemas(item);

    const summary = stripHtml(
      (item['name'] as string) || '',
    ).replace(/\n/g, ' ').trim();

    // Per-request auth override
    const reqAuth = req['auth'] as Obj | undefined;
    const epAuth = reqAuth ? extractPostmanAuth(reqAuth) : undefined;

    const endpoint: Endpoint = {
      method,
      path: epPath,
      description: summary || undefined,
      auth: epAuth || undefined,
      requiredParams,
      optionalParams,
      allParams: [...requiredParams, ...optionalParams, ...bodyParams],
      requestBody: bodyParams.length > 0 ? bodyParams : undefined,
      responses: responseSchemas,
      errors: errorSchemas,
    };

    endpoints.push(endpoint);
  }

  // Derive baseUrl from variable or common URL prefix
  const baseUrl = collectionBaseUrl || findCommonPrefix(urls);

  const apiName = (info['name'] as string) || path.basename(filePath, path.extname(filePath));
  const versionRaw = info['version'];
  const apiVersion = typeof versionRaw === 'string' ? versionRaw : undefined;

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
