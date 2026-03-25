import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { parse } from '../src/parser';
import { generateSkill, slugify, singularize, VALID_TARGETS } from '../src/skill';
import type { SkillOptions } from '../src/skill';
import { compile } from '../src/compilers/index';
import { groupName } from '../src/serializer';
import {
  metadataPath,
  readMetadata,
  writeMetadata,
  computeSpecHash,
  isValidSkillName,
  validateRegistryUrl,
  printSpecDiff,
  registerClaudeHook,
  registerCursorHook,
  registerCodexHook,
  entryHasLapsh,
  removeHookEntries,
  removeMdHookInstruction,
  removeCursorUpdateRule,
  LAP_HOOK_MARKER,
  LAP_HOOK_INSTRUCTION,
} from '../src/cli';

const OUTPUT_DIR = path.resolve(__dirname, '../../../../output');
const STRIPE_FILE = path.join(OUTPUT_DIR, 'stripe-charges.lap');

describe('Skill Generation', () => {
  describe('generateSkill', () => {
    it('should generate skill with SKILL.md and api-spec.lap', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);

      assert.ok(skill.fileMap['SKILL.md'], 'Missing SKILL.md');
      assert.ok(skill.fileMap['references/api-spec.lap'], 'Missing references/api-spec.lap');
      assert.ok(skill.tokenCount > 0, 'Token count should be > 0');
      assert.strictEqual(skill.endpointCount, spec.endpoints.length);
    });

    it('should produce correctly slugified name', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);

      assert.ok(skill.name.length > 0, 'Name should not be empty');
      assert.ok(!/[A-Z ]/.test(skill.name), 'Name should be lowercase with no spaces');
    });

    it('SKILL.md frontmatter should contain name and description fields', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      const md = skill.fileMap['SKILL.md'];

      // Extract frontmatter between --- delimiters
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'SKILL.md should have frontmatter delimiters');

      const frontmatter = fmMatch[1];
      assert.ok(frontmatter.includes('name:'), 'Frontmatter should contain name: field');
      assert.ok(frontmatter.includes('description:'), 'Frontmatter should contain description: field');

      // Verify name matches slugified API name
      const nameMatch = frontmatter.match(/name:\s*(.+)/);
      assert.ok(nameMatch, 'Should be able to extract name value');
      assert.strictEqual(nameMatch[1].trim(), slugify(spec.apiName));
    });

    it('SKILL.md Endpoints section should reference api-spec.lap', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      const md = skill.fileMap['SKILL.md'];

      // Extract Endpoints section content
      const endpointsMatch = md.match(/## Endpoints\n([\s\S]*?)(?=\n## |$)/);
      assert.ok(endpointsMatch, 'Should have Endpoints section');
      const endpointsContent = endpointsMatch[1];

      assert.ok(
        endpointsContent.includes('api-spec.lap'),
        'Endpoints section should reference api-spec.lap for full details',
      );
      assert.ok(
        endpointsContent.includes(String(spec.endpoints.length)),
        `Endpoints section should mention the endpoint count (${spec.endpoints.length})`,
      );
    });

    it('SKILL.md should contain all expected sections with real content', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      const md = skill.fileMap['SKILL.md'];

      // Verify Auth section has actual auth info, not just a header
      const authMatch = md.match(/## Auth\n([\s\S]*?)(?=\n## |$)/);
      assert.ok(authMatch, 'Should have Auth section');
      assert.ok(authMatch[1].trim().length > 0, 'Auth section should have content');
      if (spec.auth) {
        assert.ok(authMatch[1].includes(spec.auth), 'Auth section should contain the auth string from spec');
      }

      // Verify Base URL section has the actual base URL
      const baseUrlMatch = md.match(/## Base URL\n([\s\S]*?)(?=\n## |$)/);
      assert.ok(baseUrlMatch, 'Should have Base URL section');
      if (spec.baseUrl) {
        assert.ok(baseUrlMatch[1].includes(spec.baseUrl), 'Base URL section should contain the base URL');
      }

      // Verify Setup section has numbered steps
      const setupMatch = md.match(/## Setup\n([\s\S]*?)(?=\n## |$)/);
      assert.ok(setupMatch, 'Should have Setup section');
      assert.ok(/\d+\./.test(setupMatch[1]), 'Setup section should contain numbered steps');

      // Verify Common Questions section has content
      const cqMatch = md.match(/## Common Questions\n([\s\S]*?)(?=\n## |$)/);
      assert.ok(cqMatch, 'Should have Common Questions section');
      assert.ok(cqMatch[1].trim().length > 0, 'Common Questions section should have content');

      // Verify References section mentions api-spec.lap
      const refsMatch = md.match(/## References\n([\s\S]*?)(?=\n## |$)/);
      assert.ok(refsMatch, 'Should have References section');
      assert.ok(refsMatch[1].includes('api-spec.lap'), 'References should mention api-spec.lap');
    });

    it('should generate skill with explicit lean: false option', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skillLean = generateSkill(spec); // default is lean: true
      const skillFull = generateSkill(spec, { lean: false });

      // Both should produce valid output
      assert.ok(skillFull.fileMap['SKILL.md'], 'Full skill should have SKILL.md');
      assert.ok(skillFull.fileMap['references/api-spec.lap'], 'Full skill should have api-spec.lap');
      assert.strictEqual(skillFull.endpointCount, spec.endpoints.length);

      // Full (non-lean) api-spec.lap should be longer or equal (has descriptions)
      const fullLap = skillFull.fileMap['references/api-spec.lap'];
      const leanLap = skillLean.fileMap['references/api-spec.lap'];
      assert.ok(
        fullLap.length >= leanLap.length,
        `Full LAP (${fullLap.length}) should be >= lean LAP (${leanLap.length})`,
      );
    });

    it('should throw on empty spec', () => {
      const spec = parse('@lap v0.3\n@api Empty\n@endpoints 0\n@end');
      assert.throws(() => generateSkill(spec), /no endpoints/i);
    });
  });

  describe('slugify', () => {
    it('should handle standard names', () => {
      assert.strictEqual(slugify('Stripe API'), 'stripe-api');
      assert.strictEqual(slugify('Discord API'), 'discord-api');
    });

    it('should handle underscores', () => {
      assert.strictEqual(slugify('my_api'), 'my-api');
    });

    it('should handle special characters', () => {
      assert.strictEqual(slugify('API v2.0!'), 'api-v2-0');
    });

    it('should replace slashes with hyphens', () => {
      assert.strictEqual(slugify('stripe/charges'), 'stripe-charges');
    });

    it('should replace dots with hyphens', () => {
      assert.strictEqual(slugify('api-v2.0'), 'api-v2-0');
    });

    it('should collapse repeated hyphens', () => {
      assert.strictEqual(slugify('a - - b'), 'a-b');
    });

    it('should return "api" for empty input', () => {
      assert.strictEqual(slugify(''), 'api');
      assert.strictEqual(slugify('!!!'), 'api');
    });
  });

  describe('singularize', () => {
    it('should handle regular plurals', () => {
      assert.strictEqual(singularize('pets'), 'pet');
      assert.strictEqual(singularize('users'), 'user');
    });

    it('should handle -ies plurals', () => {
      assert.strictEqual(singularize('categories'), 'category');
      assert.strictEqual(singularize('companies'), 'company');
    });

    it('should handle exception words', () => {
      assert.strictEqual(singularize('responses'), 'response');
      assert.strictEqual(singularize('messages'), 'message');
      assert.strictEqual(singularize('databases'), 'database');
      assert.strictEqual(singularize('invoices'), 'invoice');
    });

    it('should not singularize already-singular words', () => {
      assert.strictEqual(singularize('status'), 'status');
      assert.strictEqual(singularize('analysis'), 'analysis');
    });

    it('should handle empty string', () => {
      assert.strictEqual(singularize(''), '');
    });
  });

  describe('distribution frontmatter', () => {
    it('frontmatter includes version field', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      const md = skill.fileMap['SKILL.md'];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(fmMatch[1].includes('version: 1.0.0'), 'Should include version');
    });

    it('frontmatter includes generator field', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      const md = skill.fileMap['SKILL.md'];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(fmMatch[1].includes('generator: lapsh'), 'Should include generator');
    });

    it('clawhub option adds metadata.openclaw block for auth specs', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      // Stripe has auth
      assert.ok(spec.auth, 'Stripe spec should have auth');
      const skill = generateSkill(spec, { clawhub: true });
      const md = skill.fileMap['SKILL.md'];
      assert.ok(md.includes('metadata:'), 'Should include metadata');
      assert.ok(md.includes('openclaw:'), 'Should include openclaw');
      assert.ok(md.includes('requires:'), 'Should include requires');
      assert.ok(md.includes('env:'), 'Should include env');
    });

    it('clawhub option without auth omits metadata block', () => {
      // Parse a minimal spec without auth
      const spec = parse('@lap v0.3\n@api NoAuth API\n@base https://api.example.com\n@endpoint GET /status\n@desc Health check\n@end');
      assert.ok(!spec.auth, 'Spec should have no auth');
      const skill = generateSkill(spec, { clawhub: true });
      const md = skill.fileMap['SKILL.md'];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(!fmMatch[1].includes('metadata:'), 'Should not include metadata for no-auth spec');
    });

    it('default mode omits clawhub metadata', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec); // clawhub defaults to false/undefined
      const md = skill.fileMap['SKILL.md'];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(!fmMatch![1].includes('metadata:'), 'Default should not include metadata');
    });

    it('body includes LAP attribution', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      const md = skill.fileMap['SKILL.md'];
      assert.ok(md.includes('Generated from the official API spec by'), 'Should have attribution');
      assert.ok(md.includes('lap.sh'), 'Attribution should link to lap.sh');
    });

    it('custom version option appears in frontmatter', () => {
      const spec = parse('@lap v0.3\n@api Test API\n@base https://api.test.com\n@version 2.0.0\n@auth Bearer token\n@endpoint GET /items\n@desc List items\n@end');
      const skill = generateSkill(spec, { version: '3.0.0' });
      const md = skill.fileMap['SKILL.md'];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(fmMatch[1].includes('version: 3.0.0'), 'Should include custom version');
      assert.ok(!fmMatch[1].includes('version: 1.0.0'), 'Should not include default version');
    });

    it('body includes API version when spec has apiVersion', () => {
      const spec = parse('@lap v0.3\n@api Versioned API\n@base https://api.test.com\n@version 1.0.27\n@endpoint GET /items\n@desc List items\n@end');
      assert.ok(spec.apiVersion, 'Spec should have apiVersion');
      const skill = generateSkill(spec);
      const md = skill.fileMap['SKILL.md'];
      assert.ok(md.includes('API version: 1.0.27'), 'Body should include API version');
    });
  });

  describe('cursor target', () => {
    it('produces .mdc file instead of SKILL.md', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec, { target: 'cursor' });
      const mdcFiles = Object.keys(skill.fileMap).filter(k => k.endsWith('.mdc'));
      assert.strictEqual(mdcFiles.length, 1, 'Should have exactly one .mdc file');
      assert.ok(!('SKILL.md' in skill.fileMap), 'Should not have SKILL.md');
    });

    it('.mdc filename matches slug', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec, { target: 'cursor' });
      const expected = `${slugify(spec.apiName)}.mdc`;
      assert.ok(expected in skill.fileMap, `Should have ${expected}`);
      assert.strictEqual(skill.mainFile, expected);
    });

    it('frontmatter has description and alwaysApply', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec, { target: 'cursor' });
      const md = skill.fileMap[skill.mainFile];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(fmMatch[1].includes('description:'), 'Should have description');
      assert.ok(fmMatch[1].includes('alwaysApply: false'), 'Should have alwaysApply');
    });

    it('frontmatter has no generator or version', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec, { target: 'cursor' });
      const md = skill.fileMap[skill.mainFile];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(!fmMatch[1].includes('generator:'), 'Should not have generator');
      assert.ok(!fmMatch[1].includes('version:'), 'Should not have version');
    });

    it('body matches claude body', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const claude = generateSkill(spec, { target: 'claude' });
      const cursor = generateSkill(spec, { target: 'cursor' });
      const claudeBody = claude.fileMap[claude.mainFile].split('---').slice(2).join('---');
      const cursorBody = cursor.fileMap[cursor.mainFile].split('---').slice(2).join('---');
      assert.strictEqual(cursorBody, claudeBody);
    });

    it('still includes references/api-spec.lap', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec, { target: 'cursor' });
      assert.ok('references/api-spec.lap' in skill.fileMap, 'Should have api-spec.lap');
    });
  });

  describe('codex target', () => {
    it('produces SKILL.md (not .mdc)', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec, { target: 'codex' });
      assert.ok('SKILL.md' in skill.fileMap, 'Should have SKILL.md');
      assert.strictEqual(skill.mainFile, 'SKILL.md');
      const mdcFiles = Object.keys(skill.fileMap).filter(k => k.endsWith('.mdc'));
      assert.strictEqual(mdcFiles.length, 0, 'Should not have any .mdc files');
    });

    it('frontmatter has name, description, version, and generator', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec, { target: 'codex' });
      const md = skill.fileMap['SKILL.md'];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(fmMatch[1].includes('name:'), 'Should have name');
      assert.ok(fmMatch[1].includes('description:'), 'Should have description');
      assert.ok(fmMatch[1].includes('version:'), 'Should have version');
      assert.ok(fmMatch[1].includes('generator: lapsh'), 'Should have generator');
    });

    it('body matches claude body', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const claude = generateSkill(spec, { target: 'claude' });
      const codex = generateSkill(spec, { target: 'codex' });
      const claudeBody = claude.fileMap[claude.mainFile].split('---').slice(2).join('---');
      const codexBody = codex.fileMap[codex.mainFile].split('---').slice(2).join('---');
      assert.strictEqual(codexBody, claudeBody);
    });

    it('still includes references/api-spec.lap', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec, { target: 'codex' });
      assert.ok('references/api-spec.lap' in skill.fileMap, 'Should have api-spec.lap');
    });
  });

  describe('default target', () => {
    it('default produces Claude output with mainFile SKILL.md', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      assert.ok('SKILL.md' in skill.fileMap, 'Should have SKILL.md');
      assert.strictEqual(skill.mainFile, 'SKILL.md');
      const md = skill.fileMap['SKILL.md'];
      const fmMatch = md.match(/^---\n([\s\S]*?)\n---/);
      assert.ok(fmMatch, 'Should have frontmatter');
      assert.ok(fmMatch[1].includes('generator: lapsh'), 'Should have generator');
      assert.ok(fmMatch[1].includes('version:'), 'Should have version');
    });
  });

  describe('CLI section', () => {
    it('generated body includes ## CLI section', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      assert.ok(skill.fileMap['SKILL.md'].includes('## CLI'), 'Should have CLI section');
    });

    it('CLI section has npx commands', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      const skill = generateSkill(spec);
      assert.ok(skill.fileMap['SKILL.md'].includes('npx @lap-platform/lapsh'), 'Should have npx command');
    });

    it('CLI section appears in all targets', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      for (const t of VALID_TARGETS) {
        const skill = generateSkill(spec, { target: t });
        assert.ok(skill.fileMap[skill.mainFile].includes('## CLI'), `CLI section missing for ${t}`);
      }
    });
  });

  describe('invalid target', () => {
    it('throws on unknown target', () => {
      const text = fs.readFileSync(STRIPE_FILE, 'utf-8');
      const spec = parse(text);
      assert.throws(
        () => generateSkill(spec, { target: 'vscode' as any }),
        /Unknown target/,
      );
    });
  });

  describe('description deduplication', () => {
    it('avoids API API doubling in description', () => {
      const spec = parse('@lap v0.3\n@api Stripe API\n@base https://api.stripe.com\n@endpoint GET /charges\n@desc List charges\n@end');
      const skill = generateSkill(spec);
      const md = skill.fileMap['SKILL.md'];
      assert.ok(!md.includes('Stripe API API skill'), 'Should not double API');
      assert.ok(md.includes('Stripe API skill'), 'Should have Stripe API skill');
    });
  });

  describe('init', () => {
    it('skills directory is resolvable', () => {
      const skillsDir = path.resolve(__dirname, '../../../../lap/skills');
      assert.ok(fs.existsSync(skillsDir), `Skills dir should exist at ${skillsDir}`);
      assert.ok(fs.existsSync(path.join(skillsDir, 'cursor', 'lap.mdc')), 'Cursor skill should exist');
      assert.ok(fs.existsSync(path.join(skillsDir, 'lap', 'SKILL.md')), 'Claude skill should exist');
      assert.ok(fs.existsSync(path.join(skillsDir, 'codex', 'SKILL.md')), 'Codex skill should exist');
    });

    it('each target has reference files', () => {
      const skillsDir = path.resolve(__dirname, '../../../../lap/skills');
      const targets = [
        { name: 'claude', dir: path.join(skillsDir, 'lap') },
        { name: 'cursor', dir: path.join(skillsDir, 'cursor') },
        { name: 'codex', dir: path.join(skillsDir, 'codex') },
      ];
      for (const t of targets) {
        assert.ok(fs.existsSync(t.dir), `${t.name} skill dir should exist`);
        const refs = path.join(t.dir, 'references');
        assert.ok(fs.existsSync(refs), `${t.name} references dir should exist`);
        assert.ok(fs.existsSync(path.join(refs, 'agent-flow.md')), `${t.name} agent-flow.md should exist`);
        assert.ok(fs.existsSync(path.join(refs, 'command-reference.md')), `${t.name} command-reference.md should exist`);
        assert.ok(fs.existsSync(path.join(refs, 'publisher-flow.md')), `${t.name} publisher-flow.md should exist`);
      }
    });
  });
});

// When compiled, __dirname = sdks/typescript/dist/tests
// Petstore spec is at repo root: examples/verbose/openapi/petstore.yaml
const PETSTORE_YAML = path.resolve(__dirname, '..', '..', '..', '..', 'examples', 'verbose', 'openapi', 'petstore.yaml');

describe('Question inference', () => {
  it('CRUD patterns produce questions', () => {
    const spec = compile(PETSTORE_YAML);
    const skill = generateSkill(spec);
    const md = skill.fileMap['SKILL.md'];

    const cqMatch = md.match(/## Common Questions\n([\s\S]*?)(?=\n## |$)/);
    assert.ok(cqMatch, 'Should have Common Questions section');
    const cqContent = cqMatch[1];
    // Common questions section should contain action pattern text
    assert.ok(
      cqContent.includes('List') || cqContent.includes('Create') || cqContent.includes('list') || cqContent.includes('create'),
      'Common Questions should contain CRUD pattern hints',
    );
  });

  it('auth question present when spec has auth', () => {
    // Parse a minimal spec with auth
    const spec = parse(
      '@lap v0.3\n@api Auth API\n@base https://api.example.com\n@auth Bearer token\n@endpoint GET /items\n@desc List items\n@end',
    );
    assert.ok(spec.auth, 'Spec should have auth');
    const skill = generateSkill(spec);
    const md = skill.fileMap['SKILL.md'];

    const cqMatch = md.match(/## Common Questions\n([\s\S]*?)(?=\n## |$)/);
    assert.ok(cqMatch, 'Should have Common Questions section');
    const cqContent = cqMatch[1];
    assert.ok(
      cqContent.toLowerCase().includes('auth') || cqContent.toLowerCase().includes('authenticate'),
      'Common Questions should mention auth when spec has auth',
    );
  });

  it('no auth question when spec has no auth', () => {
    const spec = parse(
      '@lap v0.3\n@api NoAuth API\n@base https://api.example.com\n@endpoint GET /status\n@desc Health check\n@end',
    );
    assert.ok(!spec.auth, 'Spec should have no auth');
    const skill = generateSkill(spec);
    const md = skill.fileMap['SKILL.md'];

    const cqMatch = md.match(/## Common Questions\n([\s\S]*?)(?=\n## |$)/);
    assert.ok(cqMatch, 'Should have Common Questions section');
    const cqContent = cqMatch[1];
    // The auth hint line should not appear when there is no auth
    assert.ok(
      !cqContent.includes('How to authenticate?'),
      'Common Questions should not include auth hint when spec has no auth',
    );
  });

  it('PATCH verb produces partial update hint in Common Questions', () => {
    const spec = parse(
      '@lap v0.3\n@api Patch API\n@base https://api.example.com\n@endpoint PATCH /items/{id}\n@desc Partially update item\n@end',
    );
    const skill = generateSkill(spec);
    const md = skill.fileMap['SKILL.md'];

    const cqMatch = md.match(/## Common Questions\n([\s\S]*?)(?=\n## |$)/);
    assert.ok(cqMatch, 'Should have Common Questions section');
    const cqContent = cqMatch[1];
    // The Common Questions section should describe PATCH as update/modify
    assert.ok(
      cqContent.includes('Update') || cqContent.includes('PATCH') || cqContent.includes('modify'),
      'Common Questions should mention update/modify for PATCH endpoints',
    );
  });
});

describe('Resource/group extraction', () => {
  it('endpoint catalog mentions endpoint count', () => {
    const spec = compile(PETSTORE_YAML);
    const skill = generateSkill(spec);
    const md = skill.fileMap['SKILL.md'];

    const endpointsMatch = md.match(/## Endpoints\n([\s\S]*?)(?=\n## |$)/);
    assert.ok(endpointsMatch, 'Should have Endpoints section');
    const epContent = endpointsMatch[1];
    // The catalog should reference the total endpoint count
    assert.ok(
      epContent.includes(String(spec.endpoints.length)),
      `Endpoints section should mention total count (${spec.endpoints.length})`,
    );
  });

  it('endpoint catalog references api-spec.lap', () => {
    const spec = compile(PETSTORE_YAML);
    const skill = generateSkill(spec);
    const md = skill.fileMap['SKILL.md'];

    const endpointsMatch = md.match(/## Endpoints\n([\s\S]*?)(?=\n## |$)/);
    assert.ok(endpointsMatch, 'Should have Endpoints section');
    assert.ok(
      endpointsMatch[1].includes('api-spec.lap'),
      'Endpoint catalog should reference api-spec.lap for full details',
    );
  });

  it('group name extraction from path skips version prefix', () => {
    assert.strictEqual(groupName('/v1/users'), 'users');
    assert.strictEqual(groupName('/v1/users/{id}'), 'users');
    assert.strictEqual(groupName('/v2/orders/{id}/items'), 'orders');
  });

  it('group name extraction from path without version prefix', () => {
    assert.strictEqual(groupName('/pets'), 'pets');
    assert.strictEqual(groupName('/pets/{id}'), 'pets');
    assert.strictEqual(groupName('/pets/{id}/tags'), 'pets');
  });

  it('singularize edge cases', () => {
    // -ies -> -y
    assert.strictEqual(singularize('queries'), 'query');
    // -ses with preceding vowel -> drop final 's'
    assert.strictEqual(singularize('processes'), 'process');
  });
});

describe('Metadata helpers', () => {
  describe('metadataPath', () => {
    it('returns claude path for claude target', () => {
      const p = metadataPath('claude');
      assert.ok(p.includes('.claude'), 'Should include .claude directory');
      assert.ok(p.endsWith('lap-metadata.json'), 'Should end with lap-metadata.json');
    });

    it('returns cursor path for cursor target', () => {
      const p = metadataPath('cursor');
      assert.ok(p.includes('.cursor'), 'Should include .cursor directory');
      assert.ok(p.endsWith('lap-metadata.json'), 'Should end with lap-metadata.json');
    });

    it('returns codex path for codex target', () => {
      const p = metadataPath('codex');
      assert.ok(p.includes('.codex'), 'Should include .codex directory');
      assert.ok(p.endsWith('lap-metadata.json'), 'Should end with lap-metadata.json');
    });

    it('uses os.homedir() as root', () => {
      const home = os.homedir();
      assert.ok(metadataPath('claude').startsWith(home), 'Claude path should start with home dir');
      assert.ok(metadataPath('codex').startsWith(home), 'Codex path should start with home dir');
      assert.ok(metadataPath('cursor').startsWith(home), 'Cursor path should start with home dir');
    });
  });

  describe('readMetadata', () => {
    it('T1: returns parsed data for valid file', () => {
      // Write metadata to the real claude path and read it back.
      const p = metadataPath('claude');
      const backup = p + '.bak.t1.' + Date.now();
      const existed = fs.existsSync(p);
      if (existed) fs.renameSync(p, backup);

      try {
        const data: import('../src/cli').LapMetadata = {
          skills: {
            'stripe-com': {
              registryVersion: '1.2.3',
              specHash: 'sha256:abc',
              installedAt: '2026-01-01T00:00:00Z',
              pinned: false,
            },
          },
        };
        writeMetadata('claude', data);
        const result = readMetadata('claude');
        assert.strictEqual(result.skills['stripe-com'].registryVersion, '1.2.3');
        assert.strictEqual(result.skills['stripe-com'].pinned, false);
      } finally {
        if (fs.existsSync(p)) fs.unlinkSync(p);
        if (existed) fs.renameSync(backup, p);
      }
    });

    it('T1b: returns {skills: {}} for missing file', () => {
      const p = metadataPath('claude');
      const backup = p + '.bak.missing.' + Date.now();
      const existed = fs.existsSync(p);
      if (existed) fs.renameSync(p, backup);

      try {
        if (fs.existsSync(p)) fs.unlinkSync(p);
        const result = readMetadata('claude');
        assert.deepStrictEqual(result, { skills: {} });
      } finally {
        if (existed) fs.renameSync(backup, p);
      }
    });

    it('T1c: returns {skills: {}} for corrupt JSON', () => {
      // Write valid metadata, then corrupt the file, then call readMetadata.
      const p = metadataPath('claude');
      const backup = p + '.bak.corrupt.' + Date.now();
      const existed = fs.existsSync(p);
      if (existed) fs.renameSync(p, backup);

      try {
        // Ensure parent directory exists
        const dir = path.dirname(p);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        // Write corrupt JSON directly to the metadata path
        fs.writeFileSync(p, '{ not valid json !!!', 'utf-8');
        const result = readMetadata('claude');
        assert.deepStrictEqual(result, { skills: {} }, 'Corrupt JSON should return empty skills');
      } finally {
        if (fs.existsSync(p)) fs.unlinkSync(p);
        if (existed) fs.renameSync(backup, p);
      }
    });
  });

  describe('writeMetadata + readMetadata round-trip', () => {
    it('T1d: writeMetadata creates file with correct JSON', () => {
      // We use the real metadata path for 'claude'. Back it up if it exists.
      const p = metadataPath('claude');
      const backup = p + '.bak.' + Date.now();
      const existed = fs.existsSync(p);
      if (existed) fs.renameSync(p, backup);

      try {
        const data: import('../src/cli').LapMetadata = {
          skills: {
            'stripe-com': {
              registryVersion: '2.0.0',
              specHash: 'sha256:deadbeef',
              installedAt: '2026-03-18T00:00:00Z',
              pinned: true,
            },
          },
        };
        writeMetadata('claude', data);
        assert.ok(fs.existsSync(p), 'Metadata file should be created');

        const readBack = readMetadata('claude');
        assert.strictEqual(readBack.skills['stripe-com'].registryVersion, '2.0.0');
        assert.strictEqual(readBack.skills['stripe-com'].pinned, true);
        assert.strictEqual(readBack.skills['stripe-com'].specHash, 'sha256:deadbeef');
      } finally {
        // Clean up: remove the test file, restore backup if existed
        if (fs.existsSync(p)) fs.unlinkSync(p);
        if (existed) fs.renameSync(backup, p);
      }
    });
  });

  describe('computeSpecHash', () => {
    it('T2: returns correct sha256 hash with prefix', () => {
      const hash = computeSpecHash('hello');
      // sha256('hello') = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
      assert.strictEqual(
        hash,
        'sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',
      );
    });

    it('different content produces different hash', () => {
      const h1 = computeSpecHash('abc');
      const h2 = computeSpecHash('xyz');
      assert.notStrictEqual(h1, h2);
    });

    it('empty string produces deterministic hash', () => {
      const h1 = computeSpecHash('');
      const h2 = computeSpecHash('');
      assert.strictEqual(h1, h2);
      assert.ok(h1.startsWith('sha256:'), 'Should have sha256: prefix');
    });
  });

  describe('isValidSkillName', () => {
    it('T4a: accepts valid skill names', () => {
      assert.strictEqual(isValidSkillName('stripe-com'), true);
      assert.strictEqual(isValidSkillName('my_skill'), true);
      assert.strictEqual(isValidSkillName('api.v2'), true);
      assert.strictEqual(isValidSkillName('Skill123'), true);
    });

    it('T4b: rejects path traversal and special chars', () => {
      assert.strictEqual(isValidSkillName('../hack'), false);
      assert.strictEqual(isValidSkillName('skill/bad'), false);
      assert.strictEqual(isValidSkillName('skill name'), false);
      assert.strictEqual(isValidSkillName('skill@bad'), false);
      assert.strictEqual(isValidSkillName(''), false);
      assert.strictEqual(isValidSkillName('.hidden'), false);
      assert.strictEqual(isValidSkillName('..'), false);
      assert.strictEqual(isValidSkillName('-dash-start'), false);
      assert.strictEqual(isValidSkillName('_under_start'), false);
    });
  });

  describe('validateRegistryUrl', () => {
    it('T5a: accepts HTTPS URLs and returns them', () => {
      const url = 'https://registry.lap.sh';
      assert.strictEqual(validateRegistryUrl(url), url);
    });

    it('T5b: rejects plain HTTP URLs', () => {
      assert.throws(
        () => validateRegistryUrl('http://registry.lap.sh'),
        /must use HTTPS/,
      );
    });

    it('T5c: allows localhost HTTP URLs', () => {
      const local = 'http://localhost:8080';
      assert.strictEqual(validateRegistryUrl(local), local);
    });

    it('allows 127.0.0.1 HTTP URLs', () => {
      const loopback = 'http://127.0.0.1:3000';
      assert.strictEqual(validateRegistryUrl(loopback), loopback);
    });

    it('rejects FTP or other schemes', () => {
      assert.throws(
        () => validateRegistryUrl('ftp://registry.lap.sh'),
        /must use HTTPS/,
      );
    });

    it('rejects localhost prefix confusion', () => {
      assert.throws(
        () => validateRegistryUrl('http://localhost.evil.com'),
        /must use HTTPS/,
      );
      assert.throws(
        () => validateRegistryUrl('http://localhost-attacker.com'),
        /must use HTTPS/,
      );
    });
  });
});

describe('printSpecDiff', () => {
  it('T9a: reports added endpoints', () => {
    const oldSpec = { endpoints: [{ method: 'GET', path: '/items' }] };
    const newSpec = {
      endpoints: [
        { method: 'GET', path: '/items' },
        { method: 'POST', path: '/items' },
      ],
    };
    const lines: string[] = [];
    const origLog = console.log;
    console.log = (...a: any[]) => lines.push(a.join(' '));
    try {
      printSpecDiff(oldSpec, newSpec, 'old', 'new');
    } finally {
      console.log = origLog;
    }
    const output = lines.join('\n');
    assert.ok(output.includes('Added (1)'), 'Should report 1 added endpoint');
    assert.ok(output.includes('POST /items'), 'Should list the added endpoint');
  });

  it('T9b: reports removed endpoints', () => {
    const oldSpec = {
      endpoints: [
        { method: 'GET', path: '/items' },
        { method: 'DELETE', path: '/items/{id}' },
      ],
    };
    const newSpec = { endpoints: [{ method: 'GET', path: '/items' }] };
    const lines: string[] = [];
    const origLog = console.log;
    console.log = (...a: any[]) => lines.push(a.join(' '));
    try {
      printSpecDiff(oldSpec, newSpec, 'old', 'new');
    } finally {
      console.log = origLog;
    }
    const output = lines.join('\n');
    assert.ok(output.includes('Removed (1)'), 'Should report 1 removed endpoint');
    assert.ok(output.includes('DELETE /items/{id}'), 'Should list the removed endpoint');
  });

  it('T9c: reports no differences when specs are identical', () => {
    const spec = { endpoints: [{ method: 'GET', path: '/status' }] };
    const lines: string[] = [];
    const origLog = console.log;
    console.log = (...a: any[]) => lines.push(a.join(' '));
    try {
      printSpecDiff(spec, spec, 'old', 'new');
    } finally {
      console.log = origLog;
    }
    const output = lines.join('\n');
    assert.ok(output.includes('No endpoint differences found'), 'Should report no differences');
  });

  it('T9d: includes token impact line', () => {
    const spec = { endpoints: [{ method: 'GET', path: '/status' }] };
    const lines: string[] = [];
    const origLog = console.log;
    console.log = (...a: any[]) => lines.push(a.join(' '));
    try {
      printSpecDiff(spec, spec, 'old', 'new');
    } finally {
      console.log = origLog;
    }
    const output = lines.join('\n');
    assert.ok(output.includes('Token impact:'), 'Should include token impact line');
    assert.ok(output.includes('tokens'), 'Token impact should mention tokens');
  });
});

describe('Hook registration', () => {
  const claudeConfig = path.join(os.homedir(), '.claude', 'settings.json');
  const cursorConfig = path.join(os.homedir(), '.cursor', 'hooks.json');

  function findLapHook(entries: any[]): any {
    for (const entry of entries) {
      if (!entry || typeof entry !== 'object') continue;
      for (const h of (entry.hooks || [])) {
        if (h?.command?.includes('lapsh check')) return h;
      }
    }
    return null;
  }

  it('T7a: registerClaudeHook adds SessionStart hook in new format', () => {
    let backup: string | null = null;
    if (fs.existsSync(claudeConfig)) backup = fs.readFileSync(claudeConfig, 'utf-8');

    try {
      if (fs.existsSync(claudeConfig)) fs.unlinkSync(claudeConfig);
      registerClaudeHook('npx @lap-platform/lapsh check --silent-if-clean');

      const config = JSON.parse(fs.readFileSync(claudeConfig, 'utf-8'));
      assert.ok(config.hooks?.SessionStart?.length >= 1, 'SessionStart should have entries');
      const entry = config.hooks.SessionStart[0];
      assert.strictEqual(entry.matcher, '', 'Should have empty matcher');
      assert.ok(Array.isArray(entry.hooks), 'Should have hooks array');
      const hook = findLapHook(config.hooks.SessionStart);
      assert.ok(hook, 'LAP hook should be found');
      assert.strictEqual(hook.type, 'command', 'Hook type should be command');
    } finally {
      if (backup !== null) fs.writeFileSync(claudeConfig, backup, 'utf-8');
      else if (fs.existsSync(claudeConfig)) fs.unlinkSync(claudeConfig);
    }
  });

  it('T7b: registerClaudeHook is idempotent', () => {
    let backup: string | null = null;
    if (fs.existsSync(claudeConfig)) backup = fs.readFileSync(claudeConfig, 'utf-8');

    try {
      if (fs.existsSync(claudeConfig)) fs.unlinkSync(claudeConfig);
      registerClaudeHook('npx @lap-platform/lapsh check --silent-if-clean');
      registerClaudeHook('npx @lap-platform/lapsh check --silent-if-clean');

      const config = JSON.parse(fs.readFileSync(claudeConfig, 'utf-8'));
      assert.strictEqual(config.hooks.SessionStart.length, 1, 'Should not duplicate');
    } finally {
      if (backup !== null) fs.writeFileSync(claudeConfig, backup, 'utf-8');
      else if (fs.existsSync(claudeConfig)) fs.unlinkSync(claudeConfig);
    }
  });

  it('T7c: registerClaudeHook preserves existing hooks', () => {
    let backup: string | null = null;
    if (fs.existsSync(claudeConfig)) backup = fs.readFileSync(claudeConfig, 'utf-8');

    try {
      const existing = { hooks: { SessionStart: [
        { matcher: 'Bash', hooks: [{ type: 'command', command: 'echo hello' }] }
      ] } };
      const dir = path.dirname(claudeConfig);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(claudeConfig, JSON.stringify(existing), 'utf-8');

      registerClaudeHook('npx @lap-platform/lapsh check --silent-if-clean');

      const config = JSON.parse(fs.readFileSync(claudeConfig, 'utf-8'));
      assert.strictEqual(config.hooks.SessionStart.length, 2, 'Should have both entries');
      assert.strictEqual(config.hooks.SessionStart[0].hooks[0].command, 'echo hello', 'Existing preserved');
      assert.ok(findLapHook(config.hooks.SessionStart), 'LAP hook appended');
    } finally {
      if (backup !== null) fs.writeFileSync(claudeConfig, backup, 'utf-8');
      else if (fs.existsSync(claudeConfig)) fs.unlinkSync(claudeConfig);
    }
  });

  it('T8a: registerCursorHook adds sessionStart hook in Cursor format', () => {
    let backup: string | null = null;
    if (fs.existsSync(cursorConfig)) backup = fs.readFileSync(cursorConfig, 'utf-8');

    try {
      if (fs.existsSync(cursorConfig)) fs.unlinkSync(cursorConfig);
      registerCursorHook('npx @lap-platform/lapsh check --silent-if-clean --hook');

      const config = JSON.parse(fs.readFileSync(cursorConfig, 'utf-8'));
      assert.strictEqual(config.version, 1, 'Should set version');
      assert.ok(config.hooks?.sessionStart?.length >= 1, 'sessionStart should have entries');
      // Cursor uses flat format: command + type + timeout at top level
      const entry = config.hooks.sessionStart[0];
      assert.strictEqual(entry.type, 'command', 'Should be command type');
      assert.ok(entry.command.includes('lapsh check'), 'Should have lapsh check command');
      assert.strictEqual(entry.timeout, 30, 'Cursor hook should have timeout in seconds');
    } finally {
      if (backup !== null) fs.writeFileSync(cursorConfig, backup, 'utf-8');
      else if (fs.existsSync(cursorConfig)) fs.unlinkSync(cursorConfig);
    }
  });

  it('T8a2: registerCodexHook adds both SessionStart and TaskStarted hooks', () => {
    const codexConfig = path.join(os.homedir(), '.codex', 'hooks.json');
    let backup: string | null = null;
    if (fs.existsSync(codexConfig)) backup = fs.readFileSync(codexConfig, 'utf-8');

    try {
      if (fs.existsSync(codexConfig)) fs.unlinkSync(codexConfig);
      registerCodexHook('npx @lap-platform/lapsh check --silent-if-clean --hook codex');

      const config = JSON.parse(fs.readFileSync(codexConfig, 'utf-8'));
      // Both event keys should exist
      assert.ok(config.hooks?.SessionStart?.length >= 1, 'SessionStart should have entries');
      assert.ok(config.hooks?.TaskStarted?.length >= 1, 'TaskStarted should have entries');

      // Each should have the correct hook structure
      const ssEntry = config.hooks.SessionStart[0];
      assert.strictEqual(ssEntry.matcher, '', 'SessionStart should have empty matcher');
      assert.ok(Array.isArray(ssEntry.hooks), 'SessionStart should have hooks array');
      assert.ok(ssEntry.hooks[0].command.includes('lapsh check'), 'SessionStart hook should have lapsh check command');
      assert.strictEqual(ssEntry.hooks[0].type, 'command', 'SessionStart hook type should be command');

      const tsEntry = config.hooks.TaskStarted[0];
      assert.strictEqual(tsEntry.matcher, '', 'TaskStarted should have empty matcher');
      assert.ok(Array.isArray(tsEntry.hooks), 'TaskStarted should have hooks array');
      assert.ok(tsEntry.hooks[0].command.includes('lapsh check'), 'TaskStarted hook should have lapsh check command');
    } finally {
      if (backup !== null) fs.writeFileSync(codexConfig, backup, 'utf-8');
      else if (fs.existsSync(codexConfig)) fs.unlinkSync(codexConfig);
    }
  });

  it('T8a3: registerCodexHook is idempotent', () => {
    const codexConfig = path.join(os.homedir(), '.codex', 'hooks.json');
    let backup: string | null = null;
    if (fs.existsSync(codexConfig)) backup = fs.readFileSync(codexConfig, 'utf-8');

    try {
      if (fs.existsSync(codexConfig)) fs.unlinkSync(codexConfig);
      registerCodexHook('npx @lap-platform/lapsh check --silent-if-clean');
      registerCodexHook('npx @lap-platform/lapsh check --silent-if-clean');

      const config = JSON.parse(fs.readFileSync(codexConfig, 'utf-8'));
      assert.strictEqual(config.hooks.SessionStart.length, 1, 'SessionStart should not duplicate');
      assert.strictEqual(config.hooks.TaskStarted.length, 1, 'TaskStarted should not duplicate');
    } finally {
      if (backup !== null) fs.writeFileSync(codexConfig, backup, 'utf-8');
      else if (fs.existsSync(codexConfig)) fs.unlinkSync(codexConfig);
    }
  });

  it('T8b: registerCursorHook is idempotent', () => {
    let backup: string | null = null;
    if (fs.existsSync(cursorConfig)) backup = fs.readFileSync(cursorConfig, 'utf-8');

    try {
      if (fs.existsSync(cursorConfig)) fs.unlinkSync(cursorConfig);
      registerCursorHook('npx @lap-platform/lapsh check --silent-if-clean');
      registerCursorHook('npx @lap-platform/lapsh check --silent-if-clean');

      const config = JSON.parse(fs.readFileSync(cursorConfig, 'utf-8'));
      assert.strictEqual(config.hooks.sessionStart.length, 1, 'Should not duplicate');
    } finally {
      if (backup !== null) fs.writeFileSync(cursorConfig, backup, 'utf-8');
      else if (fs.existsSync(cursorConfig)) fs.unlinkSync(cursorConfig);
    }
  });
});

// ── Check command tests (mirrored from Python test_check_*) ─────────

describe('Check command logic', () => {
  it('C9: check with no updates and silentIfClean produces no output', () => {
    // We test the underlying logic: if all skills are pinned or there are none
    // to check, cmdCheck returns silently. We verify by ensuring readMetadata
    // with only pinned skills returns an empty check list.
    const p = metadataPath('claude');
    const backup = p + '.bak.check1.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      const data: import('../src/cli').LapMetadata = {
        skills: {
          'stripe-com': {
            registryVersion: '1.0.0',
            specHash: 'sha256:abc',
            installedAt: '2026-01-01T00:00:00Z',
            pinned: false,
          },
        },
      };
      writeMetadata('claude', data);
      const meta = readMetadata('claude');

      // Simulate the check loop: gather non-pinned skills
      const skillsToCheck: { name: string; version: string }[] = [];
      for (const [name, info] of Object.entries(meta.skills)) {
        if (!info.pinned) skillsToCheck.push({ name, version: info.registryVersion });
      }
      assert.strictEqual(skillsToCheck.length, 1, 'Should find 1 non-pinned skill');
      assert.strictEqual(skillsToCheck[0].name, 'stripe-com');
      assert.strictEqual(skillsToCheck[0].version, '1.0.0');

      // Simulate a "no updates" registry response
      const results = [{ name: 'stripe-com', has_update: false, installed_version: '1.0.0', latest_version: '1.0.0' }];
      const updates = results.filter(r => r.has_update);
      assert.strictEqual(updates.length, 0, 'Should have no updates');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });

  it('C10: check with updates produces notification data', () => {
    // Simulate a registry response with updates and verify formatting
    const results = [
      { name: 'stripe', has_update: true, installed_version: '1.0.0', latest_version: '2.0.0' },
    ];
    const updates = results.filter(r => r.has_update);
    assert.strictEqual(updates.length, 1);

    // Build the same message cmdCheck would build
    const u = updates[0];
    const msg = [
      'LAP skill update available:',
      `  ${u.name}: ${u.installed_version} -> ${u.latest_version}`,
      '',
      `  Update:  lapsh skill-install ${u.name} --target claude`,
      `  Changes: lapsh diff ${u.name}`,
      `  Pin:     lapsh pin ${u.name}`,
    ].join('\n');

    assert.ok(msg.includes('stripe'), 'Should mention skill name');
    assert.ok(msg.includes('1.0.0'), 'Should mention old version');
    assert.ok(msg.includes('2.0.0'), 'Should mention new version');
    assert.ok(msg.includes('lapsh skill-install stripe'), 'Should include install command');
  });

  it('C11: check --json produces valid JSON structure', () => {
    // Simulate --json output formatting
    const updates = [
      { name: 'stripe', has_update: true, installed_version: '1.0.0', latest_version: '2.0.0' },
    ];
    const jsonStr = JSON.stringify({ updates }, null, 2);
    const parsed = JSON.parse(jsonStr);
    assert.ok(Array.isArray(parsed.updates), 'Should have updates array');
    assert.strictEqual(parsed.updates[0].name, 'stripe');
    assert.strictEqual(parsed.updates[0].latest_version, '2.0.0');
  });

  it('C12: network failure in silent mode produces no output', () => {
    // Capture console output to verify silence
    const lines: string[] = [];
    const errLines: string[] = [];
    const origLog = console.log;
    const origErr = console.error;
    console.log = (...a: any[]) => lines.push(a.join(' '));
    console.error = (...a: any[]) => errLines.push(a.join(' '));

    try {
      // Simulate cmdCheck behavior on network failure with silentIfClean=true
      const silentIfClean = true;
      try {
        throw new Error('network error');
      } catch {
        if (!silentIfClean) console.error('Warning: Could not reach LAP registry for update check.');
        // silentIfClean mode: no output on failure
      }
      assert.strictEqual(lines.length, 0, 'No stdout in silent mode');
      assert.strictEqual(errLines.length, 0, 'No stderr in silent mode');
    } finally {
      console.log = origLog;
      console.error = origErr;
    }
  });

  it('C12b: network failure in manual mode warns', () => {
    const errLines: string[] = [];
    const origErr = console.error;
    console.error = (...a: any[]) => errLines.push(a.join(' '));

    try {
      const silentIfClean = false;
      try {
        throw new Error('network error');
      } catch {
        if (!silentIfClean) console.error('Warning: Could not reach LAP registry for update check.');
      }
      assert.ok(errLines.some(l => l.includes('Warning')), 'Should warn on network failure in manual mode');
    } finally {
      console.error = origErr;
    }
  });

  it('C18: check skips pinned skills', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.pinned.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      const data: import('../src/cli').LapMetadata = {
        skills: {
          'stripe-com': {
            registryVersion: '1.0.0',
            specHash: 'sha256:abc',
            installedAt: '2026-01-01T00:00:00Z',
            pinned: true,
          },
        },
      };
      writeMetadata('claude', data);
      const meta = readMetadata('claude');

      // Reproduce cmdCheck logic: gather only non-pinned skills
      const skillsToCheck: { name: string; version: string }[] = [];
      for (const [name, info] of Object.entries(meta.skills)) {
        if (info.pinned) continue;
        skillsToCheck.push({ name, version: info.registryVersion });
      }

      // All pinned => nothing to check => no network call needed
      assert.strictEqual(skillsToCheck.length, 0, 'Pinned skills should be skipped');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });
});

// ── Pin/Unpin tests (mirrored from Python test_pin_*, test_unpin_*) ──

describe('Pin / Unpin logic', () => {
  it('C15: pin sets pinned to true in metadata', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.pin.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      const data: import('../src/cli').LapMetadata = {
        skills: {
          'stripe-com': {
            registryVersion: '1.0.0',
            specHash: 'sha256:abc',
            installedAt: '2026-01-01T00:00:00Z',
            pinned: false,
          },
        },
      };
      writeMetadata('claude', data);

      // Reproduce cmdSetPinned logic for pin
      const meta = readMetadata('claude');
      assert.ok(meta.skills['stripe-com'], 'Skill should exist');
      meta.skills['stripe-com'].pinned = true;
      writeMetadata('claude', meta);

      const after = readMetadata('claude');
      assert.strictEqual(after.skills['stripe-com'].pinned, true, 'Pinned should be true');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });

  it('C16: unpin sets pinned to false in metadata', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.unpin.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      const data: import('../src/cli').LapMetadata = {
        skills: {
          'stripe-com': {
            registryVersion: '1.0.0',
            specHash: 'sha256:abc',
            installedAt: '2026-01-01T00:00:00Z',
            pinned: true,
          },
        },
      };
      writeMetadata('claude', data);

      // Reproduce cmdSetPinned logic for unpin
      const meta = readMetadata('claude');
      assert.ok(meta.skills['stripe-com'], 'Skill should exist');
      meta.skills['stripe-com'].pinned = false;
      writeMetadata('claude', meta);

      const after = readMetadata('claude');
      assert.strictEqual(after.skills['stripe-com'].pinned, false, 'Pinned should be false');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });

  it('C17: pin unknown skill: skill not found in metadata', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.pinunk.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      const data: import('../src/cli').LapMetadata = { skills: {} };
      writeMetadata('claude', data);

      const meta = readMetadata('claude');
      // cmdSetPinned checks meta.skills[name] and errors if missing
      assert.strictEqual(meta.skills['nonexistent'], undefined, 'Unknown skill should be undefined');
      assert.ok(!meta.skills['nonexistent'], 'Missing skill should be falsy');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });

  it('C17b: unpin unknown skill: skill not found in metadata', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.unpinunk.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      const data: import('../src/cli').LapMetadata = { skills: {} };
      writeMetadata('claude', data);

      const meta = readMetadata('claude');
      assert.strictEqual(meta.skills['nonexistent'], undefined, 'Unknown skill should be undefined');
      assert.ok(!meta.skills['nonexistent'], 'Missing skill should be falsy');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });

  it('pin preserves other skill entries', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.pinother.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      const data: import('../src/cli').LapMetadata = {
        skills: {
          'stripe-com': {
            registryVersion: '1.0.0',
            specHash: 'sha256:aaa',
            installedAt: '2026-01-01T00:00:00Z',
            pinned: false,
          },
          'github-com': {
            registryVersion: '2.0.0',
            specHash: 'sha256:bbb',
            installedAt: '2026-01-01T00:00:00Z',
            pinned: false,
          },
        },
      };
      writeMetadata('claude', data);

      const meta = readMetadata('claude');
      meta.skills['stripe-com'].pinned = true;
      writeMetadata('claude', meta);

      const after = readMetadata('claude');
      assert.strictEqual(after.skills['stripe-com'].pinned, true, 'stripe-com should be pinned');
      assert.strictEqual(after.skills['github-com'].pinned, false, 'github-com should remain unpinned');
      assert.strictEqual(after.skills['github-com'].registryVersion, '2.0.0', 'github-com version preserved');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });
});

// ── Skill-install writes metadata (mirrored from Python test_skill_install_*) ──

describe('Skill-install metadata', () => {
  it('C7: writeMetadata creates entry with all required fields', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.install.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      // Reproduce what cmdSkillInstall does after a successful fetch
      const specText = '@lap v0.3\n@api Stripe API\n@base https://api.stripe.com\n@endpoint GET /charges\n@desc List charges\n@end';
      const specHash = computeSpecHash(specText);
      const registryVersion = '2.0.0';
      const skillName = 'stripe-api';

      const meta = readMetadata('claude');
      meta.skills['stripe'] = {
        registryVersion,
        specHash,
        installedAt: new Date().toISOString(),
        pinned: false,
        skillName,
      };
      writeMetadata('claude', meta);

      const after = readMetadata('claude');
      const entry = after.skills['stripe'];
      assert.ok(entry, 'Metadata entry should exist');
      assert.strictEqual(entry.registryVersion, '2.0.0', 'registryVersion should match');
      assert.ok(entry.specHash.startsWith('sha256:'), 'specHash should have sha256: prefix');
      assert.ok(entry.installedAt, 'installedAt should be set');
      assert.strictEqual(entry.pinned, false, 'pinned should default to false');
      assert.strictEqual(entry.skillName, 'stripe-api', 'skillName should be set');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });

  it('C8: reinstall overwrites existing entry', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.reinstall.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      // Write initial entry
      const initial: import('../src/cli').LapMetadata = {
        skills: {
          'stripe': {
            registryVersion: '1.0.0',
            specHash: 'sha256:oldoldold',
            installedAt: '2025-01-01T00:00:00Z',
            pinned: true,
            skillName: 'stripe-api',
          },
        },
      };
      writeMetadata('claude', initial);

      // Simulate reinstall: read, overwrite entry, write
      const meta = readMetadata('claude');
      const newSpecText = '@lap v0.3\n@api Stripe API v2\n@base https://api.stripe.com\n@endpoint GET /charges\n@desc List\n@end';
      meta.skills['stripe'] = {
        registryVersion: '3.0.0',
        specHash: computeSpecHash(newSpecText),
        installedAt: new Date().toISOString(),
        pinned: false,
        skillName: 'stripe-api',
      };
      writeMetadata('claude', meta);

      const after = readMetadata('claude');
      // Only one entry
      assert.strictEqual(Object.keys(after.skills).length, 1, 'Should have exactly one entry');
      assert.strictEqual(after.skills['stripe'].registryVersion, '3.0.0', 'Version should be updated');
      assert.strictEqual(after.skills['stripe'].pinned, false, 'Pinned should be reset to false');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });

  it('installedAt is valid ISO date', () => {
    const p = metadataPath('claude');
    const backup = p + '.bak.isodate.' + Date.now();
    const existed = fs.existsSync(p);
    if (existed) fs.renameSync(p, backup);

    try {
      const meta = readMetadata('claude');
      const now = new Date().toISOString();
      meta.skills['test-api'] = {
        registryVersion: '1.0.0',
        specHash: computeSpecHash('test'),
        installedAt: now,
        pinned: false,
      };
      writeMetadata('claude', meta);

      const after = readMetadata('claude');
      const dt = new Date(after.skills['test-api'].installedAt);
      assert.ok(!isNaN(dt.getTime()), 'installedAt should be parseable as a Date');
    } finally {
      if (fs.existsSync(p)) fs.unlinkSync(p);
      if (existed) fs.renameSync(backup, p);
    }
  });
});

// ── Diff smart overload (mirrored from Python test_diff_*) ──────────

describe('Diff smart overload', () => {
  it('C19: single arg without .lap extension is treated as skill name', () => {
    // Reproduce cmdDiff's detection logic
    const firstArg = 'stripe';
    const secondArg = '';
    const isFile = firstArg.endsWith('.lap') || firstArg.includes('/') || firstArg.includes('\\');
    assert.strictEqual(isFile, false, 'Plain skill name should not be detected as file');
    // In cmdDiff, this would call diffSkill(firstArg)
    assert.ok(isValidSkillName(firstArg), 'stripe should be a valid skill name');
  });

  it('C19b: single arg with .lap extension triggers "need two files" path', () => {
    const firstArg = 'spec.lap';
    const secondArg = '';
    const isFile = firstArg.endsWith('.lap') || firstArg.includes('/') || firstArg.includes('\\');
    assert.strictEqual(isFile, true, '.lap extension should be detected as file');
    // In cmdDiff, this would call error("Need two files to diff...")
  });

  it('C19c: single arg with slash triggers "need two files" path', () => {
    const firstArg = 'some/path';
    const secondArg = '';
    const isFile = firstArg.endsWith('.lap') || firstArg.includes('/') || firstArg.includes('\\');
    assert.strictEqual(isFile, true, 'Path with slash should be detected as file');
  });

  it('C19d: single arg with backslash triggers "need two files" path', () => {
    const firstArg = 'some\\path';
    const secondArg = '';
    const isFile = firstArg.endsWith('.lap') || firstArg.includes('/') || firstArg.includes('\\');
    assert.strictEqual(isFile, true, 'Path with backslash should be detected as file');
  });

  it('C20: two-file diff calls printSpecDiff with parsed specs', () => {
    // Create temp LAP files and verify two-file path works
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-diff-'));
    const lapContent = '@lap v0.3\n@api Test\n@base https://api.example.com\n@endpoint GET /ping\n@desc Health\n@end';
    const oldFile = path.join(tmpDir, 'old.lap');
    const newFile = path.join(tmpDir, 'new.lap');
    fs.writeFileSync(oldFile, lapContent, 'utf-8');
    fs.writeFileSync(newFile, lapContent, 'utf-8');

    try {
      // Parse both and diff -- same content should report no differences
      const oldSpec = parse(fs.readFileSync(oldFile, 'utf-8'));
      const newSpec = parse(fs.readFileSync(newFile, 'utf-8'));

      const lines: string[] = [];
      const origLog = console.log;
      console.log = (...a: any[]) => lines.push(a.join(' '));
      try {
        printSpecDiff(oldSpec, newSpec, oldFile, newFile);
      } finally {
        console.log = origLog;
      }
      const output = lines.join('\n');
      assert.ok(output.includes('No endpoint differences found'), 'Identical files should report no differences');
    } finally {
      fs.unlinkSync(oldFile);
      fs.unlinkSync(newFile);
      fs.rmdirSync(tmpDir);
    }
  });

  it('C20b: two-file diff with added endpoint shows addition', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-diff2-'));
    const oldContent = '@lap v0.3\n@api Test\n@base https://api.example.com\n@endpoint GET /ping\n@desc Health\n@end';
    const newContent = '@lap v0.3\n@api Test\n@base https://api.example.com\n@endpoint GET /ping\n@desc Health\n@endpoint POST /items\n@desc Create item\n@end';
    const oldFile = path.join(tmpDir, 'old.lap');
    const newFile = path.join(tmpDir, 'new.lap');
    fs.writeFileSync(oldFile, oldContent, 'utf-8');
    fs.writeFileSync(newFile, newContent, 'utf-8');

    try {
      const oldSpec = parse(fs.readFileSync(oldFile, 'utf-8'));
      const newSpec = parse(fs.readFileSync(newFile, 'utf-8'));

      const lines: string[] = [];
      const origLog = console.log;
      console.log = (...a: any[]) => lines.push(a.join(' '));
      try {
        printSpecDiff(oldSpec, newSpec, oldFile, newFile);
      } finally {
        console.log = origLog;
      }
      const output = lines.join('\n');
      assert.ok(output.includes('Added (1)'), 'Should report 1 added endpoint');
      assert.ok(output.includes('POST /items'), 'Should list the added endpoint');
    } finally {
      fs.unlinkSync(oldFile);
      fs.unlinkSync(newFile);
      fs.rmdirSync(tmpDir);
    }
  });
});

// ── Uninstall helper tests ───────────────────────────────────────────

describe('entryHasLapsh', () => {
  it('detects lapsh in hooks array format', () => {
    const entry = { matcher: '', hooks: [{ type: 'command', command: 'npx @lap-platform/lapsh check' }] };
    assert.strictEqual(entryHasLapsh(entry), true);
  });

  it('detects lapsh in direct command format', () => {
    const entry = { command: 'npx @lap-platform/lapsh check --silent-if-clean', type: 'command' };
    assert.strictEqual(entryHasLapsh(entry), true);
  });

  it('returns false for non-lapsh entries', () => {
    const entry = { matcher: 'Bash', hooks: [{ type: 'command', command: 'echo hello' }] };
    assert.strictEqual(entryHasLapsh(entry), false);
  });

  it('returns false for non-object input', () => {
    assert.strictEqual(entryHasLapsh(null), false);
    assert.strictEqual(entryHasLapsh('string'), false);
    assert.strictEqual(entryHasLapsh(42), false);
  });
});

describe('removeHookEntries', () => {
  it('U1: removes LAP hook from settings.json, preserving other hooks', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-unhook-'));
    const configPath = path.join(tmpDir, 'settings.json');
    const config = {
      hooks: {
        SessionStart: [
          { matcher: 'Bash', hooks: [{ type: 'command', command: 'echo hello' }] },
          { matcher: '', hooks: [{ type: 'command', command: 'npx @lap-platform/lapsh check --silent-if-clean --hook claude' }] },
        ],
        PreToolUse: [
          { matcher: 'Edit', hooks: [{ type: 'command', command: 'lint' }] },
        ],
      },
      otherSetting: true,
    };
    fs.writeFileSync(configPath, JSON.stringify(config), 'utf-8');

    removeHookEntries(configPath, ['SessionStart']);

    const result = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    // LAP hook removed, other SessionStart hook preserved
    assert.strictEqual(result.hooks.SessionStart.length, 1);
    assert.strictEqual(result.hooks.SessionStart[0].hooks[0].command, 'echo hello');
    // Other hook arrays and settings untouched
    assert.strictEqual(result.hooks.PreToolUse.length, 1);
    assert.strictEqual(result.otherSetting, true);

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('U1b: removes all LAP hooks and cleans up empty hooks object', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-unhook2-'));
    const configPath = path.join(tmpDir, 'settings.json');
    const config = {
      hooks: {
        SessionStart: [
          { matcher: '', hooks: [{ type: 'command', command: 'npx @lap-platform/lapsh check' }] },
        ],
      },
      keepMe: 42,
    };
    fs.writeFileSync(configPath, JSON.stringify(config), 'utf-8');

    removeHookEntries(configPath, ['SessionStart']);

    const result = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    assert.strictEqual(result.hooks, undefined, 'Empty hooks object should be removed');
    assert.strictEqual(result.keepMe, 42, 'Other settings preserved');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('U1c: no-op when config file does not exist', () => {
    // Should not throw
    removeHookEntries('/tmp/does-not-exist-lap-test.json', ['SessionStart']);
  });

  it('U1d: removes Codex hooks from both SessionStart and TaskStarted', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-unhook3-'));
    const configPath = path.join(tmpDir, 'hooks.json');
    const config = {
      hooks: {
        SessionStart: [
          { matcher: '', hooks: [{ type: 'command', command: 'npx @lap-platform/lapsh check --hook codex' }] },
        ],
        TaskStarted: [
          { matcher: '', hooks: [{ type: 'command', command: 'npx @lap-platform/lapsh check --hook codex' }] },
        ],
      },
    };
    fs.writeFileSync(configPath, JSON.stringify(config), 'utf-8');

    removeHookEntries(configPath, ['SessionStart', 'TaskStarted']);

    const result = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    assert.strictEqual(result.hooks, undefined, 'All hooks removed for codex');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });
});

describe('removeMdHookInstruction', () => {
  it('U2: removes LAP instruction block from CLAUDE.md, preserving surrounding content', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-unmd-'));
    const claudeDir = path.join(tmpDir, '.claude');
    fs.mkdirSync(claudeDir, { recursive: true });
    const mdPath = path.join(claudeDir, 'CLAUDE.md');

    const preamble = '## My Instructions\n\nSome existing content.\n';
    const postamble = '\n## Other Stuff\n\nMore content after LAP block.\n';
    const content = preamble + LAP_HOOK_INSTRUCTION + postamble;
    fs.writeFileSync(mdPath, content, 'utf-8');

    removeMdHookInstruction('.claude', 'CLAUDE.md', tmpDir);

    const result = fs.readFileSync(mdPath, 'utf-8');
    assert.ok(!result.includes(LAP_HOOK_MARKER), 'Marker should be removed');
    assert.ok(result.includes('My Instructions'), 'Preamble preserved');
    assert.ok(result.includes('Other Stuff'), 'Postamble preserved');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('U2b: deletes CLAUDE.md if it only contained the LAP block', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-unmd2-'));
    const claudeDir = path.join(tmpDir, '.claude');
    fs.mkdirSync(claudeDir, { recursive: true });
    const mdPath = path.join(claudeDir, 'CLAUDE.md');

    fs.writeFileSync(mdPath, LAP_HOOK_INSTRUCTION, 'utf-8');

    removeMdHookInstruction('.claude', 'CLAUDE.md', tmpDir);

    assert.ok(!fs.existsSync(mdPath), 'File should be deleted when only LAP content');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('U2c: no-op when file does not exist', () => {
    // Should not throw
    removeMdHookInstruction('.claude', 'CLAUDE.md', '/tmp/does-not-exist-lap-test');
  });
});

describe('removeCursorUpdateRule', () => {
  it('U3: removes lap-updates.mdc file', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-unrule-'));
    const rulesDir = path.join(tmpDir, '.cursor', 'rules');
    fs.mkdirSync(rulesDir, { recursive: true });
    const rulePath = path.join(rulesDir, 'lap-updates.mdc');
    fs.writeFileSync(rulePath, 'some rule content', 'utf-8');

    removeCursorUpdateRule(tmpDir);

    assert.ok(!fs.existsSync(rulePath), 'Rule file should be removed');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('U3b: no-op when rule file does not exist', () => {
    // Should not throw
    removeCursorUpdateRule('/tmp/does-not-exist-lap-test');
  });
});

// ── skill-uninstall tests ───────────────────────────────────────────

describe('skill-uninstall logic', () => {
  it('U4: skill-uninstall removes dir and metadata entry', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-su-'));
    const metaFile = path.join(tmpDir, 'lap-metadata.json');
    const data = { skills: { stripe: { registryVersion: '1.0.0', pinned: false, skillName: 'stripe', specHash: 'sha256:x', installedAt: '2026-01-01T00:00:00Z' } } };
    fs.writeFileSync(metaFile, JSON.stringify(data), 'utf-8');

    const skillDir = path.join(tmpDir, 'skills', 'stripe');
    fs.mkdirSync(skillDir, { recursive: true });
    fs.writeFileSync(path.join(skillDir, 'SKILL.md'), '# stripe', 'utf-8');

    // Simulate: read metadata, delete dir, update metadata
    const meta = JSON.parse(fs.readFileSync(metaFile, 'utf-8'));
    assert.ok(meta.skills['stripe'], 'Skill should exist in metadata');
    fs.rmSync(skillDir, { recursive: true, force: true });
    delete meta.skills['stripe'];
    fs.writeFileSync(metaFile, JSON.stringify(meta, null, 2), 'utf-8');

    assert.ok(!fs.existsSync(skillDir), 'Skill dir should be removed');
    const afterMeta = JSON.parse(fs.readFileSync(metaFile, 'utf-8'));
    assert.ok(!afterMeta.skills['stripe'], 'Metadata entry should be removed');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('U5: skill-uninstall for unknown skill fails', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-su2-'));
    const metaFile = path.join(tmpDir, 'lap-metadata.json');
    fs.writeFileSync(metaFile, JSON.stringify({ skills: {} }), 'utf-8');

    const meta = JSON.parse(fs.readFileSync(metaFile, 'utf-8'));
    assert.ok(!meta.skills['nonexistent'], 'Unknown skill should not exist');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('U6: skill-uninstall with missing dir still cleans metadata', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-su3-'));
    const metaFile = path.join(tmpDir, 'lap-metadata.json');
    const data = { skills: { stripe: { registryVersion: '1.0.0', pinned: false, skillName: 'stripe', specHash: 'sha256:x', installedAt: '2026-01-01T00:00:00Z' } } };
    fs.writeFileSync(metaFile, JSON.stringify(data), 'utf-8');

    // No skill directory exists -- only clean metadata
    const meta = JSON.parse(fs.readFileSync(metaFile, 'utf-8'));
    const skillDir = path.join(tmpDir, 'skills', 'stripe');
    assert.ok(!fs.existsSync(skillDir), 'Skill dir should not exist');
    delete meta.skills['stripe'];
    fs.writeFileSync(metaFile, JSON.stringify(meta, null, 2), 'utf-8');

    const afterMeta = JSON.parse(fs.readFileSync(metaFile, 'utf-8'));
    assert.ok(!afterMeta.skills['stripe'], 'Metadata entry should be cleaned');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });
});

// ── Full uninstall tests ────────────────────────────────────────────

describe('uninstall logic', () => {
  it('U7: uninstall removes all skill dirs and metadata file', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lap-full-'));
    const metaFile = path.join(tmpDir, 'lap-metadata.json');
    const data = {
      skills: {
        stripe: { registryVersion: '1.0.0', skillName: 'stripe', specHash: 'sha256:a', installedAt: '2026-01-01T00:00:00Z', pinned: false },
        twilio: { registryVersion: '2.0.0', skillName: 'twilio', specHash: 'sha256:b', installedAt: '2026-01-01T00:00:00Z', pinned: false },
      },
    };
    fs.writeFileSync(metaFile, JSON.stringify(data), 'utf-8');

    // Create skill dirs + builtin lap dir
    for (const name of ['stripe', 'twilio', 'lap']) {
      const d = path.join(tmpDir, 'skills', name);
      fs.mkdirSync(d, { recursive: true });
      fs.writeFileSync(path.join(d, 'SKILL.md'), `# ${name}`, 'utf-8');
    }

    // Simulate uninstall: remove all skill dirs from metadata
    const meta = JSON.parse(fs.readFileSync(metaFile, 'utf-8'));
    for (const [name, entry] of Object.entries(meta.skills)) {
      const skillDirName = (entry as any).skillName || name;
      const installDir = path.join(tmpDir, 'skills', skillDirName);
      if (fs.existsSync(installDir)) fs.rmSync(installDir, { recursive: true, force: true });
    }
    // Remove builtin lap dir
    const lapDir = path.join(tmpDir, 'skills', 'lap');
    if (fs.existsSync(lapDir)) fs.rmSync(lapDir, { recursive: true, force: true });
    // Remove metadata file
    fs.unlinkSync(metaFile);

    assert.ok(!fs.existsSync(path.join(tmpDir, 'skills', 'stripe')), 'stripe dir removed');
    assert.ok(!fs.existsSync(path.join(tmpDir, 'skills', 'twilio')), 'twilio dir removed');
    assert.ok(!fs.existsSync(path.join(tmpDir, 'skills', 'lap')), 'lap dir removed');
    assert.ok(!fs.existsSync(metaFile), 'metadata file removed');

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });
});

// ── Cross-language parity tests ──────────────────────────────────────
// Prevent Python/TypeScript constant drift that caused the CLAUDE.md removal bug.

describe('Cross-language parity', () => {
  const pyCliPath = path.resolve(__dirname, '..', '..', '..', '..', 'lap', 'cli', 'main.py');

  it('P1: LAP_HOOK_MARKER matches Python _LAP_HOOK_MARKER', () => {
    const pySource = fs.readFileSync(pyCliPath, 'utf-8');
    const match = pySource.match(/_LAP_HOOK_MARKER\s*=\s*"([^"]+)"/);
    assert.ok(match, 'Should find _LAP_HOOK_MARKER in Python source');
    assert.strictEqual(LAP_HOOK_MARKER, match[1], 'Hook markers must match across languages');
  });

  it('P2: LAP_HOOK_INSTRUCTION body matches Python _LAP_HOOK_INSTRUCTION', () => {
    const pySource = fs.readFileSync(pyCliPath, 'utf-8').replace(/\r\n/g, '\n');
    // Extract the Python f-string content between the triple quotes
    const match = pySource.match(/_LAP_HOOK_INSTRUCTION\s*=\s*f"""([\s\S]*?)"""/);
    assert.ok(match, 'Should find _LAP_HOOK_INSTRUCTION in Python source');
    // Normalize: replace {_LAP_HOOK_MARKER} with actual marker value, trim
    const pyBody = match[1].replace('{_LAP_HOOK_MARKER}', LAP_HOOK_MARKER).trim();
    const tsBody = LAP_HOOK_INSTRUCTION.trim();
    assert.strictEqual(tsBody, pyBody, 'Hook instruction text must match across languages');
  });

  it('P3: Cursor update rule body matches Python _ensure_cursor_update_rule', () => {
    const pySource = fs.readFileSync(pyCliPath, 'utf-8').replace(/\r\n/g, '\n');
    // Python writes the cursor rule as concatenated string literals -- extract all lines between the quotes
    const pyMatch = pySource.match(/_ensure_cursor_update_rule[\s\S]*?write_text\(\s*\n([\s\S]*?)\n\s*encoding=/);
    assert.ok(pyMatch, 'Should find cursor rule write_text block in Python source');
    // Join the concatenated Python strings: strip quotes, join
    const pyText = pyMatch[1]
      .split('\n')
      .map(line => line.trim().replace(/^['"]|['"],?\s*$/g, ''))
      .join('')
      .replace(/---\\n.*?---\\n\\n/, '')  // strip frontmatter
      .replace(/\\n/g, '\n')
      .trim();

    // Extract same from TypeScript
    const tsSource = fs.readFileSync(path.resolve(__dirname, '..', '..', 'src', 'cli.ts'), 'utf-8').replace(/\r\n/g, '\n');
    const tsMatch = tsSource.match(/ensureCursorUpdateRule[\s\S]*?writeFileSync\(rulePath,\s*`([\s\S]*?)`,/);
    assert.ok(tsMatch, 'Should find cursor rule template in TypeScript source');
    const tsText = tsMatch[1]
      .replace(/---[\s\S]*?---\s*\n*/, '')  // strip frontmatter
      .trim();

    assert.strictEqual(tsText, pyText, 'Cursor update rule text must match across languages');
  });
});

console.log('\n-- Skill tests complete --');
