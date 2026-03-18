import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as os from 'os';
import * as crypto from 'crypto';
import * as path from 'path';
import { compileGraphql } from '../src/compilers/graphql';
import { detectFormat } from '../src/compilers/index';

// When compiled, __dirname = sdks/typescript/dist/tests
const EXAMPLES_DIR = path.resolve(__dirname, '../../../../examples/verbose/graphql');

describe('GraphQL Compiler', () => {
  describe('Airbnb schema', () => {
    it('should detect graphql format from .graphql extension', () => {
      const specPath = path.join(EXAMPLES_DIR, 'airbnb.graphql');
      const format = detectFormat(specPath);
      assert.strictEqual(format, 'graphql');
    });

    it('should compile airbnb.graphql with correct metadata', () => {
      const specPath = path.join(EXAMPLES_DIR, 'airbnb.graphql');
      const spec = compileGraphql(specPath);

      assert.ok(spec.apiName, 'Should have API name');
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
    });

    it('should map Query fields to GET endpoints', () => {
      const specPath = path.join(EXAMPLES_DIR, 'airbnb.graphql');
      const spec = compileGraphql(specPath);

      // Airbnb schema has Query type with listing, search, host, etc.
      const getEndpoints = spec.endpoints.filter(e => e.method === 'GET');
      assert.ok(getEndpoints.length > 0, 'Should have GET endpoints from Query type');

      // Check specific query field
      const listing = spec.getEndpoint('GET', '/graphql/listing');
      assert.ok(listing, 'Should find GET /graphql/listing');
    });

    it('should map Mutation fields to POST endpoints', () => {
      const specPath = path.join(EXAMPLES_DIR, 'airbnb.graphql');
      const spec = compileGraphql(specPath);

      // Airbnb schema has Mutation type with createBooking, cancelBooking, etc.
      const postEndpoints = spec.endpoints.filter(e => e.method === 'POST');
      assert.ok(postEndpoints.length > 0, 'Should have POST endpoints from Mutation type');

      const createBooking = spec.getEndpoint('POST', '/graphql/createBooking');
      assert.ok(createBooking, 'Should find POST /graphql/createBooking');
    });

    it('should extract args as params', () => {
      const specPath = path.join(EXAMPLES_DIR, 'airbnb.graphql');
      const spec = compileGraphql(specPath);

      // listing(id: ID!) should have id as required param
      const listing = spec.getEndpoint('GET', '/graphql/listing')!;
      const reqNames = listing.requiredParams.map(p => p.name);
      assert.ok(reqNames.includes('id'), 'listing query should have required id param');

      // search(input: SearchInput!) should have input as required param
      const search = spec.getEndpoint('GET', '/graphql/search')!;
      const searchReqNames = search.requiredParams.map(p => p.name);
      assert.ok(searchReqNames.includes('input'), 'search query should have required input param');
    });

    it('should set baseUrl to /graphql', () => {
      const specPath = path.join(EXAMPLES_DIR, 'airbnb.graphql');
      const spec = compileGraphql(specPath);

      assert.strictEqual(spec.baseUrl, '/graphql');
    });

    it('should have no HTML in descriptions', () => {
      const specPath = path.join(EXAMPLES_DIR, 'airbnb.graphql');
      const spec = compileGraphql(specPath);

      for (const ep of spec.endpoints) {
        if (ep.description) {
          assert.ok(
            !/<[a-zA-Z][^>]*>/.test(ep.description),
            `Endpoint ${ep.method} ${ep.path} has HTML tags: ${ep.description.slice(0, 100)}`
          );
        }
      }
    });
  });

  describe('Analytics schema', () => {
    it('should compile analytics.graphql', () => {
      const specPath = path.join(EXAMPLES_DIR, 'analytics.graphql');
      const spec = compileGraphql(specPath);

      assert.ok(spec.apiName, 'Should have API name');
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
    });
  });

  describe('Negative tests', () => {
    it('should throw on non-existent file', () => {
      assert.throws(
        () => compileGraphql('/nonexistent/path/to/schema.graphql'),
        /ENOENT|no such file/i,
      );
    });

    it('should throw on non-GraphQL content', () => {
      const tmpFile = path.join(os.tmpdir(), 'bad-graphql-test.graphql');
      fs.writeFileSync(tmpFile, 'this is not graphql at all', 'utf-8');
      try {
        assert.throws(
          () => compileGraphql(tmpFile),
          /error|does not appear|graphql/i,
        );
      } finally {
        fs.unlinkSync(tmpFile);
      }
    });
  });
});

describe('GraphQL introspection JSON', () => {
  function writeTmp(data: unknown): string {
    const tmpPath = path.join(os.tmpdir(), `gql-introspection-${crypto.randomUUID()}.json`);
    fs.writeFileSync(tmpPath, JSON.stringify(data), 'utf-8');
    return tmpPath;
  }

  function makeSchema(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return {
      __schema: {
        queryType: { name: 'Query' },
        mutationType: null,
        subscriptionType: null,
        types: [
          {
            kind: 'OBJECT',
            name: 'Query',
            fields: [
              {
                name: 'hello',
                description: null,
                args: [],
                type: { kind: 'SCALAR', name: 'String', ofType: null },
              },
            ],
          },
        ],
        ...overrides,
      },
    };
  }

  it('compiles basic query from introspection', () => {
    const tmpPath = writeTmp(makeSchema());
    try {
      const spec = compileGraphql(tmpPath);
      assert.ok(spec.endpoints.length >= 1, 'Should have at least one endpoint');
      const ep = spec.getEndpoint('GET', '/graphql/hello');
      assert.ok(ep, 'Should find GET /graphql/hello');
      assert.strictEqual(ep!.method, 'GET');
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });

  it('handles data wrapper', () => {
    const bareSchema = makeSchema();
    const wrapped = { data: bareSchema };
    const tmpPath = writeTmp(wrapped);
    try {
      const spec = compileGraphql(tmpPath);
      const ep = spec.getEndpoint('GET', '/graphql/hello');
      assert.ok(ep, 'Wrapped introspection should produce same endpoint');
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });

  it('compiles mutations to POST', () => {
    const schema = makeSchema({
      mutationType: { name: 'Mutation' },
      types: [
        {
          kind: 'OBJECT',
          name: 'Query',
          fields: [
            {
              name: 'hello',
              description: null,
              args: [],
              type: { kind: 'SCALAR', name: 'String', ofType: null },
            },
          ],
        },
        {
          kind: 'OBJECT',
          name: 'Mutation',
          fields: [
            {
              name: 'createUser',
              description: null,
              args: [],
              type: { kind: 'SCALAR', name: 'String', ofType: null },
            },
          ],
        },
      ],
    });
    const tmpPath = writeTmp(schema);
    try {
      const spec = compileGraphql(tmpPath);
      const ep = spec.getEndpoint('POST', '/graphql/createUser');
      assert.ok(ep, 'Should find POST /graphql/createUser');
      assert.strictEqual(ep!.method, 'POST');
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });

  it('compiles query args to params', () => {
    const schema = makeSchema({
      types: [
        {
          kind: 'OBJECT',
          name: 'Query',
          fields: [
            {
              name: 'hello',
              description: null,
              args: [
                {
                  name: 'name',
                  description: null,
                  type: { kind: 'NON_NULL', name: null, ofType: { kind: 'SCALAR', name: 'String', ofType: null } },
                },
              ],
              type: { kind: 'SCALAR', name: 'String', ofType: null },
            },
          ],
        },
      ],
    });
    const tmpPath = writeTmp(schema);
    try {
      const spec = compileGraphql(tmpPath);
      const ep = spec.getEndpoint('GET', '/graphql/hello');
      assert.ok(ep, 'Should find GET /graphql/hello');
      const reqNames = ep!.requiredParams.map((p) => p.name);
      assert.ok(reqNames.includes('name'), 'Should have required param "name"');
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });

  it('handles subscriptions', () => {
    const schema = makeSchema({
      subscriptionType: { name: 'Subscription' },
      types: [
        {
          kind: 'OBJECT',
          name: 'Query',
          fields: [
            {
              name: 'hello',
              description: null,
              args: [],
              type: { kind: 'SCALAR', name: 'String', ofType: null },
            },
          ],
        },
        {
          kind: 'OBJECT',
          name: 'Subscription',
          fields: [
            {
              name: 'onMessage',
              description: null,
              args: [],
              type: { kind: 'SCALAR', name: 'String', ofType: null },
            },
          ],
        },
      ],
    });
    const tmpPath = writeTmp(schema);
    try {
      const spec = compileGraphql(tmpPath);
      const ep = spec.getEndpoint('GET', '/graphql/onMessage');
      assert.ok(ep, 'Should find GET /graphql/onMessage');
      assert.ok(
        ep!.description && ep!.description.includes('[SUBSCRIPTION]'),
        `description should include [SUBSCRIPTION], got: ${ep!.description}`,
      );
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });
});

describe('GraphQL introspection format detection', () => {
  it('detects bare introspection JSON', () => {
    const data = {
      __schema: {
        queryType: { name: 'Query' },
        mutationType: null,
        subscriptionType: null,
        types: [
          {
            kind: 'OBJECT',
            name: 'Query',
            fields: [
              {
                name: 'ping',
                description: null,
                args: [],
                type: { kind: 'SCALAR', name: 'String', ofType: null },
              },
            ],
          },
        ],
      },
    };
    const tmpPath = path.join(os.tmpdir(), `gql-detect-bare-${crypto.randomUUID()}.json`);
    fs.writeFileSync(tmpPath, JSON.stringify(data), 'utf-8');
    try {
      assert.doesNotThrow(() => compileGraphql(tmpPath));
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });

  it('detects data-wrapped introspection', () => {
    const data = {
      data: {
        __schema: {
          queryType: { name: 'Query' },
          mutationType: null,
          subscriptionType: null,
          types: [
            {
              kind: 'OBJECT',
              name: 'Query',
              fields: [
                {
                  name: 'ping',
                  description: null,
                  args: [],
                  type: { kind: 'SCALAR', name: 'String', ofType: null },
                },
              ],
            },
          ],
        },
      },
    };
    const tmpPath = path.join(os.tmpdir(), `gql-detect-wrapped-${crypto.randomUUID()}.json`);
    fs.writeFileSync(tmpPath, JSON.stringify(data), 'utf-8');
    try {
      assert.doesNotThrow(() => compileGraphql(tmpPath));
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });

  it('rejects non-graphql JSON', () => {
    const data = { openapi: '3.0.0', info: { title: 'Test', version: '1.0.0' } };
    const tmpPath = path.join(os.tmpdir(), `gql-reject-${crypto.randomUUID()}.json`);
    fs.writeFileSync(tmpPath, JSON.stringify(data), 'utf-8');
    try {
      assert.throws(
        () => compileGraphql(tmpPath),
        /does not appear|introspection/i,
      );
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });
});

console.log('\n-- GraphQL compiler tests complete --');
