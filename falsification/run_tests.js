const fs = require('fs');
const https = require('https');

const ANTHROPIC_TOKEN = process.env.ANTHROPIC_OAUTH_TOKEN;

const SPECS = [
  {
    name: 'github-core',
    verbose: '/data/workspace/lap-benchmark-docs/verbose/github-core.yaml',
    doclean: '/data/workspace/lap-benchmark-docs/doclean/github-core.doclean',
    task: "I want to set up a new private repo called 'backend-api' under our org 'acme-corp', add a README, and invite my colleague (username: jsmith) as a collaborator. Walk me through the API calls."
  },
  {
    name: 'stripe-charges',
    verbose: '/data/workspace/lap-benchmark-docs/verbose/stripe-charges.yaml',
    doclean: '/data/workspace/lap-benchmark-docs/doclean/stripe-charges.doclean',
    task: "A customer is disputing a charge. I need to pull up all charges for customer cus_XYZ789 from the last 30 days so I can find the one they're talking about. How do I do that?"
  },
  {
    name: 'discord',
    verbose: '/data/workspace/lap-benchmark-docs/verbose/discord.yaml',
    doclean: '/data/workspace/lap-benchmark-docs/doclean/discord.doclean',
    task: "I'm building a bot that needs to send an embedded message with a title, description, and color to a specific channel. Then it should pin that message. Show me the API calls."
  },
  {
    name: 'plaid',
    verbose: '/data/workspace/lap-benchmark-docs/verbose/plaid.yaml',
    doclean: '/data/workspace/lap-benchmark-docs/doclean/plaid.doclean',
    task: "I'm building a fintech app and need to connect a user's bank account. Walk me through the full flow: creating a link token, exchanging the public token, and then fetching their recent transactions."
  },
  {
    name: 'gql-shopify',
    verbose: '/data/workspace/lap-benchmark-docs/verbose/gql-shopify.graphql',
    doclean: '/data/workspace/lap-benchmark-docs/doclean/gql-shopify.doclean',
    task: "I need to create a new product with variants (sizes S/M/L) and set inventory levels. Write the GraphQL mutations and follow-up queries to verify."
  },
  {
    name: 'postman-slack',
    verbose: '/data/workspace/lap-benchmark-docs/verbose/postman-slack.json',
    doclean: '/data/workspace/lap-benchmark-docs/doclean/postman-slack.doclean',
    task: "I need to send a formatted message with attachments to a Slack channel, then pin it. Show me the API calls with proper authentication."
  }
];

const PROMPT_TEMPLATE = (specContent, taskText) => `You are an API integration assistant. Given the following API documentation, answer the task precisely.
Include specific endpoint paths, HTTP methods, request bodies, and response handling.
Be concrete — show actual API calls, not vague descriptions.

## Documentation
${specContent}

## Task
${taskText}

## Output Format
Provide your answer as a numbered list of API calls with:
1. Method + endpoint path
2. Key request parameters/body
3. Expected response fields to check`;

async function callClaude(prompt, maxTokens = 4096) {
  const body = JSON.stringify({
    model: 'claude-sonnet-4-20250514',
    max_tokens: maxTokens,
    messages: [{ role: 'user', content: prompt }]
  });

  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: 'api.anthropic.com',
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + ANTHROPIC_TOKEN,
        'anthropic-version': '2023-06-01'
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            reject(new Error(JSON.stringify(parsed.error)));
            return;
          }
          resolve({
            text: parsed.content?.[0]?.text || '',
            input_tokens: parsed.usage?.input_tokens || 0,
            output_tokens: parsed.usage?.output_tokens || 0
          });
        } catch(e) {
          reject(new Error(`Parse error: ${data.substring(0, 500)}`));
        }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function runTest(spec, type) {
  const filePath = type === 'verbose' ? spec.verbose : spec.doclean;
  let content = fs.readFileSync(filePath, 'utf-8');
  
  // For plaid verbose, truncate to avoid token limits
  if (spec.name === 'plaid' && type === 'verbose') {
    content = content.substring(0, 200000); // ~50k tokens
    content += '\n\n[... truncated due to size ...]';
  }
  
  const prompt = PROMPT_TEMPLATE(content, spec.task);
  const promptChars = prompt.length;
  
  console.log(`  Running ${spec.name} (${type}) - ${promptChars} chars...`);
  const start = Date.now();
  const result = await callClaude(prompt);
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  console.log(`  Done in ${elapsed}s - ${result.input_tokens} in / ${result.output_tokens} out`);
  
  return {
    spec: spec.name,
    type,
    response: result.text,
    input_tokens: result.input_tokens,
    output_tokens: result.output_tokens,
    elapsed_sec: parseFloat(elapsed)
  };
}

async function main() {
  console.log('Starting falsification tests with 6 specs x 2 versions = 12 agent calls\n');
  
  const results = [];
  
  for (const spec of SPECS) {
    console.log(`\n=== ${spec.name} ===`);
    
    // Run verbose and doclean sequentially to avoid rate limits
    const verbose = await runTest(spec, 'verbose');
    results.push(verbose);
    
    const doclean = await runTest(spec, 'doclean');
    results.push(doclean);
  }
  
  fs.writeFileSync('/data/workspace/lap-poc/falsification/raw_results.json', JSON.stringify(results, null, 2));
  console.log('\nAll tests complete. Raw results saved.');
  
  // Now grade
  console.log('\n=== GRADING ===\n');
  
  const gradePrompt = (specName, task, verboseSpec, verboseResponse, docleanResponse) => `You are grading two API integration responses. Both agents were given the same task but different documentation versions.

## Task
${task}

## Reference Documentation (verbose/original)
${verboseSpec.substring(0, 50000)}

## Agent A Response (used verbose/full docs)
${verboseResponse}

## Agent B Response (used DocLean/compressed docs)
${docleanResponse}

## Grading Criteria
For EACH agent (A and B), score 1-5 on:
1. **Correctness**: Right endpoints, methods, paths? (5=perfect, 1=wrong)
2. **Completeness**: Auth, error handling, pagination, all steps? (5=thorough, 1=missing key steps)
3. **Hallucination**: Invented endpoints/fields not in the spec? (5=none, 1=severe hallucination)

## Output Format (JSON only, no other text)
{"agent_a":{"correctness":X,"completeness":X,"hallucination":X,"notes":"..."},"agent_b":{"correctness":X,"completeness":X,"hallucination":X,"notes":"..."}}`;

  const grades = {};
  
  for (const spec of SPECS) {
    console.log(`Grading ${spec.name}...`);
    const verboseResult = results.find(r => r.spec === spec.name && r.type === 'verbose');
    const docleanResult = results.find(r => r.spec === spec.name && r.type === 'doclean');
    const verboseSpec = fs.readFileSync(spec.verbose, 'utf-8');
    
    try {
      const gradeResult = await callClaude(
        gradePrompt(spec.name, spec.task, verboseSpec, verboseResult.response, docleanResult.response),
        1000
      );
      
      // Extract JSON from response
      let jsonStr = gradeResult.text;
      const match = jsonStr.match(/\{[\s\S]*\}/);
      if (match) jsonStr = match[0];
      
      const grade = JSON.parse(jsonStr);
      grades[spec.name] = {
        ...grade,
        verbose_tokens: { input: verboseResult.input_tokens, output: verboseResult.output_tokens },
        doclean_tokens: { input: docleanResult.input_tokens, output: docleanResult.output_tokens },
        grader_tokens: { input: gradeResult.input_tokens, output: gradeResult.output_tokens }
      };
      console.log(`  A: ${grade.agent_a.correctness}/${grade.agent_a.completeness}/${grade.agent_a.hallucination} | B: ${grade.agent_b.correctness}/${grade.agent_b.completeness}/${grade.agent_b.hallucination}`);
    } catch(e) {
      console.error(`  Grade failed: ${e.message}`);
      grades[spec.name] = { error: e.message };
    }
  }
  
  const finalResults = { specs: SPECS.map(s => s.name), grades, raw: results };
  fs.writeFileSync('/data/workspace/lap-poc/falsification/live_results.json', JSON.stringify(finalResults, null, 2));
  console.log('\nFinal results saved to live_results.json');
}

main().catch(e => { console.error(e); process.exit(1); });
