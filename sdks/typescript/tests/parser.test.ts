import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as path from 'path';
import { parse, LAPClient, toContext } from '../src/index';
import { splitTopLevel, parseParams, parseFieldList, parseReturns, parseErrors, parseTypeExpr } from '../src/parser';

// When compiled, __dirname = sdk/typescript/dist/tests, so we need to go up to lap-poc/output
const OUTPUT_DIR = path.resolve(__dirname, '../../../../output');

describe('LAP Parser', () => {
  const files = fs.readdirSync(OUTPUT_DIR).filter(f => f.endsWith('.lap'));

  it('should find .lap files', () => {
    assert.ok(files.length > 0, 'No .lap files found');
    console.log(`Found ${files.length} .lap files`);
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
  const text = fs.readFileSync(path.join(OUTPUT_DIR, 'stripe-charges.lap'), 'utf-8');
  const spec = parse(text);

  it('should parse API metadata', () => {
    assert.strictEqual(spec.apiName, 'Stripe Charges API');
    assert.strictEqual(spec.baseUrl, 'https://api.stripe.com');
    assert.strictEqual(spec.apiVersion, '2024-12-18');
    assert.strictEqual(spec.auth, 'Bearer');
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
    assert.strictEqual(resp.statusCode, '200');
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
    assert.strictEqual(ep.errors[0].statusCode, '400');
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
  const githubFile = path.join(OUTPUT_DIR, 'github-core.lap');
  const hasFile = fs.existsSync(githubFile);

  it('should parse enums', () => {
    if (!hasFile) return; // skip when fixture not available
    const text = fs.readFileSync(githubFile, 'utf-8');
    const spec = parse(text);
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
    const spec = client.loadFile(path.join(OUTPUT_DIR, 'stripe-charges.lap'));
    assert.strictEqual(spec.apiName, 'Stripe Charges API');
    assert.ok(spec.endpoints.length > 0);
  });

  it('should generate context', () => {
    const client = new LAPClient();
    const spec = client.loadFile(path.join(OUTPUT_DIR, 'stripe-charges.lap'));
    const ctx = toContext(spec, { lean: true });
    assert.ok(ctx.includes('POST /v1/charges'));
    assert.ok(ctx.includes('amount'));
    console.log('--- Lean context (first 500 chars) ---');
    console.log(ctx.slice(0, 500));
  });
});

describe('splitTopLevel', () => {
  it('splits simple comma-separated items', () => {
    const result = splitTopLevel('a, b, c');
    assert.deepStrictEqual(result, ['a', 'b', 'c']);
  });

  it('splits field definitions', () => {
    const result = splitTopLevel('a: str, b: int, c: bool');
    assert.deepStrictEqual(result, ['a: str', 'b: int', 'c: bool']);
  });

  it('respects nested braces', () => {
    const result = splitTopLevel('a: map{x: str, y: int}, b: str');
    assert.strictEqual(result.length, 2);
    assert.ok(result[0].includes('{'), 'first item should contain braces');
    assert.strictEqual(result[1], 'b: str');
  });

  it('respects nested parens', () => {
    const result = splitTopLevel('a: str(email/url), b: int');
    assert.strictEqual(result.length, 2);
    assert.ok(result[0].includes('('), 'first item should contain parens');
    assert.strictEqual(result[1], 'b: int');
  });
});

describe('parseParams', () => {
  it('parses simple param', () => {
    const result = parseParams('name: str', true);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].name, 'name');
    assert.strictEqual(result[0].type, 'str');
    assert.strictEqual(result[0].required, true);
    assert.strictEqual(result[0].nullable, false);
  });

  it('parses param with description', () => {
    const result = parseParams('name: str # A user name', true);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].description, 'A user name');
    assert.strictEqual(result[0].type, 'str');
  });

  it('parses param with default', () => {
    const result = parseParams('limit: int=10', true);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].defaultValue, '10');
    assert.strictEqual(result[0].type, 'int');
  });

  it('parses param with enum', () => {
    const result = parseParams('status: str(active/inactive/pending)', true);
    assert.strictEqual(result.length, 1);
    assert.deepStrictEqual(result[0].enumValues, ['active', 'inactive', 'pending']);
    assert.strictEqual(result[0].format, undefined);
  });

  it('parses param with format (not enum)', () => {
    const result = parseParams('created: int(unix-timestamp)', true);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].format, 'unix-timestamp');
    assert.strictEqual(result[0].enumValues, undefined);
  });

  it('parses default + description combo', () => {
    const result = parseParams('limit: int=10 # Max results', true);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].defaultValue, '10');
    assert.strictEqual(result[0].description, 'Max results');
  });
});

describe('parseFieldList', () => {
  it('parses simple field', () => {
    const result = parseFieldList('id: str');
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].name, 'id');
    assert.strictEqual(result[0].type, 'str');
    assert.strictEqual(result[0].nullable, false);
  });

  it('parses nullable field', () => {
    const result = parseFieldList('email: str?');
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].name, 'email');
    assert.strictEqual(result[0].type, 'str');
    assert.strictEqual(result[0].nullable, true);
  });

  it('parses nested map', () => {
    const result = parseFieldList('billing: map{name: str?, email: str?}');
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].name, 'billing');
    assert.ok(result[0].nested, 'billing should have nested fields');
    assert.strictEqual(result[0].nested!.length, 2);
    assert.strictEqual(result[0].nested![0].nullable, true);
    assert.strictEqual(result[0].nested![1].nullable, true);
  });

  it('parses deep nested map', () => {
    const result = parseFieldList('outer: map{inner: map{deep: str}}');
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].name, 'outer');
    assert.ok(result[0].nested, 'outer should have nested fields');
    assert.strictEqual(result[0].nested!.length, 1);
    assert.strictEqual(result[0].nested![0].name, 'inner');
    assert.ok(result[0].nested![0].nested, 'inner should have nested fields');
    assert.strictEqual(result[0].nested![0].nested!.length, 1);
    assert.strictEqual(result[0].nested![0].nested![0].name, 'deep');
  });
});

describe('parseReturns', () => {
  it('parses with fields', () => {
    const result = parseReturns('@returns(200) {id: str, name: str?}');
    assert.strictEqual(result.statusCode, '200');
    assert.strictEqual(result.fields.length, 2);
    assert.strictEqual(result.fields[0].name, 'id');
    assert.strictEqual(result.fields[1].name, 'name');
    assert.strictEqual(result.fields[1].nullable, true);
  });

  it('parses with fields and comment', () => {
    const result = parseReturns('@returns(200) {id: str} # Success');
    assert.strictEqual(result.statusCode, '200');
    assert.strictEqual(result.fields.length, 1);
    assert.strictEqual(result.description, 'Success');
  });
});

describe('parseErrors', () => {
  it('parses with descriptions', () => {
    const result = parseErrors('@errors {400: Bad request, 401: Unauthorized}');
    assert.strictEqual(result.length, 2);
    assert.strictEqual(result[0].statusCode, '400');
    assert.strictEqual(result[0].description, 'Bad request');
    assert.strictEqual(result[1].statusCode, '401');
    assert.strictEqual(result[1].description, 'Unauthorized');
  });

  it('handles description with commas', () => {
    // splitTopLevel splits at ALL top-level commas, so "404: Not found, check the ID, 500: Server error"
    // becomes 3 items: "404: Not found", "check the ID", "500: Server error"
    const result = parseErrors('@errors {404: Not found, check the ID, 500: Server error}');
    // The 500 error is the last item
    const err500 = result.find(e => e.statusCode === '500');
    assert.ok(err500, '500 error should be present');
    assert.strictEqual(err500!.description, 'Server error');
  });
});

describe('parseTypeExpr', () => {
  it('parses plain type', () => {
    const result = parseTypeExpr('str');
    assert.strictEqual(result.type, 'str');
    assert.strictEqual(result.nullable, false);
    assert.strictEqual(result.isArray, false);
  });

  it('parses nullable type', () => {
    const result = parseTypeExpr('str?');
    assert.strictEqual(result.type, 'str');
    assert.strictEqual(result.nullable, true);
  });

  it('parses array type', () => {
    const result = parseTypeExpr('[int]');
    assert.strictEqual(result.type, 'int');
    assert.strictEqual(result.isArray, true);
  });

  it('parses enum type', () => {
    const result = parseTypeExpr('str(active/inactive)');
    assert.strictEqual(result.type, 'str');
    assert.deepStrictEqual(result.enumValues, ['active', 'inactive']);
    assert.strictEqual(result.format, undefined);
  });

  it('parses format hint (no slash)', () => {
    const result = parseTypeExpr('int(unix-timestamp)');
    assert.strictEqual(result.type, 'int');
    assert.strictEqual(result.format, 'unix-timestamp');
    assert.strictEqual(result.enumValues, undefined);
  });

  it('parses nested map type', () => {
    const result = parseTypeExpr('map{name: str, age: int}');
    assert.strictEqual(result.type, 'map');
    assert.ok(result.nested, 'map should have nested fields');
    assert.strictEqual(result.nested!.length, 2);
    assert.strictEqual(result.nested![0].name, 'name');
    assert.strictEqual(result.nested![1].name, 'age');
  });

  it('parses nullable array', () => {
    const result = parseTypeExpr('[str]?');
    assert.strictEqual(result.type, 'str');
    assert.strictEqual(result.isArray, true);
    assert.strictEqual(result.nullable, true);
  });
});
