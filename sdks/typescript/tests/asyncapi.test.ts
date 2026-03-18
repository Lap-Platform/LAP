import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { compileAsyncApi, resolveRef, extractType } from '../src/compilers/asyncapi';
import { detectFormat } from '../src/compilers/index';

// When compiled, __dirname = sdks/typescript/dist/tests
const EXAMPLES_DIR = path.resolve(__dirname, '../../../../examples/verbose/asyncapi');

describe('AsyncAPI Compiler', () => {
  describe('Ad Bidding spec', () => {
    it('should detect asyncapi format', () => {
      const specPath = path.join(EXAMPLES_DIR, 'ad-bidding.yaml');
      const format = detectFormat(specPath);
      assert.strictEqual(format, 'asyncapi');
    });

    it('should compile ad-bidding.yaml with correct metadata', () => {
      const specPath = path.join(EXAMPLES_DIR, 'ad-bidding.yaml');
      const spec = compileAsyncApi(specPath);

      assert.strictEqual(spec.apiName, 'Ad Bidding Real-time Events');
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
    });

    it('should extract server URL as baseUrl', () => {
      const specPath = path.join(EXAMPLES_DIR, 'ad-bidding.yaml');
      const spec = compileAsyncApi(specPath);

      // Server is kafka-ads:9092 with protocol kafka
      assert.ok(spec.baseUrl, 'Should have a baseUrl from servers');
      assert.ok(spec.baseUrl!.includes('kafka'), `baseUrl should contain kafka protocol, got: ${spec.baseUrl}`);
    });

    it('should map channel operations to endpoints', () => {
      const specPath = path.join(EXAMPLES_DIR, 'ad-bidding.yaml');
      const spec = compileAsyncApi(specPath);

      // bid-requests has publish -> PUB
      const bidReq = spec.getEndpoint('PUB', 'bid-requests');
      assert.ok(bidReq, 'Should find PUB bid-requests endpoint');

      // bid-responses has subscribe -> SUB
      const bidResp = spec.getEndpoint('SUB', 'bid-responses');
      assert.ok(bidResp, 'Should find SUB bid-responses endpoint');

      // impressions has subscribe -> SUB
      const impressions = spec.getEndpoint('SUB', 'impressions');
      assert.ok(impressions, 'Should find SUB impressions endpoint');

      // clicks has subscribe -> SUB
      const clicks = spec.getEndpoint('SUB', 'clicks');
      assert.ok(clicks, 'Should find SUB clicks endpoint');
    });

    it('should extract payload fields as params', () => {
      const specPath = path.join(EXAMPLES_DIR, 'ad-bidding.yaml');
      const spec = compileAsyncApi(specPath);

      const bidReq = spec.getEndpoint('PUB', 'bid-requests')!;
      const allParamNames = bidReq.allParams.map(p => p.name);
      assert.ok(allParamNames.includes('requestId'), 'Should have requestId param');
      assert.ok(allParamNames.includes('impressions'), 'Should have impressions param');

      // Required params from the schema
      const reqNames = bidReq.requiredParams.map(p => p.name);
      assert.ok(reqNames.includes('requestId'), 'requestId should be required');
    });

    it('should have no HTML in descriptions', () => {
      const specPath = path.join(EXAMPLES_DIR, 'ad-bidding.yaml');
      const spec = compileAsyncApi(specPath);

      for (const ep of spec.endpoints) {
        if (ep.description) {
          assert.ok(
            !/<[a-zA-Z][^>]*>/.test(ep.description),
            `Endpoint ${ep.method} ${ep.path} has HTML tags: ${ep.description.slice(0, 100)}`
          );
        }
        for (const p of [...ep.requiredParams, ...ep.optionalParams]) {
          if (p.description) {
            assert.ok(
              !/<[a-zA-Z][^>]*>/.test(p.description),
              `Param ${p.name} has HTML tags: ${p.description.slice(0, 100)}`
            );
          }
        }
      }
    });
  });

  describe('AWS SNS/SQS spec', () => {
    it('should compile aws-sns-sqs.yaml', () => {
      const specPath = path.join(EXAMPLES_DIR, 'aws-sns-sqs.yaml');
      const spec = compileAsyncApi(specPath);

      assert.ok(spec.apiName, 'Should have API name');
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
    });
  });

  describe('Negative tests', () => {
    it('should throw on non-existent file', () => {
      assert.throws(
        () => compileAsyncApi('/nonexistent/path/to/spec.yaml'),
        /ENOENT|no such file/i,
      );
    });

    it('should throw on invalid YAML content', () => {
      const tmpFile = path.join(os.tmpdir(), 'bad-asyncapi-test.yaml');
      fs.writeFileSync(tmpFile, '{{{{invalid yaml: [[[', 'utf-8');
      try {
        assert.throws(
          () => compileAsyncApi(tmpFile),
          /error|invalid|yaml/i,
        );
      } finally {
        fs.unlinkSync(tmpFile);
      }
    });
  });
});

describe('resolveRef', () => {
  it('resolves basic $ref', () => {
    const spec = { components: { schemas: { Foo: { type: 'object' } } } };
    const result = resolveRef(spec, '#/components/schemas/Foo');
    assert.deepStrictEqual(result, { type: 'object' });
  });

  it('resolves nested ref chain', () => {
    const spec = {
      components: {
        schemas: {
          A: { '$ref': '#/components/schemas/B' },
          B: { type: 'string' },
        },
      },
    };
    const result = resolveRef(spec, '#/components/schemas/A');
    assert.deepStrictEqual(result, { type: 'string' });
  });

  it('throws on circular ref', () => {
    const spec = {
      components: {
        schemas: {
          A: { '$ref': '#/components/schemas/B' },
          B: { '$ref': '#/components/schemas/A' },
        },
      },
    };
    assert.throws(
      () => resolveRef(spec, '#/components/schemas/A'),
      /Circular/,
    );
  });
});

describe('extractType', () => {
  it('maps string to str', () => {
    assert.strictEqual(extractType({ type: 'string' }, {}), 'str');
  });

  it('maps string with format', () => {
    assert.strictEqual(extractType({ type: 'string', format: 'date-time' }, {}), 'str(date-time)');
  });

  it('maps integer to int', () => {
    assert.strictEqual(extractType({ type: 'integer' }, {}), 'int');
  });

  it('maps array of strings', () => {
    assert.strictEqual(extractType({ type: 'array', items: { type: 'string' } }, {}), '[str]');
  });

  it('maps boolean to bool', () => {
    assert.strictEqual(extractType({ type: 'boolean' }, {}), 'bool');
  });
});

console.log('\n-- AsyncAPI compiler tests complete --');
