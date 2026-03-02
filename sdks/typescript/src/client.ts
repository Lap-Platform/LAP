import * as fs from 'fs';
import * as http from 'http';
import * as https from 'https';
import { parse, LAPSpec } from './parser';

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
    const url = `${registryUrl.replace(/\/$/, '')}/specs/${encodeURIComponent(apiName)}`;
    const text = await this._fetch(url);
    return parse(text);
  }

  private _fetch(url: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const mod = url.startsWith('https') ? https : http;
      mod.get(url, res => {
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
