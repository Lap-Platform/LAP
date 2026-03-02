import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import { hasClaudeCli, replaceSection } from '../src/skill_llm';

describe('Skill LLM', () => {
  describe('hasClaudeCli', () => {
    it('should return a boolean', () => {
      const result = hasClaudeCli();
      assert.strictEqual(typeof result, 'boolean');
    });
  });

  describe('replaceSection', () => {
    it('should replace Common Questions section', () => {
      const md = `# Title

## Auth
Bearer token

## Common Questions
- Old question 1
- Old question 2

## Response Tips
- Some tip`;

      const result = replaceSection(md, 'Common Questions', 'New enhanced content here');
      assert.ok(result.includes('## Enhanced Skill Content'), 'Should have new section header');
      assert.ok(result.includes('New enhanced content here'), 'Should have new content');
      assert.ok(!result.includes('Old question'), 'Should not have old content');
      assert.ok(result.includes('## Response Tips'), 'Should preserve next section');
    });

    it('should handle section at end of document', () => {
      const md = `# Title

## Common Questions
- Last section content`;

      const result = replaceSection(md, 'Common Questions', 'Replaced');
      assert.ok(result.includes('## Enhanced Skill Content'), 'Should have new section header');
      assert.ok(result.includes('Replaced'), 'Should have new content');
    });

    it('should return original string when section does not exist', () => {
      const md = `# Title

## Auth
Bearer token

## Response Tips
- Some tip`;

      const result = replaceSection(md, 'Nonexistent Section', 'New content');
      assert.strictEqual(result, md, 'Should return original string unchanged');
    });

    it('should handle section at start of document', () => {
      const md = `## Common Questions
- Question 1

## Next Section
- Content`;

      const result = replaceSection(md, 'Common Questions', 'Replaced start');
      assert.ok(result.includes('Replaced start'), 'Should have new content');
      assert.ok(result.includes('## Next Section'), 'Should preserve next section');
    });
  });
});

console.log('\n-- Skill LLM tests complete --');
