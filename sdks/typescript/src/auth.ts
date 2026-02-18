/**
 * LAP CLI authentication -- browser-based GitHub OAuth flow.
 *
 * Uses only Node.js stdlib (no extra dependencies).
 * Credentials stored in ~/.lap/credentials.json (shared with Python CLI).
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as http from 'http';
import * as https from 'https';
import { exec } from 'child_process';

const DEFAULT_REGISTRY = 'https://registry.lap.sh';
const CREDENTIALS_DIR = path.join(os.homedir(), '.lap');
const CREDENTIALS_FILE = path.join(CREDENTIALS_DIR, 'credentials.json');

export function getRegistryUrl(): string {
  return (process.env.LAP_REGISTRY || DEFAULT_REGISTRY).replace(/\/$/, '');
}

// ── Credentials ─────────────────────────────────────────────────────

export interface Credentials {
  token: string;
  username: string;
}

export function loadCredentials(): Credentials | null {
  if (!fs.existsSync(CREDENTIALS_FILE)) return null;
  try {
    return JSON.parse(fs.readFileSync(CREDENTIALS_FILE, 'utf-8'));
  } catch {
    return null;
  }
}

export function saveCredentials(token: string, username: string): void {
  fs.mkdirSync(CREDENTIALS_DIR, { recursive: true });
  fs.writeFileSync(CREDENTIALS_FILE, JSON.stringify({ token, username }, null, 2));
  // Restrict perms on non-Windows
  if (process.platform !== 'win32') {
    fs.chmodSync(CREDENTIALS_FILE, 0o600);
  }
}

export function clearCredentials(): void {
  if (fs.existsSync(CREDENTIALS_FILE)) {
    fs.unlinkSync(CREDENTIALS_FILE);
  }
}

export function getToken(): string | null {
  const creds = loadCredentials();
  return creds ? creds.token : null;
}

// ── HTTP helpers ────────────────────────────────────────────────────

export function apiRequest(
  method: string,
  urlPath: string,
  body?: unknown,
  token?: string
): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const baseUrl = getRegistryUrl();
    const fullUrl = new URL(urlPath, baseUrl);
    const mod = fullUrl.protocol === 'https:' ? https : http;

    const headers: Record<string, string> = { Accept: 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let data: string | undefined;
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      data = JSON.stringify(body);
      headers['Content-Length'] = Buffer.byteLength(data).toString();
    }

    const req = mod.request(
      fullUrl,
      { method, headers },
      (res) => {
        let responseData = '';
        res.on('data', (chunk: Buffer) => (responseData += chunk));
        res.on('end', () => {
          if (res.statusCode && res.statusCode >= 400) {
            let errMsg: string;
            try {
              const parsed = JSON.parse(responseData);
              errMsg = parsed.error || parsed.message || responseData;
            } catch {
              errMsg = responseData || `HTTP ${res.statusCode}`;
            }
            reject(new Error(errMsg));
          } else {
            try {
              resolve(JSON.parse(responseData));
            } catch {
              resolve({});
            }
          }
        });
      }
    );

    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

// ── SSE stream ──────────────────────────────────────────────────────

export function pollSseStream(
  sessionId: string
): Promise<{ token: string; username: string }> {
  return new Promise((resolve, reject) => {
    const baseUrl = getRegistryUrl();
    const fullUrl = new URL(`/auth/cli/stream/${sessionId}`, baseUrl);
    const mod = fullUrl.protocol === 'https:' ? https : http;

    const req = mod.get(
      fullUrl,
      { headers: { Accept: 'text/event-stream' }, timeout: 130_000 },
      (res) => {
        let buffer = '';

        res.on('data', (chunk: Buffer) => {
          buffer += chunk.toString();
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;
            const payload = trimmed.slice(6);
            try {
              const data = JSON.parse(payload);
              if (data.token && data.username) {
                res.destroy();
                resolve({ token: data.token, username: data.username });
                return;
              }
              if (data.error) {
                res.destroy();
                reject(new Error(`Authentication failed: ${data.error}`));
                return;
              }
            } catch {
              // Ignore parse errors
            }
          }
        });

        res.on('end', () => {
          reject(new Error('Authentication timed out. Please try again.'));
        });

        res.on('error', reject);
      }
    );

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Connection timed out.'));
    });
  });
}

// ── Browser open ────────────────────────────────────────────────────

export function openBrowser(url: string): void {
  const cmd =
    process.platform === 'win32' ? `start "" "${url}"` :
    process.platform === 'darwin' ? `open "${url}"` :
    `xdg-open "${url}"`;
  exec(cmd);
}
