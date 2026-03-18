import { describe, it, before, after, beforeEach, afterEach } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as http from 'node:http';
import {
  loadCredentials,
  saveCredentials,
  clearCredentials,
  getToken,
  getRegistryUrl,
  apiRequest,
} from '../src/auth';

// ── helpers ─────────────────────────────────────────────────────────────────

/**
 * Monkey-patch the module-level CREDENTIALS_FILE constant by writing directly
 * to the real credentials path. We instead exercise the module functions with
 * a temp file by writing+reading it in each test so as not to touch the real
 * ~/.lap/credentials.json on the developer's machine.
 *
 * Because `saveCredentials` always writes to the module constant path, we
 * redirect at test level by temporarily swapping process.env.HOME and
 * os.homedir is not patchable. Instead, we directly write JSON to the module-
 * resolved file and read it back -- tests for load/get/clear use temp files
 * by writing them into the actual CREDENTIALS_FILE location and restoring.
 *
 * Simpler approach: test the high-level contract by exercising
 * save -> load -> getToken -> clear in sequence against the real path,
 * capturing the original contents and restoring them in cleanup.
 */
function backupAndRestoreCredentials(): { restore: () => void } {
  const credPath = path.join(os.homedir(), '.lap', 'credentials.json');
  let original: string | null = null;
  let existed = false;

  if (fs.existsSync(credPath)) {
    existed = true;
    original = fs.readFileSync(credPath, 'utf-8');
  }

  return {
    restore() {
      if (existed && original !== null) {
        fs.mkdirSync(path.dirname(credPath), { recursive: true });
        fs.writeFileSync(credPath, original, 'utf-8');
      } else {
        if (fs.existsSync(credPath)) fs.unlinkSync(credPath);
      }
    },
  };
}

// ── Credentials ──────────────────────────────────────────────────────────────

describe('Credentials', () => {
  let restore: () => void;

  before(() => {
    const bak = backupAndRestoreCredentials();
    restore = bak.restore;
    // Start each test group with a clean slate
    clearCredentials();
  });

  after(() => {
    restore();
  });

  it('saves and loads token', () => {
    saveCredentials('tok-abc123', 'alice');
    const creds = loadCredentials();
    assert.ok(creds, 'loadCredentials should return an object after save');
    assert.strictEqual(creds!.token, 'tok-abc123');
    assert.strictEqual(creds!.username, 'alice');
  });

  it('getToken returns saved token', () => {
    saveCredentials('tok-xyz789', 'bob');
    const token = getToken();
    assert.strictEqual(token, 'tok-xyz789');
  });

  it('clear removes credentials', () => {
    saveCredentials('tok-to-delete', 'carol');
    clearCredentials();
    const creds = loadCredentials();
    assert.strictEqual(creds, null, 'loadCredentials should return null after clear');
  });

  it('getToken returns null when no credentials exist', () => {
    clearCredentials();
    const token = getToken();
    assert.strictEqual(token, null);
  });

  it('load with no file returns null', () => {
    clearCredentials();
    const result = loadCredentials();
    assert.strictEqual(result, null);
  });

  it('handles corrupt JSON gracefully', () => {
    // Write corrupt JSON directly to the credentials file
    const credPath = path.join(os.homedir(), '.lap', 'credentials.json');
    fs.mkdirSync(path.dirname(credPath), { recursive: true });
    fs.writeFileSync(credPath, '{ this is not valid json {{{{', 'utf-8');
    const result = loadCredentials();
    assert.strictEqual(result, null, 'loadCredentials should return null for corrupt JSON');
  });
});

// ── Registry URL ─────────────────────────────────────────────────────────────

describe('Registry URL', () => {
  let saved: string | undefined;

  before(() => {
    saved = process.env.LAP_REGISTRY;
  });

  after(() => {
    if (saved !== undefined) {
      process.env.LAP_REGISTRY = saved;
    } else {
      delete process.env.LAP_REGISTRY;
    }
  });

  it('has sensible default', () => {
    delete process.env.LAP_REGISTRY;
    const url = getRegistryUrl();
    assert.ok(url.startsWith('https://'), `Default registry should be https://, got: ${url}`);
    assert.ok(url.includes('lap'), `Default registry URL should reference lap, got: ${url}`);
  });

  it('respects LAP_REGISTRY env var', () => {
    process.env.LAP_REGISTRY = 'http://localhost:9000';
    const url = getRegistryUrl();
    assert.strictEqual(url, 'http://localhost:9000');
  });

  it('strips trailing slash from LAP_REGISTRY', () => {
    process.env.LAP_REGISTRY = 'http://localhost:9000/';
    const url = getRegistryUrl();
    assert.ok(!url.endsWith('/'), `Registry URL should not end with slash, got: ${url}`);
  });
});

// ── apiRequest ───────────────────────────────────────────────────────────────

describe('apiRequest', () => {
  let server: http.Server;
  let baseUrl: string;
  let capturedMethod: string;
  let capturedUrl: string;
  let capturedHeaders: http.IncomingHttpHeaders;
  let capturedBody: string;
  let mockStatus = 200;
  let mockBody = JSON.stringify({ ok: true });
  let savedEnv: string | undefined;

  before(async () => {
    savedEnv = process.env.LAP_REGISTRY;

    server = http.createServer((req, res) => {
      capturedMethod = req.method || '';
      capturedUrl = req.url || '';
      capturedHeaders = req.headers;

      let body = '';
      req.on('data', (chunk: Buffer) => (body += chunk.toString()));
      req.on('end', () => {
        capturedBody = body;
        res.writeHead(mockStatus, { 'Content-Type': 'application/json' });
        res.end(mockBody);
      });
    });

    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    const addr = server.address() as { port: number };
    baseUrl = `http://127.0.0.1:${addr.port}`;
    process.env.LAP_REGISTRY = baseUrl;
  });

  after(() => {
    server.close();
    if (savedEnv !== undefined) {
      process.env.LAP_REGISTRY = savedEnv;
    } else {
      delete process.env.LAP_REGISTRY;
    }
  });

  beforeEach(() => {
    mockStatus = 200;
    mockBody = JSON.stringify({ ok: true });
  });

  it('sends GET request', async () => {
    await apiRequest('GET', '/v1/ping');
    assert.strictEqual(capturedMethod, 'GET');
    assert.strictEqual(capturedUrl, '/v1/ping');
  });

  it('sends Accept: application/json header', async () => {
    await apiRequest('GET', '/v1/ping');
    assert.strictEqual(capturedHeaders['accept'], 'application/json');
  });

  it('sends Authorization header when token provided', async () => {
    await apiRequest('GET', '/v1/ping', undefined, 'my-token');
    assert.strictEqual(capturedHeaders['authorization'], 'Bearer my-token');
  });

  it('sends POST request with JSON body', async () => {
    await apiRequest('POST', '/v1/upload', { name: 'test' });
    assert.strictEqual(capturedMethod, 'POST');
    assert.strictEqual(capturedHeaders['content-type'], 'application/json');
    const parsed = JSON.parse(capturedBody);
    assert.strictEqual(parsed.name, 'test');
  });

  it('parses JSON response', async () => {
    mockBody = JSON.stringify({ result: 'success', count: 42 });
    const data = await apiRequest('GET', '/v1/ping');
    assert.strictEqual((data as { result: string }).result, 'success');
  });

  it('rejects on 4xx error', async () => {
    mockStatus = 404;
    mockBody = JSON.stringify({ error: 'not found' });
    await assert.rejects(() => apiRequest('GET', '/v1/missing'), /not found/);
    mockStatus = 200;
  });

  it('rejects on 5xx error', async () => {
    mockStatus = 500;
    mockBody = JSON.stringify({ error: 'internal server error' });
    await assert.rejects(() => apiRequest('GET', '/v1/broken'), /internal server error/);
    mockStatus = 200;
  });
});
