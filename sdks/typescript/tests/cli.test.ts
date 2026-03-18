import { describe, it } from 'node:test';
import * as assert from 'assert';
import { execSync } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import pkg from '../package.json';

// When compiled, __dirname = sdks/typescript/dist/tests
// CLI binary: dist/src/cli.js (one level up from dist/tests, then src/cli.js)
const CLI = path.resolve(__dirname, '..', 'src', 'cli.js');

// Petstore spec is at repo root: examples/verbose/openapi/petstore.yaml
// From dist/tests that is 4 levels up
const PETSTORE = path.resolve(__dirname, '..', '..', '..', '..', 'examples', 'verbose', 'openapi', 'petstore.yaml');

describe('CLI --version', () => {
  it('prints version with --version flag', () => {
    const output = execSync(`node ${CLI} --version`, { encoding: 'utf-8' }).trim();
    assert.strictEqual(output, `lapsh ${pkg.version}`);
  });

  it('prints version with -v flag', () => {
    const output = execSync(`node ${CLI} -v`, { encoding: 'utf-8' }).trim();
    assert.strictEqual(output, `lapsh ${pkg.version}`);
  });
});

describe('CLI compile subcommand', () => {
  it('compile outputs LAP to stdout', () => {
    const output = execSync(`node "${CLI}" compile "${PETSTORE}"`, { encoding: 'utf-8' });
    assert.ok(output.includes('@lap'), 'Output should contain @lap header');
    assert.ok(output.includes('@api'), 'Output should contain @api directive');
    assert.ok(output.includes('@endpoint'), 'Output should contain @endpoint directives');
  });

  it('compile --lean excludes descriptions', () => {
    const output = execSync(`node "${CLI}" compile "${PETSTORE}" --lean`, { encoding: 'utf-8' });
    assert.ok(output.includes('@lap'), 'Lean output should still contain @lap header');
    assert.ok(!output.includes('@desc'), 'Lean output should not contain @desc directives');
  });

  it('compile -o writes to file', () => {
    const tmpFile = path.join(os.tmpdir(), `lap-cli-test-${Date.now()}.lap`);
    try {
      execSync(`node "${CLI}" compile "${PETSTORE}" -o "${tmpFile}"`, { encoding: 'utf-8' });
      assert.ok(fs.existsSync(tmpFile), 'Output file should exist after compile -o');
      const content = fs.readFileSync(tmpFile, 'utf-8');
      assert.ok(content.length > 0, 'Output file should not be empty');
      assert.ok(content.includes('@lap'), 'Output file should contain @lap header');
    } finally {
      if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
    }
  });

  it('compile nonexistent file throws', () => {
    assert.throws(
      () => execSync(`node "${CLI}" compile "/nonexistent/path/to/spec.yaml"`, { encoding: 'utf-8', stdio: 'pipe' }),
      /Command failed/,
    );
  });
});
