import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as path from 'path';
import { parse } from '../src/parser';
import { toLap, groupName } from '../src/serializer';

// When compiled, __dirname = sdks/typescript/dist/tests
const OUTPUT_DIR = path.resolve(__dirname, '../../../../output');
const STRIPE_FILE = fs.existsSync(path.join(OUTPUT_DIR, 'stripe-charges.lap'))
  ? path.join(OUTPUT_DIR, 'stripe-charges.lap')
  : path.join(OUTPUT_DIR, 'stripe-charges.lap');

describe('Serializer', () => {
  describe('Round-trip', () => {
    it('should round-trip stripe-charges with full content fidelity', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const original = parse(text);
      const serialized = toLap(original);
      const reparsed = parse(serialized);

      // Top-level metadata
      assert.strictEqual(reparsed.apiName, original.apiName);
      assert.strictEqual(reparsed.baseUrl, original.baseUrl);
      assert.strictEqual(reparsed.auth, original.auth);
      assert.strictEqual(reparsed.apiVersion, original.apiVersion);
      assert.strictEqual(reparsed.endpoints.length, original.endpoints.length);

      // Per-endpoint content fidelity
      for (let i = 0; i < original.endpoints.length; i++) {
        const origEp = original.endpoints[i];
        const parsedEp = reparsed.endpoints[i];

        assert.strictEqual(parsedEp.method, origEp.method, `Endpoint ${i} method mismatch`);
        assert.strictEqual(parsedEp.path, origEp.path, `Endpoint ${i} path mismatch`);
        assert.strictEqual(parsedEp.description, origEp.description, `Endpoint ${i} description mismatch`);

        // Compare required param names and types
        assert.deepStrictEqual(
          parsedEp.requiredParams.map(p => p.name),
          origEp.requiredParams.map(p => p.name),
          `Endpoint ${i} required param names mismatch`,
        );
        assert.deepStrictEqual(
          parsedEp.requiredParams.map(p => p.type),
          origEp.requiredParams.map(p => p.type),
          `Endpoint ${i} required param types mismatch`,
        );

        // Compare optional param names and types
        assert.deepStrictEqual(
          parsedEp.optionalParams.map(p => p.name),
          origEp.optionalParams.map(p => p.name),
          `Endpoint ${i} optional param names mismatch`,
        );
        assert.deepStrictEqual(
          parsedEp.optionalParams.map(p => p.type),
          origEp.optionalParams.map(p => p.type),
          `Endpoint ${i} optional param types mismatch`,
        );

        // Compare required flags
        for (const origP of origEp.requiredParams) {
          const parsedP = parsedEp.requiredParams.find(p => p.name === origP.name);
          assert.ok(parsedP, `Endpoint ${i}: required param ${origP.name} missing after round-trip`);
          assert.strictEqual(parsedP.required, true, `Endpoint ${i}: param ${origP.name} should be required`);
        }

        // Compare response status codes and descriptions
        assert.deepStrictEqual(
          parsedEp.responses.map(r => r.statusCode),
          origEp.responses.map(r => r.statusCode),
          `Endpoint ${i} response status codes mismatch`,
        );

        // Compare error status codes
        assert.deepStrictEqual(
          parsedEp.errors.map(e => e.statusCode),
          origEp.errors.map(e => e.statusCode),
          `Endpoint ${i} error status codes mismatch`,
        );
      }
    });
  });

  describe('Lean mode', () => {
    it('should produce strictly shorter output in lean mode', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const full = toLap(spec);
      const lean = toLap(spec, { lean: true });

      assert.ok(lean.length < full.length, `Lean output (${lean.length}) should be shorter than full output (${full.length})`);
    });

    it('should not contain @desc in lean mode', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const lean = toLap(spec, { lean: true });

      assert.ok(!lean.includes('@desc '), 'Lean mode should omit @desc lines');
    });

    it('should still contain all endpoints in lean mode', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const lean = toLap(spec, { lean: true });
      const reparsed = parse(lean);

      assert.strictEqual(reparsed.endpoints.length, spec.endpoints.length,
        'Lean mode should preserve all endpoints');
    });
  });

  describe('Empty spec', () => {
    it('should serialize a spec with 0 endpoints to valid LAP output', () => {
      const spec = parse('@lap v0.3\n@api EmptyAPI\n@base https://empty.example.com\n@endpoints 0\n@end');
      const result = toLap(spec);

      assert.ok(result.includes('@lap v0.3'), 'Should contain LAP version');
      assert.ok(result.includes('@api EmptyAPI'), 'Should contain API name');
      assert.ok(result.includes('@base https://empty.example.com'), 'Should contain base URL');
      assert.ok(result.includes('@endpoints 0'), 'Should show 0 endpoints');
      assert.ok(result.includes('@end'), 'Should contain @end marker');

      // Round-trip the empty spec
      const reparsed = parse(result);
      assert.strictEqual(reparsed.apiName, 'EmptyAPI');
      assert.strictEqual(reparsed.baseUrl, 'https://empty.example.com');
      assert.strictEqual(reparsed.endpoints.length, 0);
    });
  });

  describe('Edge cases', () => {
    it('should serialize a single-endpoint spec', () => {
      const spec = parse(
        '@lap v0.3\n@api TestAPI\n@base https://api.test.com\n@endpoints 1\n@endpoint GET /test\n@returns(200) OK\n@end',
      );
      const result = toLap(spec);
      assert.ok(result.includes('@api TestAPI'));
      assert.ok(result.includes('@base https://api.test.com'));
      assert.ok(result.includes('@endpoint GET /test'));
    });

    it('should handle spec with no auth', () => {
      const spec = parse(
        '@lap v0.3\n@api NoAuthAPI\n@base https://api.test.com\n@endpoints 1\n@endpoint GET /test\n@end',
      );
      const result = toLap(spec);
      assert.ok(!result.includes('@auth'));
    });

    it('should handle spec with no base URL', () => {
      const spec = parse('@lap v0.3\n@api NoBurlAPI\n@endpoints 1\n@endpoint GET /test\n@end');
      const result = toLap(spec);
      assert.ok(!result.includes('@base'));
    });

    it('should not emit @group for single-group specs', () => {
      const spec = parse(
        '@lap v0.3\n@api Test\n@endpoints 2\n@endpoint GET /users\n@endpoint POST /users\n@end',
      );
      const result = toLap(spec);
      assert.ok(!result.includes('@group'), 'Single group should not emit @group markers');
    });

    it('should emit @group for multi-group specs', () => {
      const spec = parse(
        '@lap v0.3\n@api Test\n@endpoints 2\n@endpoint GET /users\n@endpoint GET /posts\n@end',
      );
      const result = toLap(spec);
      assert.ok(result.includes('@group users'), 'Multi-group should emit @group users');
      assert.ok(result.includes('@group posts'), 'Multi-group should emit @group posts');
    });
  });

  describe('groupName', () => {
    it('should skip version prefix and return first meaningful segment', () => {
      assert.strictEqual(groupName('/v1/users'), 'users');
    });

    it('should return first segment when no version prefix', () => {
      assert.strictEqual(groupName('/users'), 'users');
    });

    it('should return "root" for bare slash', () => {
      assert.strictEqual(groupName('/'), 'root');
    });

    it('should skip path params and return first non-version segment', () => {
      assert.strictEqual(groupName('/{id}/things'), '{id}');
    });

    it('should handle multi-version prefix', () => {
      assert.strictEqual(groupName('/v2/accounts/settings'), 'accounts');
    });

    it('should return the version itself when nothing follows it', () => {
      assert.strictEqual(groupName('/v1'), 'v1');
    });

    it('should handle empty string', () => {
      assert.strictEqual(groupName(''), 'root');
    });
  });
});

console.log('\n-- Serializer tests complete --');
