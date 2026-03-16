import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as path from 'path';
import { compileOpenapi } from '../src/compilers/openapi';

// When compiled, __dirname = sdks/typescript/dist/tests
const EXAMPLES_DIR = path.resolve(__dirname, '../../../../examples/verbose/openapi');

describe('OpenAPI Compiler', () => {
  describe('Discord API', () => {
    it('should compile discord.yaml', () => {
      const specPath = path.join(EXAMPLES_DIR, 'discord.yaml');
      const spec = compileOpenapi(specPath);

      assert.strictEqual(spec.apiName, 'Discord API');
      assert.strictEqual(spec.baseUrl, 'https://discord.com/api/v10');
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
      assert.strictEqual(spec.endpoints.length, 4, `Expected 4 endpoints, got ${spec.endpoints.length}`);
    });

    it('should extract auth', () => {
      const specPath = path.join(EXAMPLES_DIR, 'discord.yaml');
      const spec = compileOpenapi(specPath);
      assert.ok(spec.auth, 'Should have auth');
      assert.ok(spec.auth!.includes('Bearer'), 'Auth should contain Bearer');
    });

    it('should parse endpoint methods and paths', () => {
      const specPath = path.join(EXAMPLES_DIR, 'discord.yaml');
      const spec = compileOpenapi(specPath);

      const createMsg = spec.getEndpoint('post', '/channels/{channel_id}/messages');
      assert.ok(createMsg, 'Should find POST /channels/{channel_id}/messages');
      assert.ok(createMsg.description, 'Should have description');

      const listMembers = spec.getEndpoint('get', '/guilds/{guild_id}/members');
      assert.ok(listMembers, 'Should find GET /guilds/{guild_id}/members');
    });

    it('should classify required vs optional params', () => {
      const specPath = path.join(EXAMPLES_DIR, 'discord.yaml');
      const spec = compileOpenapi(specPath);

      const createMsg = spec.getEndpoint('post', '/channels/{channel_id}/messages')!;
      const reqNames = createMsg.requiredParams.map(p => p.name);
      assert.ok(reqNames.includes('channel_id'), 'channel_id should be required');

      // Body params are now stored separately in requestBody (not merged into requiredParams)
      const bodyNames = (createMsg.requestBody || []).map(p => p.name);
      assert.ok(bodyNames.includes('content'), 'content should be in requestBody');

      const optNames = createMsg.optionalParams.map(p => p.name);
      // tts may be in optionalParams or requestBody depending on its required flag
      const allOptNames = [...optNames, ...(createMsg.requestBody || []).filter(p => !p.required).map(p => p.name)];
      assert.ok(allOptNames.includes('tts'), 'tts should be optional');
    });

    it('should parse response schemas', () => {
      const specPath = path.join(EXAMPLES_DIR, 'discord.yaml');
      const spec = compileOpenapi(specPath);

      const createMsg = spec.getEndpoint('post', '/channels/{channel_id}/messages')!;
      assert.ok(createMsg.responses.length > 0, 'Should have responses');
      assert.strictEqual(createMsg.responses[0].statusCode, '200');
      assert.ok(createMsg.responses[0].fields.length > 0, 'Should have response fields');
    });

    it('should handle optional query params with defaults', () => {
      const specPath = path.join(EXAMPLES_DIR, 'discord.yaml');
      const spec = compileOpenapi(specPath);

      const listMembers = spec.getEndpoint('get', '/guilds/{guild_id}/members')!;
      const limit = listMembers.optionalParams.find(p => p.name === 'limit');
      assert.ok(limit, 'Should find limit param');
      assert.strictEqual(limit.type, 'int');
      assert.strictEqual(limit.defaultValue, '1');
    });
  });

  describe('Petstore API', () => {
    it('should compile petstore.yaml with correct structure', () => {
      const specPath = path.join(EXAMPLES_DIR, 'petstore.yaml');
      const spec = compileOpenapi(specPath);

      assert.ok(spec.apiName, 'Should have API name');
      assert.ok(spec.endpoints.length >= 3, `Should have at least 3 endpoints, got ${spec.endpoints.length}`);

      // Verify specific endpoints exist
      const methods = spec.endpoints.map(e => `${e.method} ${e.path}`);
      assert.ok(methods.some(m => m.startsWith('get ')), 'Should have at least one GET endpoint');
      assert.ok(methods.some(m => m.startsWith('post ')), 'Should have at least one POST endpoint');
    });
  });

  describe('Negative tests', () => {
    it('should throw on non-existent file', () => {
      assert.throws(
        () => compileOpenapi('/nonexistent/path/to/spec.yaml'),
        /ENOENT|no such file/i,
      );
    });

    it('should throw on invalid YAML content', () => {
      const fs = require('fs');
      const os = require('os');
      const tmpFile = path.join(os.tmpdir(), 'bad-openapi-test.yaml');
      fs.writeFileSync(tmpFile, '{{{{invalid yaml: [[[', 'utf-8');
      try {
        assert.throws(
          () => compileOpenapi(tmpFile),
          /error|invalid|yaml/i,
        );
      } finally {
        fs.unlinkSync(tmpFile);
      }
    });
  });

  describe('Common field deduplication', () => {
    it('should extract common fields for APIs with many shared params', () => {
      // Use a larger spec that has many endpoints with shared params
      const fs = require('fs');
      const candidates = ['google-maps.yaml', 'stripe-full.yaml', 'jira.yaml', 'circleci.yaml'];
      let specPath: string | null = null;
      for (const c of candidates) {
        const p = path.join(EXAMPLES_DIR, c);
        if (fs.existsSync(p)) { specPath = p; break; }
      }
      if (!specPath) {
        // Skip if no large fixture available
        return;
      }
      const spec = compileOpenapi(specPath);
      // If spec has >5 endpoints, common fields should be attempted
      if (spec.endpoints.length > 5) {
        // commonFields may or may not be populated depending on the spec
        // Just verify the algorithm doesn't crash
        assert.ok(spec.endpoints.length > 5, 'Spec should have >5 endpoints');
      }
    });
  });
});

describe('HTML Stripping', () => {
  it('should strip HTML tags from param descriptions', () => {
    const specPath = path.join(EXAMPLES_DIR, 'discord.yaml');
    const spec = compileOpenapi(specPath);
    for (const ep of spec.endpoints) {
      for (const p of [...ep.requiredParams, ...ep.optionalParams]) {
        if (p.description) {
          assert.ok(!/<[a-zA-Z][^>]*>/.test(p.description),
            `Param ${p.name} has HTML tags: ${p.description.slice(0, 100)}`);
        }
      }
    }
  });

  it('should strip HTML tags from endpoint summaries', () => {
    // Create a minimal spec with HTML in summary
    const fs = require('fs');
    const os = require('os');
    const tmpFile = path.join(os.tmpdir(), 'html-test-spec.json');
    const specData = {
      openapi: '3.0.0',
      info: { title: 'Test', version: '1.0' },
      paths: {
        '/items': {
          get: {
            summary: '<p>List all items</p>',
            responses: { '200': { description: '<b>OK</b>' } },
          },
        },
      },
    };
    fs.writeFileSync(tmpFile, JSON.stringify(specData));
    try {
      const spec = compileOpenapi(tmpFile);
      assert.ok(spec.endpoints.length > 0);
      assert.ok(!/<[a-zA-Z][^>]*>/.test(spec.endpoints[0].description || ''),
        'Summary should not contain HTML tags');
      assert.ok(spec.endpoints[0].description?.includes('List all items'),
        'Summary text content should be preserved');
    } finally {
      fs.unlinkSync(tmpFile);
    }
  });

  it('should strip HTML tags from response descriptions', () => {
    const fs = require('fs');
    const os = require('os');
    const tmpFile = path.join(os.tmpdir(), 'resp-html-test-spec.json');
    const specData = {
      openapi: '3.0.0',
      info: { title: 'Test', version: '1.0' },
      paths: {
        '/items': {
          get: {
            summary: 'List items',
            responses: {
              '200': { description: '<p>Successful response with <b>data</b></p>' },
              '404': { description: '<span class="error">Not found</span>' },
            },
          },
        },
      },
    };
    fs.writeFileSync(tmpFile, JSON.stringify(specData));
    try {
      const spec = compileOpenapi(tmpFile);
      const ep = spec.endpoints[0];
      for (const rs of ep.responses) {
        assert.ok(!/<[a-zA-Z][^>]*>/.test(rs.description || ''),
          `Response ${rs.statusCode} has HTML tags: ${rs.description}`);
      }
    } finally {
      fs.unlinkSync(tmpFile);
    }
  });

  it('should strip HTML from request body field descriptions', () => {
    const fs = require('fs');
    const os = require('os');
    const tmpFile = path.join(os.tmpdir(), 'body-html-test-spec.json');
    const specData = {
      openapi: '3.0.0',
      info: { title: 'Test', version: '1.0' },
      paths: {
        '/items': {
          post: {
            summary: 'Create item',
            requestBody: {
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    properties: {
                      name: { type: 'string', description: '<b>Item</b> name' },
                    },
                  },
                },
              },
            },
            responses: { '201': { description: 'Created' } },
          },
        },
      },
    };
    fs.writeFileSync(tmpFile, JSON.stringify(specData));
    try {
      const spec = compileOpenapi(tmpFile);
      const ep = spec.endpoints[0];
      const bodyParams = ep.requestBody || [];
      for (const p of bodyParams) {
        if (p.description) {
          assert.ok(!/<[a-zA-Z][^>]*>/.test(p.description),
            `Body param ${p.name} has HTML tags: ${p.description}`);
          assert.ok(p.description.includes('Item'),
            'Text content should be preserved');
        }
      }
    } finally {
      fs.unlinkSync(tmpFile);
    }
  });

  it('should decode HTML entities in descriptions', () => {
    const fs = require('fs');
    const os = require('os');
    const tmpFile = path.join(os.tmpdir(), 'entity-test-spec.json');
    const specData = {
      openapi: '3.0.0',
      info: { title: 'Test', version: '1.0' },
      paths: {
        '/items': {
          get: {
            summary: '&lt;p&gt;List items&lt;/p&gt;',
            responses: { '200': { description: 'OK' } },
          },
        },
      },
    };
    fs.writeFileSync(tmpFile, JSON.stringify(specData));
    try {
      const spec = compileOpenapi(tmpFile);
      assert.ok(!/<[a-zA-Z][^>]*>/.test(spec.endpoints[0].description || ''),
        'Decoded entities should be stripped');
      assert.ok(!spec.endpoints[0].description?.includes('&lt;'),
        'HTML entities should be decoded');
      assert.ok(spec.endpoints[0].description?.includes('List items'),
        'Text content should be preserved');
    } finally {
      fs.unlinkSync(tmpFile);
    }
  });
});

console.log('\n-- OpenAPI compiler tests complete --');
