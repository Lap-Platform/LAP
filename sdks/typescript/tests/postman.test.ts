import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as path from 'path';
import { compilePostman } from '../src/compilers/postman';
import { detectFormat } from '../src/compilers/index';

// When compiled, __dirname = sdks/typescript/dist/tests
const EXAMPLES_DIR = path.resolve(__dirname, '../../../../examples/verbose/postman');

describe('Postman Compiler', () => {
  describe('Format Detection', () => {
    it('should detect Postman collection format', () => {
      const specPath = path.join(EXAMPLES_DIR, 'algolia-search.json');
      const format = detectFormat(specPath);
      assert.strictEqual(format, 'postman');
    });
  });

  describe('Algolia Search Collection', () => {
    it('should compile with correct apiName and endpoints', () => {
      const specPath = path.join(EXAMPLES_DIR, 'algolia-search.json');
      const spec = compilePostman(specPath);

      assert.ok(spec.apiName, 'Should have an API name');
      assert.ok(spec.apiName.toLowerCase().includes('algolia'), `API name should contain Algolia, got: ${spec.apiName}`);
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
      assert.strictEqual(spec.endpoints.length, 5, `Expected 5 endpoints, got ${spec.endpoints.length}`);
    });

    it('should extract auth from collection-level auth', () => {
      const specPath = path.join(EXAMPLES_DIR, 'algolia-search.json');
      const spec = compilePostman(specPath);

      assert.ok(spec.auth, 'Should have auth');
      assert.ok(spec.auth!.length > 0, 'Auth should not be empty');
    });

    it('should extract params on at least one endpoint', () => {
      const specPath = path.join(EXAMPLES_DIR, 'algolia-search.json');
      const spec = compilePostman(specPath);

      const hasParams = spec.endpoints.some(
        ep => ep.requiredParams.length > 0 || ep.optionalParams.length > 0 || (ep.requestBody && ep.requestBody.length > 0),
      );
      assert.ok(hasParams, 'At least one endpoint should have params');
    });

    it('should not have HTML tags in descriptions', () => {
      const specPath = path.join(EXAMPLES_DIR, 'algolia-search.json');
      const spec = compilePostman(specPath);

      for (const ep of spec.endpoints) {
        if (ep.description) {
          assert.ok(!/<[a-zA-Z][^>]*>/.test(ep.description),
            `Endpoint "${ep.path}" has HTML in description: ${ep.description.slice(0, 100)}`);
        }
        for (const p of [...ep.requiredParams, ...ep.optionalParams, ...(ep.requestBody || [])]) {
          if (p.description) {
            assert.ok(!/<[a-zA-Z][^>]*>/.test(p.description),
              `Param ${p.name} has HTML tags: ${p.description.slice(0, 100)}`);
          }
        }
      }
    });

    it('should extract response schemas from examples', () => {
      const specPath = path.join(EXAMPLES_DIR, 'algolia-search.json');
      const spec = compilePostman(specPath);

      const withResponses = spec.endpoints.filter(ep => ep.responses.length > 0);
      assert.ok(withResponses.length > 0, 'At least one endpoint should have response schemas');

      // The Search endpoint has a 200 response with body
      const searchEp = spec.endpoints.find(ep => ep.description?.includes('Search') || ep.path.includes('query'));
      if (searchEp) {
        assert.ok(searchEp.responses.length > 0, 'Search endpoint should have responses');
        assert.ok(searchEp.responses[0].fields.length > 0, 'Search response should have fields');
      }
    });

    it('should extract path variables as params', () => {
      const specPath = path.join(EXAMPLES_DIR, 'algolia-search.json');
      const spec = compilePostman(specPath);

      // The Get Object endpoint uses :indexName and :objectID path variables
      const getObj = spec.endpoints.find(ep => ep.description === 'Get Object');
      if (getObj) {
        const allParamNames = [
          ...getObj.requiredParams.map(p => p.name),
          ...getObj.optionalParams.map(p => p.name),
        ];
        assert.ok(
          allParamNames.includes('indexName') || allParamNames.includes('objectID'),
          `Should have path variable params, got: ${allParamNames.join(', ')}`,
        );
      }
    });

    it('should parse endpoint methods correctly', () => {
      const specPath = path.join(EXAMPLES_DIR, 'algolia-search.json');
      const spec = compilePostman(specPath);

      const methods = spec.endpoints.map(ep => ep.method.toUpperCase());
      assert.ok(methods.includes('POST'), 'Should have POST endpoints');
      assert.ok(methods.includes('GET'), 'Should have GET endpoints');
      assert.ok(methods.includes('DELETE'), 'Should have DELETE endpoints');
    });
  });

  describe('Auth-Heavy Collection', () => {
    it('should compile auth-heavy.json with auth info', () => {
      const fs = require('fs');
      const specPath = path.join(EXAMPLES_DIR, 'auth-heavy.json');
      if (!fs.existsSync(specPath)) return; // skip if fixture not available

      const spec = compilePostman(specPath);
      assert.ok(spec.apiName, 'Should have API name');
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
      assert.ok(spec.auth, 'Auth-heavy collection should have auth');
    });
  });

  describe('Negative tests', () => {
    it('should throw on non-existent file', () => {
      assert.throws(
        () => compilePostman('/nonexistent/postman-collection.json'),
        /ENOENT|no such file/i,
      );
    });
  });
});

console.log('\n-- Postman compiler tests complete --');
