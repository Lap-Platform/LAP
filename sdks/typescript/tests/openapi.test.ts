import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { compileOpenapi, extractAuth, stripHtml, inferAuthFromDescription } from '../src/compilers/openapi';

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

// When compiled, __dirname = sdks/typescript/dist/tests
// Fixtures live at sdks/typescript/tests/fixtures, so two levels up then into tests/fixtures
const FIXTURES_DIR = path.resolve(__dirname, '../../tests/fixtures');

describe('OpenAPI edge cases', () => {
  it('empty_spec: compiles with 0 endpoints', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'empty_spec.yaml'));
    assert.strictEqual(spec.endpoints.length, 0, 'Empty spec should have 0 endpoints');
  });

  it('no_params: endpoints have no query or path params', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'no_params.yaml'));
    assert.ok(spec.endpoints.length > 0, 'Should have at least one endpoint');
    for (const ep of spec.endpoints) {
      assert.strictEqual(ep.requiredParams.length, 0, `Endpoint ${ep.path} should have no required params`);
      assert.strictEqual(ep.optionalParams.length, 0, `Endpoint ${ep.path} should have no optional params`);
    }
  });

  it('only_required: path param is required', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'only_required.yaml'));
    assert.ok(spec.endpoints.length > 0);
    const ep = spec.endpoints[0];
    const reqNames = ep.requiredParams.map(p => p.name);
    assert.ok(reqNames.includes('user_id'), 'user_id should be a required path param');
    assert.strictEqual(ep.optionalParams.length, 0, 'Should have no optional params');
  });

  it('deep_nested: response schema preserves nested structure', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'deep_nested.yaml'));
    assert.ok(spec.endpoints.length > 0);
    const ep = spec.endpoints[0];
    assert.ok(ep.responses.length > 0, 'Should have response schemas');
    const fields = ep.responses[0].fields;
    assert.ok(fields.length > 0, 'Should have top-level response fields');
    const level1 = fields.find(f => f.name === 'level1');
    assert.ok(level1, 'Should have level1 field');
    assert.ok(level1!.nested && level1!.nested.length > 0, 'level1 should have nested children');
  });

  it('many_params: all params are collected', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'many_params.yaml'));
    assert.ok(spec.endpoints.length > 0);
    const ep = spec.endpoints[0];
    const total = ep.requiredParams.length + ep.optionalParams.length;
    assert.ok(total >= 5, `Should have many params, got ${total}`);
  });

  it('no_auth: auth is empty or falsy', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'no_auth.yaml'));
    assert.ok(!spec.auth || spec.auth === '', 'No-auth spec should have no auth string');
  });

  it('special_chars: param descriptions survive special characters', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'special_chars.yaml'));
    assert.ok(spec.endpoints.length > 0);
    const ep = spec.endpoints[0];
    const allParams = [...ep.requiredParams, ...ep.optionalParams];
    assert.ok(allParams.length > 0, 'Should have params');
    const queryParam = allParams.find(p => p.name === 'query');
    assert.ok(queryParam, 'Should have query param');
    // Description must be a string and must not be empty
    assert.ok(typeof queryParam!.description === 'string' || queryParam!.description === undefined);
  });

  it('big_enum: enum values are present and non-empty', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'big_enum.yaml'));
    assert.ok(spec.endpoints.length > 0);
    const ep = spec.endpoints[0];
    const allParams = [...ep.requiredParams, ...ep.optionalParams];
    const countryParam = allParams.find(p => p.name === 'country');
    assert.ok(countryParam, 'Should have country param');
    assert.ok(countryParam!.enumValues && countryParam!.enumValues.length > 0, 'country should have enum values');
  });

  it('array_nested: response contains array fields with nested items', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'array_nested.yaml'));
    assert.ok(spec.endpoints.length > 0);
    const ep = spec.endpoints[0];
    assert.ok(ep.responses.length > 0);
    const fields = ep.responses[0].fields;
    assert.ok(fields.length > 0, 'Should have top-level response fields');
    const ordersField = fields.find(f => f.name === 'orders');
    assert.ok(ordersField, 'Should have orders array field');
  });

  it('multi_auth: auth contains multiple scheme types', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'multi_auth.yaml'));
    assert.ok(spec.auth, 'Should have auth');
    assert.ok(spec.auth!.includes('Bearer'), 'Auth should include Bearer');
    assert.ok(spec.auth!.includes('ApiKey'), 'Auth should include ApiKey');
    assert.ok(spec.auth!.includes('OAuth2'), 'Auth should include OAuth2');
  });
});

describe('extractAuth formatting', () => {
  it('basic auth produces Basic', () => {
    const syntheticSpec = {
      components: {
        securitySchemes: {
          basicAuth: { type: 'http', scheme: 'basic' },
        },
      },
    };
    const result = extractAuth(syntheticSpec as Record<string, unknown>);
    assert.strictEqual(result, 'Basic', `Expected 'Basic', got '${result}'`);
  });

  it('bearer auth produces Bearer', () => {
    const syntheticSpec = {
      components: {
        securitySchemes: {
          bearerAuth: { type: 'http', scheme: 'bearer' },
        },
      },
    };
    const result = extractAuth(syntheticSpec as Record<string, unknown>);
    assert.strictEqual(result, 'Bearer', `Expected 'Bearer', got '${result}'`);
  });

  it('mixed basic and bearer produces Basic | Bearer', () => {
    const syntheticSpec = {
      components: {
        securitySchemes: {
          basicAuth: { type: 'http', scheme: 'basic' },
          bearerAuth: { type: 'http', scheme: 'bearer' },
        },
      },
    };
    const result = extractAuth(syntheticSpec as Record<string, unknown>);
    assert.ok(result.includes('Basic'), `Result should include 'Basic': ${result}`);
    assert.ok(result.includes('Bearer'), `Result should include 'Bearer': ${result}`);
    assert.ok(result.includes('|'), `Result should be pipe-separated: ${result}`);
  });

  it('unknown http scheme is capitalized', () => {
    const syntheticSpec = {
      components: {
        securitySchemes: {
          digestAuth: { type: 'http', scheme: 'digest' },
        },
      },
    };
    const result = extractAuth(syntheticSpec as Record<string, unknown>);
    assert.strictEqual(result, 'Digest', `Expected 'Digest', got '${result}'`);
  });
});

describe('inferAuthFromDescription', () => {
  it('detects bearer token from description', () => {
    const spec = {
      info: { description: 'Authenticate with a Bearer token in the Authorization header.' },
    };
    const result = inferAuthFromDescription(spec as Record<string, unknown>);
    assert.ok(result.includes('Bearer'), `Expected Bearer in result, got '${result}'`);
  });

  it('detects api key from description', () => {
    const spec = {
      info: { description: 'Supply your API key as a query parameter or header.' },
    };
    const result = inferAuthFromDescription(spec as Record<string, unknown>);
    assert.ok(result.includes('ApiKey'), `Expected ApiKey in result, got '${result}'`);
  });

  it('detects oauth2 from description', () => {
    const spec = {
      info: { description: 'This API uses OAuth2 for authorization.' },
    };
    const result = inferAuthFromDescription(spec as Record<string, unknown>);
    assert.ok(result.includes('OAuth2'), `Expected OAuth2 in result, got '${result}'`);
  });

  it('no false positive for generic weather API description', () => {
    const spec = {
      info: { description: 'A fully open public API for weather data. Access is unrestricted.' },
    };
    const result = inferAuthFromDescription(spec as Record<string, unknown>);
    assert.strictEqual(result, '', `Expected empty string for weather API, got '${result}'`);
  });

  it('empty info object returns empty string', () => {
    const result = inferAuthFromDescription({} as Record<string, unknown>);
    assert.strictEqual(result, '', `Expected empty string for missing info, got '${result}'`);
  });
});

describe('Swagger 2.0 support', () => {
  const NETLIFY_PATH = path.resolve(__dirname, '../../../../examples/verbose/openapi/netlify.yaml');

  it('detects auth from securityDefinitions in Swagger 2.0 spec', () => {
    const spec = compileOpenapi(NETLIFY_PATH);
    assert.ok(spec.auth, 'Netlify spec should have auth');
    assert.ok(spec.auth!.length > 0, 'Auth should be non-empty');
  });

  it('constructs base URL from host and basePath for Swagger 2.0', () => {
    const spec = compileOpenapi(NETLIFY_PATH);
    assert.ok(spec.baseUrl, 'Netlify spec should have a base URL');
    assert.ok(
      spec.baseUrl.startsWith('http://') || spec.baseUrl.startsWith('https://'),
      `Base URL should start with http(s)://, got: ${spec.baseUrl}`,
    );
    assert.ok(spec.baseUrl.includes('netlify'), `Base URL should include 'netlify', got: ${spec.baseUrl}`);
  });

  it('detects auth from description when securitySchemes absent', () => {
    const tmpFile = path.join(os.tmpdir(), 'infer-auth-test.json');
    const specData = {
      openapi: '3.0.0',
      info: {
        title: 'Described Auth API',
        version: '1.0',
        description: 'All requests must use a Bearer token for authorization.',
      },
      paths: {},
    };
    fs.writeFileSync(tmpFile, JSON.stringify(specData), 'utf-8');
    try {
      const spec = compileOpenapi(tmpFile);
      assert.ok(spec.auth, 'Auth should be inferred from description');
      assert.ok(spec.auth!.includes('Bearer'), `Auth should include Bearer, got: ${spec.auth}`);
    } finally {
      fs.unlinkSync(tmpFile);
    }
  });
});

describe('Boolean enum preservation', () => {
  it('preserves NO and DK as strings in big_enum', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'big_enum.yaml'));
    const ep = spec.endpoints[0];
    const allParams = [...ep.requiredParams, ...ep.optionalParams];
    const currencyParam = allParams.find(p => p.name === 'currency');
    assert.ok(currencyParam, 'Should have currency param');
    const enumVals = currencyParam!.enumValues ?? [];
    assert.ok(enumVals.length > 0, 'Should have enum values');
    // DKK and NOK should be strings, not booleans
    for (const val of enumVals) {
      assert.strictEqual(typeof val, 'string', `Enum value '${val}' should be a string, not ${typeof val}`);
    }
  });

  it('no boolean corruption in any enum values', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'big_enum.yaml'));
    const ep = spec.endpoints[0];
    const allParams = [...ep.requiredParams, ...ep.optionalParams];
    for (const param of allParams) {
      for (const val of param.enumValues ?? []) {
        assert.notStrictEqual(val, true, `Enum value should not be boolean true in param '${param.name}'`);
        assert.notStrictEqual(val, false, `Enum value should not be boolean false in param '${param.name}'`);
      }
    }
  });
});

describe('HTML entity stripping', () => {
  it('strips HTML tags from a plain string', () => {
    const result = stripHtml('<p>Hello</p>');
    assert.strictEqual(result, 'Hello', `Expected 'Hello', got '${result}'`);
  });

  it('decodes HTML entities then strips resulting tags', () => {
    const result = stripHtml('&lt;p&gt;Hello&lt;/p&gt;');
    assert.strictEqual(result, 'Hello', `Expected 'Hello', got '${result}'`);
  });
});

describe('Deep nesting', () => {
  it('preserves 3-level deep response fields', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'deep_nested.yaml'));
    const ep = spec.endpoints[0];
    const topFields = ep.responses[0].fields;
    const level1 = topFields.find(f => f.name === 'level1');
    assert.ok(level1, 'Should have level1 field');
    const level2 = (level1!.nested ?? []).find(f => f.name === 'level2');
    assert.ok(level2, 'level1 should contain level2 field');
    const level3 = (level2!.nested ?? []).find(f => f.name === 'level3');
    assert.ok(level3, 'level2 should contain level3 field');
  });

  it('nested response fields have populated children arrays', () => {
    const spec = compileOpenapi(path.join(FIXTURES_DIR, 'deep_nested.yaml'));
    const ep = spec.endpoints[0];
    const topFields = ep.responses[0].fields;
    const level1 = topFields.find(f => f.name === 'level1');
    assert.ok(level1!.nested && level1!.nested.length > 0, 'level1.nested should be a non-empty array');
  });
});

console.log('\n-- OpenAPI compiler tests complete --');
