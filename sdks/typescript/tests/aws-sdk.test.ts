import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as path from 'path';

// When compiled, __dirname = sdks/typescript/dist/tests
const FIXTURE = path.resolve(__dirname, '../../../../sdks/typescript/tests/fixtures/aws-sdk-minimal.json');

describe('AWS SDK Compiler', () => {
  describe('Format Detection', () => {
    it('should detect AWS SDK JSON format', () => {
      const { detectFormat } = require('../src/compilers/index');
      const format = detectFormat(FIXTURE);
      assert.strictEqual(format, 'aws_sdk');
    });
  });

  describe('Compilation', () => {
    it('should compile minimal AWS SDK spec', () => {
      const { compileAwsSdk } = require('../src/compilers/aws-sdk');
      const spec = compileAwsSdk(FIXTURE);

      assert.strictEqual(spec.apiName, 'AWS Test Service');
      // version comes from metadata.apiVersion or top-level version field
      assert.ok(spec.version, 'Should have a version');
      assert.ok(spec.auth?.includes('AWS SigV4'), 'Should detect AWS SigV4 auth');
      assert.strictEqual(spec.endpoints.length, 2, 'Should have 2 endpoints');
    });

    it('should extract correct HTTP methods and paths', () => {
      const { compileAwsSdk } = require('../src/compilers/aws-sdk');
      const spec = compileAwsSdk(FIXTURE);

      const getItem = spec.endpoints.find((e: any) => e.description?.includes('Retrieves'));
      assert.ok(getItem, 'Should find GetItem endpoint');
      assert.strictEqual(getItem.method, 'GET');
      assert.strictEqual(getItem.path, '/items/{ItemId}');

      const createItem = spec.endpoints.find((e: any) => e.description?.includes('Creates'));
      assert.ok(createItem, 'Should find CreateItem endpoint');
      assert.strictEqual(createItem.method, 'POST');
      assert.strictEqual(createItem.path, '/items');
    });

    it('should strip HTML tags from descriptions', () => {
      const { compileAwsSdk } = require('../src/compilers/aws-sdk');
      const spec = compileAwsSdk(FIXTURE);

      for (const ep of spec.endpoints) {
        if (ep.description) {
          assert.ok(!/<[a-zA-Z][^>]*>/.test(ep.description),
            `Endpoint has HTML tags: ${ep.description.slice(0, 100)}`);
        }
      }
    });

    it('should decode HTML entities in descriptions', () => {
      const { compileAwsSdk } = require('../src/compilers/aws-sdk');
      const spec = compileAwsSdk(FIXTURE);

      const createItem = spec.endpoints.find((e: any) => e.description?.includes('Creates'));
      assert.ok(createItem, 'Should find CreateItem');
      assert.ok(!createItem.description?.includes('&lt;'), 'Should not have &lt;');
      assert.ok(!createItem.description?.includes('&amp;'), 'Should not have &amp;');
      assert.ok(createItem.description?.includes('& special chars'), 'Should have decoded &');
    });

    it('should classify path params as required', () => {
      const { compileAwsSdk } = require('../src/compilers/aws-sdk');
      const spec = compileAwsSdk(FIXTURE);

      const getItem = spec.endpoints.find((e: any) => e.method === 'GET');
      assert.ok(getItem, 'Should find GET endpoint');
      const pathParam = getItem.requiredParams.find((p: any) => p.name === 'ItemId');
      assert.ok(pathParam, 'ItemId should be a required param');
    });

    it('should extract response fields', () => {
      const { compileAwsSdk } = require('../src/compilers/aws-sdk');
      const spec = compileAwsSdk(FIXTURE);

      const getItem = spec.endpoints.find((e: any) => e.method === 'GET');
      assert.ok(getItem, 'Should find GET endpoint');
      assert.ok(getItem.responses.length > 0, 'Should have response schemas');
    });

    it('should extract error schemas', () => {
      const { compileAwsSdk } = require('../src/compilers/aws-sdk');
      const spec = compileAwsSdk(FIXTURE);

      const getItem = spec.endpoints.find((e: any) => e.method === 'GET');
      assert.ok(getItem, 'Should find GET endpoint');
      assert.ok(getItem.errors.length >= 2, 'Should have at least 2 error schemas');

      // "Client" in shape name -> 400, otherwise 500
      const notFound = getItem.errors.find((e: any) =>
        e.type === 'ItemNotFoundException' || e.statusCode);
      assert.ok(notFound, 'Should have error schema');
    });
  });
});

console.log('\n-- AWS SDK compiler tests complete --');
