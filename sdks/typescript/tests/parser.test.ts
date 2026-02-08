import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as path from 'path';
import { parse, LAPClient, toContext } from '../src/index';

// When compiled, __dirname = sdk/typescript/dist/tests, so we need to go up to lap-poc/output
const OUTPUT_DIR = path.resolve(__dirname, '../../../../output');

describe('DocLean Parser', () => {
  const files = fs.readdirSync(OUTPUT_DIR).filter(f => f.endsWith('.doclean'));

  it('should find .doclean files', () => {
    assert.ok(files.length > 0, 'No .doclean files found');
    console.log(`Found ${files.length} .doclean files`);
  });

  for (const file of files) {
    it(`should parse ${file}`, () => {
      const text = fs.readFileSync(path.join(OUTPUT_DIR, file), 'utf-8');
      const spec = parse(text);

      assert.ok(spec.apiName, `${file}: missing apiName`);
      assert.ok(spec.endpoints.length > 0, `${file}: no endpoints parsed`);

      for (const ep of spec.endpoints) {
        assert.ok(ep.method, `${file}: endpoint missing method`);
        assert.ok(ep.path, `${file}: endpoint missing path`);
        assert.deepStrictEqual(ep.allParams, [...ep.requiredParams, ...ep.optionalParams]);
      }

      console.log(`  ✓ ${file}: ${spec.apiName} — ${spec.endpoints.length} endpoints`);
    });
  }
});

describe('Stripe Charges - detailed', () => {
  const text = fs.readFileSync(path.join(OUTPUT_DIR, 'stripe-charges.doclean'), 'utf-8');
  const spec = parse(text);

  it('should parse API metadata', () => {
    assert.strictEqual(spec.apiName, 'Stripe Charges API');
    assert.strictEqual(spec.baseUrl, 'https://api.stripe.com');
    assert.strictEqual(spec.apiVersion, '2024-12-18');
    assert.strictEqual(spec.auth, 'Bearer bearer');
  });

  it('should find POST /v1/charges', () => {
    const ep = spec.getEndpoint('POST', '/v1/charges');
    assert.ok(ep, 'POST /v1/charges not found');
    assert.strictEqual(ep.description, 'Create a charge');
    assert.strictEqual(ep.requiredParams.length, 2);
    assert.strictEqual(ep.requiredParams[0].name, 'amount');
    assert.strictEqual(ep.requiredParams[0].type, 'int');
    assert.strictEqual(ep.requiredParams[1].name, 'currency');
  });

  it('should parse response schema with nested maps', () => {
    const ep = spec.getEndpoint('POST', '/v1/charges')!;
    assert.ok(ep.responses.length > 0);
    const resp = ep.responses[0];
    assert.strictEqual(resp.statusCode, 200);
    assert.ok(resp.fields.length > 0);

    // Check nested map fields
    const billing = resp.fields.find(f => f.name === 'billing_details');
    assert.ok(billing, 'billing_details field not found');
    assert.ok(billing.nested && billing.nested.length > 0, 'billing_details should have nested fields');

    const outcome = resp.fields.find(f => f.name === 'outcome');
    assert.ok(outcome, 'outcome field not found');
    assert.ok(outcome.nested && outcome.nested.length > 0);
  });

  it('should parse errors', () => {
    const ep = spec.getEndpoint('POST', '/v1/charges')!;
    assert.ok(ep.errors.length === 4);
    assert.strictEqual(ep.errors[0].statusCode, 400);
    assert.ok(ep.errors[0].description);
  });

  it('should parse nullable fields', () => {
    const ep = spec.getEndpoint('POST', '/v1/charges')!;
    const resp = ep.responses[0];
    const customerField = resp.fields.find(f => f.name === 'customer');
    assert.ok(customerField, 'customer field not found');
    assert.strictEqual(customerField.nullable, true);
  });
});

describe('GitHub - enum and defaults', () => {
  const text = fs.readFileSync(path.join(OUTPUT_DIR, 'github-core.doclean'), 'utf-8');
  const spec = parse(text);

  it('should parse enums', () => {
    const ep = spec.getEndpoint('GET', '/repos/{owner}/{repo}/issues')!;
    const state = ep.optionalParams.find(p => p.name === 'state');
    assert.ok(state);
    assert.deepStrictEqual(state.enumValues, ['open', 'closed', 'all']);
    assert.strictEqual(state.defaultValue, 'open');
  });
});

describe('LAPClient', () => {
  it('should load file via client', () => {
    const client = new LAPClient();
    const spec = client.loadFile(path.join(OUTPUT_DIR, 'stripe-charges.doclean'));
    assert.strictEqual(spec.apiName, 'Stripe Charges API');
    assert.ok(spec.endpoints.length > 0);
  });

  it('should generate context', () => {
    const client = new LAPClient();
    const spec = client.loadFile(path.join(OUTPUT_DIR, 'stripe-charges.doclean'));
    const ctx = toContext(spec, { lean: true });
    assert.ok(ctx.includes('POST /v1/charges'));
    assert.ok(ctx.includes('amount'));
    console.log('--- Lean context (first 500 chars) ---');
    console.log(ctx.slice(0, 500));
  });
});

console.log('\n✅ All tests passed!');
