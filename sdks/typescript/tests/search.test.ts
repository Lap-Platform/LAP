import { describe, it, before, after } from 'node:test';
import * as assert from 'node:assert';
import * as http from 'node:http';
import { LAPClient } from '../src/client';

describe('LAPClient.search', () => {
  let server: http.Server;
  let baseUrl: string;
  let captured: { url?: string; headers?: http.IncomingHttpHeaders };
  let mockStatus = 200;
  let mockBody = JSON.stringify({
    query: 'test',
    results: [],
    total: 0,
    limit: 20,
    offset: 0,
    has_more: false,
  });

  before(async () => {
    server = http.createServer((req, res) => {
      captured = { url: req.url, headers: req.headers };
      res.writeHead(mockStatus, { 'Content-Type': 'application/json' });
      res.end(mockBody);
    });
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    const addr = server.address() as { port: number };
    baseUrl = `http://127.0.0.1:${addr.port}`;
  });

  after(() => {
    server.close();
  });

  it('builds correct URL with query only', async () => {
    const client = new LAPClient();
    await client.search(baseUrl, 'stripe');
    assert.ok(captured.url);
    assert.strictEqual(captured.url, '/v1/search?q=stripe');
  });

  it('builds correct URL with all options', async () => {
    const client = new LAPClient();
    await client.search(baseUrl, 'stripe', { tag: 'pay', sort: 'popularity', limit: 5, offset: 10 });
    assert.ok(captured.url);
    const params = new URL(captured.url, baseUrl).searchParams;
    assert.strictEqual(params.get('q'), 'stripe');
    assert.strictEqual(params.get('tag'), 'pay');
    assert.strictEqual(params.get('sort'), 'popularity');
    assert.strictEqual(params.get('limit'), '5');
    assert.strictEqual(params.get('offset'), '10');
  });

  it('sends Accept: application/json header', async () => {
    const client = new LAPClient();
    await client.search(baseUrl, 'test');
    assert.ok(captured.headers);
    assert.strictEqual(captured.headers.accept, 'application/json');
  });

  it('parses JSON response correctly', async () => {
    const canned = {
      query: 'stripe',
      results: [{ name: 'Stripe', description: 'Payments', endpoints: 587 }],
      total: 1,
      limit: 20,
      offset: 0,
      has_more: false,
    };
    mockBody = JSON.stringify(canned);
    const client = new LAPClient();
    const result = await client.search(baseUrl, 'stripe');
    assert.strictEqual(result.query, 'stripe');
    assert.strictEqual(result.results.length, 1);
    assert.strictEqual(result.results[0].name, 'Stripe');
    assert.strictEqual(result.total, 1);
    // Reset
    mockBody = JSON.stringify({ query: 'test', results: [], total: 0, limit: 20, offset: 0, has_more: false });
  });

  it('rejects on server error', async () => {
    mockStatus = 500;
    const client = new LAPClient();
    await assert.rejects(() => client.search(baseUrl, 'fail'), /500/);
    mockStatus = 200;
  });

  it('strips trailing slash from registryUrl', async () => {
    const client = new LAPClient();
    await client.search(baseUrl + '/', 'test');
    assert.ok(captured.url);
    assert.ok(!captured.url.startsWith('//'), 'URL should not have double slash');
    assert.ok(captured.url.startsWith('/v1/search'), 'URL should start with /v1/search');
  });
});
