import * as fs from 'fs';
import * as http from 'http';
import * as https from 'https';
import { parse, LAPSpec, SearchResponse } from './parser';

export interface ToContextOptions {
  lean?: boolean;
  endpoints?: string[]; // filter by "METHOD /path"
}

export class LAPClient {
  loadFile(filePath: string): LAPSpec {
    const text = fs.readFileSync(filePath, 'utf-8');
    return parse(text);
  }

  loadString(text: string): LAPSpec {
    return parse(text);
  }

  async fromRegistry(registryUrl: string, apiName: string): Promise<LAPSpec> {
    const url = `${registryUrl.replace(/\/$/, '')}/v1/apis/${encodeURIComponent(apiName)}`;
    const text = await this._fetch(url);
    return parse(text);
  }

  async search(
    registryUrl: string,
    query: string,
    options?: { tag?: string; sort?: string; limit?: number; offset?: number }
  ): Promise<SearchResponse> {
    const params = new URLSearchParams({ q: query });
    if (options?.tag) params.set('tag', options.tag);
    if (options?.sort) params.set('sort', options.sort);
    if (options?.limit !== undefined) params.set('limit', String(options.limit));
    if (options?.offset !== undefined) params.set('offset', String(options.offset));

    const url = `${registryUrl.replace(/\/$/, '')}/v1/search?${params}`;
    const text = await this._fetch(url, { Accept: 'application/json' });
    return JSON.parse(text) as SearchResponse;
  }

  private _fetch(url: string, headers?: Record<string, string>): Promise<string> {
    return new Promise((resolve, reject) => {
      const mod = url.startsWith('https') ? https : http;
      const options = headers ? { headers } : {};
      mod.get(url, options, res => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          if (res.statusCode && res.statusCode >= 400) {
            reject(new Error(`Registry returned ${res.statusCode}: ${data}`));
          } else {
            resolve(data);
          }
        });
      }).on('error', reject);
    });
  }
}

export function toContext(spec: LAPSpec, opts: ToContextOptions = {}): string {
  const lines: string[] = [];
  lines.push(`API: ${spec.apiName}`);
  lines.push(`Base: ${spec.baseUrl}`);
  if (spec.auth) lines.push(`Auth: ${spec.auth}`);
  lines.push('');

  for (const ep of spec.endpoints) {
    if (opts.endpoints && !opts.endpoints.includes(`${ep.method} ${ep.path}`)) continue;

    lines.push(`${ep.method} ${ep.path}`);
    if (!opts.lean && ep.description) lines.push(`  ${ep.description}`);

    const formatParams = (params: typeof ep.requiredParams, label: string) => {
      if (params.length === 0) return;
      const parts = params.map(p => {
        let s = `${p.name}: ${p.isArray ? '[' + p.type + ']' : p.type}`;
        if (p.nullable) s += '?';
        if (p.enumValues) s += `(${p.enumValues.join('/')})`;
        if (p.defaultValue) s += `=${p.defaultValue}`;
        if (!opts.lean && p.description) s += ` # ${p.description}`;
        return s;
      });
      lines.push(`  ${label}: {${parts.join(', ')}}`);
    };

    formatParams(ep.requiredParams, 'Required');
    formatParams(ep.optionalParams, 'Optional');

    for (const r of ep.responses) {
      if (r.fields.length > 0) {
        const fields = r.fields.map(f => `${f.name}: ${f.type}${f.nullable ? '?' : ''}`).join(', ');
        lines.push(`  → ${r.statusCode} {${fields}}`);
      } else if (r.description) {
        lines.push(`  → ${r.statusCode} ${r.description}`);
      }
    }
    lines.push('');
  }

  return lines.join('\n');
}
