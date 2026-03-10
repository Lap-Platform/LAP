#!/usr/bin/env node
/**
 * LAP CLI (Node.js) -- authenticate, publish, compile specs, and generate skills.
 *
 * Usage:
 *   lapsh login                           # Browser OAuth, store token
 *   lapsh logout                          # Revoke + delete local creds
 *   lapsh whoami                          # Show current user
 *   lapsh publish <spec> --provider <p>   # Compile + publish spec
 *   lapsh compile <spec> [-o out]         # Local compilation to LAP
 *   lapsh skill <spec> [-o dir]           # Generate Claude Code skill
 *   lapsh skill-batch <dir> -o <outdir>   # Batch generate skills
 *   lapsh skill-install <name>            # Install skill from registry
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  loadCredentials,
  saveCredentials,
  clearCredentials,
  getToken,
  apiRequest,
  pollSseStream,
  openBrowser,
  getRegistryUrl,
} from './auth';
import { parse } from './parser';
import { toLap } from './serializer';
import { generateSkill } from './skill';
import { enhanceSkill, hasClaudeCli } from './skill_llm';
import { compile } from './compilers/index';

// ── Helpers ─────────────────────────────────────────────────────────

function info(msg: string): void {
  console.log(`\x1b[32m✓\x1b[0m ${msg}`);
}

function warn(msg: string): void {
  console.error(`\x1b[33m⚠\x1b[0m ${msg}`);
}

function error(msg: string): never {
  console.error(`\x1b[31m✗\x1b[0m ${msg}`);
  process.exit(1);
}

function resolveLayer(explicit: number | undefined): number {
  if (explicit !== undefined) return explicit;
  return hasClaudeCli() ? 2 : 1;
}

function usage(): never {
  console.log(`LAP CLI (Node.js)

Commands:
  login [--name <token-name>]           Authenticate with the LAP registry via GitHub
  logout                                Log out and revoke API token
  whoami                                Show current authenticated user
  publish <spec> --provider <slug>      Compile and publish a spec to the registry
    [--name <name>]                     Override spec name
    [--source-url <url>]                Upstream spec URL
  compile <spec> [-o output] [--lean]   Compile API spec to LAP format
    [-f format]                         Force format (openapi, graphql, etc.)
  skill <spec> [-o dir] [--layer 1|2]   Generate a Claude Code skill
    [--full-spec] [--install]           Include full spec / install to ~/.claude/skills
    [-f format]                         Force spec format
  skill-batch <dir> -o <outdir>         Batch generate skills
    [--layer 1|2] [-v]                  Layer + verbose mode
  skill-install <name> [--dir <path>]   Install skill from registry

Environment:
  LAP_REGISTRY                          Registry URL (default: https://registry.lap.sh)`);
  process.exit(0);
}

// ── Auth Commands ───────────────────────────────────────────────────

async function cmdLogin(tokenName?: string): Promise<void> {
  const creds = loadCredentials();
  if (creds) {
    info(`Already logged in as ${creds.username}. Run 'lapsh logout' first to switch accounts.`);
    return;
  }

  console.log(`Authenticating with ${getRegistryUrl()}...`);

  const body = tokenName ? { name: tokenName } : undefined;
  const result = await apiRequest('POST', '/auth/cli/session', body);
  const sessionId = result.session_id as string;
  const streamKey = result.stream_key as string;
  const authUrl = result.auth_url as string;

  console.log('Opening browser for GitHub authorization...');
  openBrowser(authUrl);
  console.log('Waiting for authentication (press Ctrl+C to cancel)...');

  const { token, username } = await pollSseStream(sessionId, streamKey);
  saveCredentials(token, username);
  info(`Logged in as ${username}`);
}

async function cmdLogout(): Promise<void> {
  const token = getToken();
  if (!token) {
    info('Not logged in.');
    return;
  }

  try {
    await apiRequest('DELETE', '/auth/cli/token', undefined, token);
  } catch {
    // Server error is OK -- still clear local creds
  }

  clearCredentials();
  info('Logged out.');
}

async function cmdWhoami(): Promise<void> {
  const token = getToken();
  if (!token) {
    console.log("Not logged in. Run 'lapsh login' to authenticate.");
    return;
  }

  const result = await apiRequest('GET', '/auth/me', undefined, token);
  const user = (result.user || {}) as Record<string, unknown>;
  info(`Logged in as ${user.username || 'unknown'}`);
}

async function cmdPublish(args: string[]): Promise<void> {
  const token = getToken();
  if (!token) {
    error("Not logged in. Run 'lapsh login' first.");
  }

  // Parse args: <spec> --provider <slug> [--name <name>] [--source-url <url>]
  let specPath = '';
  let provider = '';
  let name = '';
  let sourceUrl = '';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--provider' && i + 1 < args.length) {
      provider = args[++i];
    } else if (args[i] === '--name' && i + 1 < args.length) {
      name = args[++i];
    } else if (args[i] === '--source-url' && i + 1 < args.length) {
      sourceUrl = args[++i];
    } else if (!args[i].startsWith('--')) {
      specPath = args[i];
    }
  }

  if (!specPath) error('Missing spec file path. Usage: lapsh publish <spec> --provider <slug>');
  if (!provider) error('Missing --provider flag. Usage: lapsh publish <spec> --provider <domain>');
  if (!fs.existsSync(specPath)) error(`File not found: ${specPath}`);

  // Read spec and compile via registry API
  const specContent = fs.readFileSync(specPath, 'utf-8');
  const sourceSize = fs.statSync(specPath).size;

  console.log(`Compiling ${path.basename(specPath)} via registry...`);

  // Use the registry compile endpoint
  const compileResult = await apiRequest('POST', '/v1/compile', {
    content: specContent,
    filename: path.basename(specPath),
  });

  const spec = compileResult.lap as string;
  const leanSpec = compileResult.leanLap as string;

  if (!spec) error('Compilation returned empty spec.');

  // Extract name from compiled spec if not provided
  if (!name) {
    const apiMatch = spec.match(/@api\s+(.+)/);
    if (apiMatch) {
      name = apiMatch[1].trim().toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '').replace(/-+/g, '-');
    }
    if (!name) error('Could not auto-detect spec name. Use --name to specify.');
  }

  console.log(`Publishing ${name} to provider ${provider}...`);
  const result = await apiRequest(
    'POST',
    `/v1/apis/${encodeURIComponent(name)}`,
    {
      spec,
      lean_spec: leanSpec,
      provider,
      source_url: sourceUrl,
      source_size: sourceSize,
    },
    token,
  );

  info(`Published ${name} v${result.version || '?'} (provider: ${result.provider || provider})`);
}

// ── Compile Command ─────────────────────────────────────────────────

async function cmdCompile(args: string[]): Promise<void> {
  let specPath = '';
  let output = '';
  let format: string | undefined;
  let lean = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-o' || args[i] === '--output') { output = args[++i]; }
    else if (args[i] === '-f' || args[i] === '--format') { format = args[++i]; }
    else if (args[i] === '--lean') { lean = true; }
    else if (!args[i].startsWith('-')) { specPath = args[i]; }
  }

  if (!specPath) error('Missing spec file. Usage: lapsh compile <spec> [-o output] [--lean] [-f format]');
  if (!fs.existsSync(specPath)) error(`File not found: ${specPath}`);

  const spec = compile(specPath, format ? { format } : undefined);
  const result = toLap(spec, { lean });

  if (output) {
    const dir = path.dirname(output);
    if (dir) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(output, result, 'utf-8');
    info(`Compiled ${path.basename(specPath)} -> ${output}`);
    info(`${spec.endpoints.length} endpoints | ${result.length.toLocaleString()} chars | ${lean ? 'lean' : 'standard'} mode`);
  } else {
    console.log(result);
  }
}

// ── Skill Commands ──────────────────────────────────────────────────

async function cmdSkill(args: string[]): Promise<void> {
  let specPath = '';
  let output = '';
  let format: string | undefined;
  let layerArg: number | undefined;
  let fullSpec = false;
  let install = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-o' || args[i] === '--output') { output = args[++i]; }
    else if (args[i] === '-f' || args[i] === '--format') { format = args[++i]; }
    else if (args[i] === '--layer') { layerArg = parseInt(args[++i], 10); }
    else if (args[i] === '--full-spec') { fullSpec = true; }
    else if (args[i] === '--install') { install = true; }
    else if (!args[i].startsWith('-')) { specPath = args[i]; }
  }

  if (layerArg !== undefined && (isNaN(layerArg) || (layerArg !== 1 && layerArg !== 2))) {
    error(`Invalid --layer value: ${layerArg}. Must be 1 or 2.`);
  }
  if (!specPath) error('Missing spec file. Usage: lapsh skill <spec> [-o output] [--layer 1|2]');
  if (!fs.existsSync(specPath)) error(`File not found: ${specPath}`);

  // Parse or compile spec
  let spec;
  if (specPath.endsWith('.lap')) {
    const text = fs.readFileSync(specPath, 'utf-8');
    spec = parse(text);
  } else {
    spec = compile(specPath, format ? { format } : undefined);
  }

  const layer = resolveLayer(layerArg);
  let skill = generateSkill(spec, { layer, lean: !fullSpec });

  // Layer 2 enhancement
  if (layer === 2) {
    try {
      console.log('Enhancing skill with LLM (Layer 2)...');
      skill = enhanceSkill(spec, skill);
    } catch (err: unknown) {
      if (layerArg === 2) {
        // Explicit layer 2 -- warn on failure
        const msg = err instanceof Error ? err.message : String(err);
        warn(`Layer 2 enhancement failed: ${msg}`);
        warn('Falling back to Layer 1 skill.');
      } else {
        // Auto-detected layer 2 -- log fallback
        console.log('Note: Layer 2 enhancement unavailable, using Layer 1.');
      }
    }
  }

  // Install to ~/.claude/skills/
  if (install) {
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const skillDir = path.join(homeDir, '.claude', 'skills', skill.name);
    for (const [relPath, content] of Object.entries(skill.fileMap)) {
      const out = path.join(skillDir, relPath);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.writeFileSync(out, content, 'utf-8');
    }
    info(`Installed skill to ${skillDir}`);
    info(`${skill.endpointCount} endpoints | ${skill.tokenCount.toLocaleString()} tokens`);
    return;
  }

  // Write to output directory
  if (output) {
    const outDir = path.join(output, skill.name);
    for (const [relPath, content] of Object.entries(skill.fileMap)) {
      const out = path.join(outDir, relPath);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.writeFileSync(out, content, 'utf-8');
    }
    info(`Generated skill: ${outDir}`);
    info(`${skill.endpointCount} endpoints | ${skill.tokenCount.toLocaleString()} tokens | ${Object.keys(skill.fileMap).length} files`);
    return;
  }

  // Default: print SKILL.md to stdout
  console.log(skill.fileMap['SKILL.md']);
}

async function cmdSkillBatch(args: string[]): Promise<void> {
  let directory = '';
  let output = '';
  let layerArg: number | undefined;
  let verbose = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-o' || args[i] === '--output') { output = args[++i]; }
    else if (args[i] === '--layer') { layerArg = parseInt(args[++i], 10); }
    else if (args[i] === '-v' || args[i] === '--verbose') { verbose = true; }
    else if (!args[i].startsWith('-')) { directory = args[i]; }
  }

  if (layerArg !== undefined && (isNaN(layerArg) || (layerArg !== 1 && layerArg !== 2))) {
    error(`Invalid --layer value: ${layerArg}. Must be 1 or 2.`);
  }
  if (!directory) error('Missing directory. Usage: lapsh skill-batch <dir> -o <outdir>');
  if (!output) error('Missing output directory. Usage: lapsh skill-batch <dir> -o <outdir>');
  if (!fs.existsSync(directory) || !fs.statSync(directory).isDirectory()) {
    error(`Not a directory: ${directory}`);
  }

  const specFiles = fs.readdirSync(directory)
    .filter(f => /\.(yaml|yml|json)$/.test(f) && !f.includes('stripe-full'))
    .map(f => path.join(directory, f))
    .sort();

  if (specFiles.length === 0) error(`No spec files found in ${directory}`);

  fs.mkdirSync(output, { recursive: true });
  const layer = resolveLayer(layerArg);
  let success = 0;
  let failed = 0;

  console.log(`Generating skills for ${specFiles.length} specs`);

  for (const specFilePath of specFiles) {
    const name = path.basename(specFilePath, path.extname(specFilePath));
    try {
      const spec = compile(specFilePath);
      let skill = generateSkill(spec, { layer, lean: true });

      if (layer === 2) {
        try {
          skill = enhanceSkill(spec, skill);
        } catch (err: unknown) {
          if (verbose) {
            const msg = err instanceof Error ? err.message : String(err);
            warn(`Layer 2 failed for ${name}: ${msg}`);
          } else {
            console.log(`Note: Layer 2 enhancement unavailable for ${name}, using Layer 1.`);
          }
        }
      }

      const skillDir = path.join(output, skill.name);
      for (const [relPath, content] of Object.entries(skill.fileMap)) {
        const out = path.join(skillDir, relPath);
        fs.mkdirSync(path.dirname(out), { recursive: true });
        fs.writeFileSync(out, content, 'utf-8');
      }
      success++;
      console.log(`  ${name} -> ${skill.name} (${skill.tokenCount.toLocaleString()} tokens)`);
    } catch (err: unknown) {
      failed++;
      const msg = err instanceof Error ? err.message : String(err);
      warn(`Failed ${name}: ${msg}`);
      if (verbose && err instanceof Error) {
        console.error(err.stack);
      }
    }
  }

  info(`Generated ${success} skills, ${failed} failures`);
}

async function cmdSkillInstall(args: string[]): Promise<void> {
  let name = '';
  let dir = '';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--dir') { dir = args[++i]; }
    else if (!args[i].startsWith('-')) { name = args[i]; }
  }

  if (!name) error('Missing skill name. Usage: lapsh skill-install <name> [--dir <path>]');

  console.log(`Fetching skill bundle for ${name}...`);

  let result: Record<string, unknown>;
  try {
    result = await apiRequest('GET', `/v1/apis/${encodeURIComponent(name)}/skill/bundle`);
  } catch {
    error(`Failed to fetch skill. Check that '${name}' exists and has a skill.`);
  }

  const files = (result.files || {}) as Record<string, string>;
  if (Object.keys(files).length === 0) error(`No skill files found for '${name}'.`);

  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const installDir = dir || path.join(homeDir, '.claude', 'skills', name);

  for (const [relPath, content] of Object.entries(files)) {
    const out = path.join(installDir, relPath);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, content, 'utf-8');
  }

  info(`Installed ${Object.keys(files).length} files to ${installDir}`);
}

// ── Main ────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === '--help' || command === '-h') usage();

  try {
    switch (command) {
      case 'login': {
        const nameIdx = args.indexOf('--name');
        const loginTokenName = nameIdx !== -1 && args[nameIdx + 1] ? args[nameIdx + 1] : undefined;
        await cmdLogin(loginTokenName);
        break;
      }
      case 'logout':
        await cmdLogout();
        break;
      case 'whoami':
        await cmdWhoami();
        break;
      case 'publish':
        await cmdPublish(args.slice(1));
        break;
      case 'compile':
        await cmdCompile(args.slice(1));
        break;
      case 'skill':
        await cmdSkill(args.slice(1));
        break;
      case 'skill-batch':
        await cmdSkillBatch(args.slice(1));
        break;
      case 'skill-install':
        await cmdSkillInstall(args.slice(1));
        break;
      default:
        console.error(`Unknown command: ${command}`);
        usage();
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    error(msg);
  }
}

main();
