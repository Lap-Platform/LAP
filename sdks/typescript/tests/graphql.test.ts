import { describe, it } from 'node:test';
import * as assert from 'node:assert';
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
      const fs = require('fs');
      const os = require('os');
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

console.log('\n-- GraphQL compiler tests complete --');
