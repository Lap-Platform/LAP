import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as path from 'path';
import { compileSmithySpec } from '../src/compilers/smithy';
import { detectFormat } from '../src/compilers/index';

// When compiled, __dirname = sdks/typescript/dist/tests
const EXAMPLES_DIR = path.resolve(__dirname, '../../../../examples/verbose/smithy');

describe('Smithy Compiler', () => {
  describe('Format Detection', () => {
    it('should detect Smithy JSON AST format', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const format = detectFormat(specPath);
      assert.strictEqual(format, 'smithy');
    });
  });

  describe('Weather Service', () => {
    it('should compile with correct apiName', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      assert.ok(spec.apiName, 'Should have API name');
      assert.ok(
        spec.apiName.toLowerCase().includes('weather'),
        `API name should contain Weather, got: ${spec.apiName}`,
      );
    });

    it('should only include HTTP-bound operations', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      // weather.json has 4 operations, all with @http trait
      assert.strictEqual(spec.endpoints.length, 4, `Expected 4 HTTP-bound endpoints, got ${spec.endpoints.length}`);
    });

    it('should extract auth scheme', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      // weather.json service has aws.auth#sigv4 trait
      assert.ok(spec.auth, 'Should have auth');
      assert.ok(spec.auth!.length > 0, 'Auth should not be empty');
    });

    it('should extract path params from URI patterns', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      // GetCity has GET /cities/{cityId} with cityId as @httpLabel
      const getCity = spec.endpoints.find(ep => ep.path.includes('/cities/'));
      assert.ok(getCity, 'Should find GetCity endpoint');
      assert.strictEqual(getCity.method, 'GET');

      const pathParam = getCity.requiredParams.find(p => p.name === 'cityId');
      assert.ok(pathParam, 'cityId should be a required path param');
    });

    it('should extract query params', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      // GetForecast has cityId (required query), days (optional query), units (optional query)
      const getForecast = spec.endpoints.find(ep => ep.path.includes('/forecast'));
      assert.ok(getForecast, 'Should find GetForecast endpoint');

      const allParams = [...getForecast.requiredParams, ...getForecast.optionalParams];
      const paramNames = allParams.map(p => p.name);
      // The compiler uses the httpQuery key name ('city') rather than the member name ('cityId')
      assert.ok(
        paramNames.includes('cityId') || paramNames.includes('city'),
        `Should have cityId or city param, got: ${paramNames.join(', ')}`,
      );
    });

    it('should extract response fields', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      const getCity = spec.endpoints.find(ep => ep.path.includes('/cities/'));
      assert.ok(getCity, 'Should find GetCity endpoint');
      assert.ok(getCity.responses.length > 0, 'Should have response schemas');

      const successResponse = getCity.responses[0];
      assert.ok(successResponse.fields.length > 0, 'Response should have fields');

      const fieldNames = successResponse.fields.map(f => f.name);
      assert.ok(fieldNames.includes('name'), `Should have name field, got: ${fieldNames.join(', ')}`);
    });

    it('should extract error schemas', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      // GetCity has NoSuchResource error (404)
      const getCity = spec.endpoints.find(ep => ep.path.includes('/cities/'));
      assert.ok(getCity, 'Should find GetCity endpoint');
      assert.ok(getCity.errors.length > 0, `Should have error schemas, got ${getCity.errors.length}`);

      // CreateReport has InvalidInput error (400)
      const createReport = spec.endpoints.find(ep => ep.path.includes('/reports'));
      assert.ok(createReport, 'Should find CreateReport endpoint');
      assert.ok(createReport.errors.length > 0, 'CreateReport should have error schemas');
    });

    it('should not have HTML tags in descriptions', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

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

    it('should extract correct HTTP methods', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      const methods = spec.endpoints.map(ep => ep.method.toUpperCase());
      assert.ok(methods.includes('GET'), 'Should have GET endpoints');
      assert.ok(methods.includes('POST'), 'Should have POST endpoints');
    });

    it('should extract request body params for POST operations', () => {
      const specPath = path.join(EXAMPLES_DIR, 'weather.json');
      const spec = compileSmithySpec(specPath);

      // CreateReport is POST with body members (cityId, temperature, conditions, reportedBy)
      const createReport = spec.endpoints.find(ep => ep.path.includes('/reports'));
      assert.ok(createReport, 'Should find CreateReport endpoint');
      assert.strictEqual(createReport.method, 'POST');

      const allParams = [
        ...createReport.requiredParams,
        ...createReport.optionalParams,
        ...(createReport.requestBody || []),
      ];
      assert.ok(allParams.length > 0, 'CreateReport should have params');
    });
  });

  describe('Negative tests', () => {
    it('should throw on non-existent file', () => {
      assert.throws(
        () => compileSmithySpec('/nonexistent/smithy-spec.json'),
        /ENOENT|no such file|could not read/i,
      );
    });
  });
});

console.log('\n-- Smithy compiler tests complete --');
