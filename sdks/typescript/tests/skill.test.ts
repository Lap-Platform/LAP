import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as path from 'path';
import { parse } from '../src/parser';
import { generateSkill, slugify, singularize, VALID_TARGETS } from '../src/skill';
import type { SkillOptions } from '../src/skill';
import { compile } from '../src/compilers/index';
import { groupName } from '../src/serializer';

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
      const skillsDir = path.resolve(__dirname, '../../../../skills');
      assert.ok(fs.existsSync(skillsDir), `Skills dir should exist at ${skillsDir}`);
      assert.ok(fs.existsSync(path.join(skillsDir, 'cursor', 'lap.mdc')), 'Cursor skill should exist');
      assert.ok(fs.existsSync(path.join(skillsDir, 'lap', 'SKILL.md')), 'Claude skill should exist');
    });

    it('each target has reference files', () => {
      const skillsDir = path.resolve(__dirname, '../../../../skills');
      const targets = [
        { name: 'claude', dir: path.join(skillsDir, 'lap') },
        { name: 'cursor', dir: path.join(skillsDir, 'cursor') },
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

console.log('\n-- Skill tests complete --');
