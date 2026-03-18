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
 *   lapsh init                            # Set up LAP in your IDE
 *   lapsh skill-install <name>            # Install skill from registry
 *   lapsh check [--silent-if-clean]       # Check for skill updates
 *   lapsh pin <name>                      # Pin a skill (skip update checks)
 *   lapsh unpin <name>                    # Unpin a skill (resume update checks)
 *   lapsh diff <skill>                    # Diff installed vs registry spec
 *   lapsh diff <old.lap> <new.lap>        # Diff two local LAP files
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as crypto from 'crypto';
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
import pkg from '../package.json';
import { generateSkill, VALID_TARGETS, detectTarget } from './skill';
import type { SkillTarget } from './skill';
import { enhanceSkill, hasClaudeCli } from './skill_llm';
import { compile } from './compilers/index';
import { LAPClient } from './client';

const BUILTIN_TARGET_DIRS: Record<SkillTarget, string> = {
  claude: 'lap',
  cursor: 'cursor',
};

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

function resolveSkillsDir(): string | null {
  // Development: skills live at <repo>/lap/skills/ (dist/src/cli.js -> 4 levels up + lap/skills)
  const devDir = path.resolve(__dirname, '..', '..', '..', '..', 'lap', 'skills');
  if (fs.existsSync(devDir)) return devDir;
  // Installed npm package: skills/ next to dist/
  const pkgDir = path.resolve(__dirname, '..', '..', 'skills');
  if (fs.existsSync(pkgDir)) return pkgDir;
  return null;
}

function copyDirRecursive(src: string, dest: string): void {
  fs.cpSync(src, dest, { recursive: true });
}

function parseTargetArg(args: string[], i: number): SkillTarget | undefined {
  const val = args[i + 1];
  if (!(VALID_TARGETS as readonly string[]).includes(val)) {
    error(`Invalid --target value: ${val}. Must be one of: ${VALID_TARGETS.join(', ')}`);
  }
  return val as SkillTarget;
}

function resolveInstallDir(target: SkillTarget, skillName: string, customDir?: string): string {
  if (customDir) return customDir;
  const homeDir = process.env.HOME || process.env.USERPROFILE;
  if (!homeDir) error('Cannot determine home directory.');
  if (target === 'cursor') {
    return path.join(homeDir, '.cursor', 'rules', skillName);
  }
  return path.join(homeDir, '.claude', 'skills', skillName);
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
  skill <spec> [-o dir] [--layer 1|2]   Generate an AI IDE skill
    [--full-spec] [--install]           Include full spec / install to target IDE dir
    [--target claude|cursor]            Target IDE (default: claude)
    [-f format]                         Force spec format
  skill-batch <dir> -o <outdir>         Batch generate skills
    [--layer 1|2] [--target t] [-v]    Layer, target IDE, verbose mode
  init [--target claude|cursor]          Set up LAP in your IDE
  skill-install <name> [--dir <path>]   Install skill from registry
    [--target claude|cursor]            Target IDE (default: auto-detect)
  get <name> [-o output] [--lean]        Download a LAP spec from the registry
  search <query> [--tag t] [--sort s]   Search the LAP registry for APIs
    [--limit n] [--offset n] [--json]   Pagination and JSON output
  check [--silent-if-clean] [--json]    Check installed skills for updates
    [--target claude|cursor]            Limit check to one target
  pin <name> [--target claude|cursor]   Pin a skill to skip update checks
  unpin <name> [--target claude|cursor] Unpin a skill to resume update checks
  diff <skill>                          Diff installed spec vs registry latest
  diff <old.lap> <new.lap>              Diff two local LAP files

Environment:
  LAP_REGISTRY                          Registry URL (default: https://registry.lap.sh)`);
  process.exit(0);
}

// ── Metadata Helpers ────────────────────────────────────────────────

export function metadataPath(target: SkillTarget): string {
  const home = os.homedir();
  if (target === 'cursor') return path.join(home, '.cursor', 'lap-metadata.json');
  return path.join(home, '.claude', 'lap-metadata.json');
}

export interface SkillMetadataEntry {
  registryVersion: string;
  specHash: string;
  installedAt: string;
  pinned: boolean;
}

export interface LapMetadata {
  skills: Record<string, SkillMetadataEntry>;
}

export function readMetadata(target: SkillTarget): LapMetadata {
  const p = metadataPath(target);
  if (!fs.existsSync(p)) return { skills: {} };
  try {
    const data = JSON.parse(fs.readFileSync(p, 'utf-8'));
    if (!data || typeof data !== 'object' || !data.skills) return { skills: {} };
    return data as LapMetadata;
  } catch {
    console.error(`Warning: corrupt metadata at ${p}, resetting.`);
    return { skills: {} };
  }
}

export function writeMetadata(target: SkillTarget, data: LapMetadata): void {
  const p = metadataPath(target);
  try { if (fs.lstatSync(p).isSymbolicLink()) throw new Error(`Refusing to write: ${p} is a symlink`); } catch (e: unknown) { if (e instanceof Error && e.message.includes('symlink')) throw e; /* file does not exist -- OK */ }
  const dir = path.dirname(p);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = p + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf-8');
  try {
    fs.renameSync(tmp, p);
  } catch {
    // Windows: renameSync may fail if target exists; fall back to unlink + rename
    try { fs.unlinkSync(p); } catch { /* may not exist */ }
    fs.renameSync(tmp, p);
  }
}

export function computeSpecHash(content: string): string {
  return 'sha256:' + crypto.createHash('sha256').update(content, 'utf-8').digest('hex');
}

export function isValidSkillName(name: string): boolean {
  return /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(name);
}

export function validateRegistryUrl(url: string): string {
  const localPrefixes = ['http://localhost:', 'http://localhost/', 'http://127.0.0.1:', 'http://127.0.0.1/'];
  for (const prefix of localPrefixes) {
    if (url.startsWith(prefix)) return url;
  }
  if (url === 'http://localhost' || url === 'http://127.0.0.1') return url;
  if (!url.startsWith('https://')) throw new Error(`Registry URL must use HTTPS: ${url}`);
  return url;
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
  let target: SkillTarget | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-o' || args[i] === '--output') { output = args[++i]; }
    else if (args[i] === '-f' || args[i] === '--format') { format = args[++i]; }
    else if (args[i] === '--layer') { layerArg = parseInt(args[++i], 10); }
    else if (args[i] === '--full-spec') { fullSpec = true; }
    else if (args[i] === '--install') { install = true; }
    else if (args[i] === '--target') { target = parseTargetArg(args, i); i++; }
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

  const resolvedTarget = target ?? detectTarget();
  const layer = resolveLayer(layerArg);
  let skill = generateSkill(spec, { layer, lean: !fullSpec, target: resolvedTarget });

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

  // Install to target IDE directory
  if (install) {
    const skillDir = resolveInstallDir(resolvedTarget, skill.name);
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

  // Default: print main skill file to stdout
  console.log(skill.fileMap[skill.mainFile]);
}

async function cmdSkillBatch(args: string[]): Promise<void> {
  let directory = '';
  let output = '';
  let layerArg: number | undefined;
  let verbose = false;
  let target: SkillTarget | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-o' || args[i] === '--output') { output = args[++i]; }
    else if (args[i] === '--layer') { layerArg = parseInt(args[++i], 10); }
    else if (args[i] === '-v' || args[i] === '--verbose') { verbose = true; }
    else if (args[i] === '--target') { target = parseTargetArg(args, i); i++; }
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
  const resolvedTarget = target ?? detectTarget();
  let success = 0;
  let failed = 0;

  console.log(`Generating skills for ${specFiles.length} specs`);

  for (const specFilePath of specFiles) {
    const name = path.basename(specFilePath, path.extname(specFilePath));
    try {
      const spec = compile(specFilePath);
      let skill = generateSkill(spec, { layer, lean: true, target: resolvedTarget });

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

async function cmdSearch(args: string[]): Promise<void> {
  const queryParts: string[] = [];
  let tag: string | undefined;
  let sort: string | undefined;
  let limit: number | undefined;
  let offset: number | undefined;
  let jsonOutput = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--tag' && i + 1 < args.length) { tag = args[++i]; }
    else if (args[i] === '--sort' && i + 1 < args.length) { sort = args[++i]; }
    else if (args[i] === '--limit' && i + 1 < args.length) { limit = parseInt(args[++i], 10); }
    else if (args[i] === '--offset' && i + 1 < args.length) { offset = parseInt(args[++i], 10); }
    else if (args[i] === '--json') { jsonOutput = true; }
    else if (!args[i].startsWith('-')) { queryParts.push(args[i]); }
  }

  const query = queryParts.join(' ').trim();
  if (!query) error('Please provide a search query. Usage: lapsh search <query>');

  const client = new LAPClient();
  const registryUrl = getRegistryUrl();
  const result = await client.search(registryUrl, query, { tag, sort, limit, offset });

  if (jsonOutput) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  if (result.results.length === 0) {
    info(`No results for '${query}'.`);
    return;
  }

  const rows = result.results.map(r => {
    const name = r.name || '';
    const prov = r.provider?.domain || r.provider?.display_name || '';
    const desc = r.description || '';
    const ep = typeof r.endpoints === 'number' ? `${r.endpoints} endpoints` : '';
    const size = r.size;
    const lean = r.lean_size;
    const ratio = (typeof size === 'number' && typeof lean === 'number' && lean)
      ? `${(size / lean).toFixed(1)}x compressed` : '';
    const skill = r.has_skill ? ' [skill]' : '';
    const community = r.is_community ? ' [community]' : '';
    return { name, prov, ep, ratio, desc, skill, community };
  });

  const nameW = Math.max(...rows.map(r => r.name.length));
  const provW = Math.max(...rows.map(r => r.prov.length));
  const epW = Math.max(...rows.map(r => r.ep.length));
  const ratioW = Math.max(...rows.map(r => r.ratio.length));

  for (const { name, prov, ep, ratio, desc, skill, community } of rows) {
    console.log(`  ${name.padEnd(nameW)}  ${prov.padEnd(provW)}  ${ep.padStart(epW)}  ${ratio.padStart(ratioW)}   ${desc}${skill}${community}`);
  }

  const shown = (result.offset || 0) + result.results.length;
  if (shown < result.total) {
    info(`Showing ${shown}/${result.total} results. Use --offset ${shown} for more.`);
  }
}

async function cmdGet(args: string[]): Promise<void> {
  let name = '';
  let output = '';
  let lean = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-o' || args[i] === '--output') { output = args[++i]; }
    else if (args[i] === '--lean') { lean = true; }
    else if (!args[i].startsWith('-')) { name = args[i]; }
  }

  if (!name) error('Missing API name. Usage: lapsh get <name> [-o output] [--lean]');

  const registryUrl = getRegistryUrl();
  let url = `${registryUrl}/v1/apis/${encodeURIComponent(name)}`;
  if (lean) url += '?format=lean';

  const http = await import('http');
  const https = await import('https');
  const fetcher = url.startsWith('https') ? https : http;

  const body = await new Promise<string>((resolve, reject) => {
    const req = fetcher.get(url, { headers: { 'Accept': 'text/lap', 'User-Agent': `lapsh/${pkg.version}` } }, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        reject(new Error(`HTTP ${res.statusCode} fetching '${name}'`));
        res.resume();
        return;
      }
      const chunks: Buffer[] = [];
      res.on('data', (chunk: Buffer) => chunks.push(chunk));
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    });
    req.on('error', reject);
  });

  if (output) {
    const dir = path.dirname(output);
    if (dir) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(output, body, 'utf-8');
    info(`Saved ${name} to ${output}`);
  } else {
    console.log(body);
  }
}

async function cmdInit(args: string[]): Promise<void> {
  let target: SkillTarget | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--target') { target = parseTargetArg(args, i); i++; }
  }

  const resolvedTarget = target ?? 'claude';

  const skillsDir = resolveSkillsDir();
  if (!skillsDir) error('Built-in skill files not found. Reinstall the package.');

  const srcSubdir = BUILTIN_TARGET_DIRS[resolvedTarget] || 'lap';
  const src = path.join(skillsDir, srcSubdir);
  if (!fs.existsSync(src)) error(`No built-in skill for target '${resolvedTarget}'.`);

  const installDir = resolveInstallDir(resolvedTarget, 'lap');

  copyDirRecursive(src, installDir);
  info(`Installed skill to ${installDir}`);

  // NOTE: Hook auto-registration removed. Users should configure hooks manually.
  // See registerClaudeHook / registerCursorHook if needed in the future.
}

export function registerClaudeHook(command: string): void {
  const configPath = path.join(os.homedir(), '.claude', 'settings.json');
  let config: any = {};

  if (fs.existsSync(configPath)) {
    try {
      config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    } catch { /* start fresh */ }
  }

  if (typeof config !== 'object' || config === null) config = {};

  if (!config.hooks) config.hooks = {};
  if (!config.hooks.SessionStart) config.hooks.SessionStart = [];

  // Idempotent: check if already registered
  const exists = config.hooks.SessionStart.some(
    (h: any) => typeof h === 'object' && h.command && h.command.includes('lapsh check')
  );
  if (exists) {
    console.log('Session hook already registered.');
    return;
  }

  config.hooks.SessionStart.push({ command });

  const dir = path.dirname(configPath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const tmp = configPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(config, null, 2), 'utf-8');
  try { fs.renameSync(tmp, configPath); } catch { try { fs.unlinkSync(configPath); } catch {} fs.renameSync(tmp, configPath); }
  console.log('Registered session-start hook for update checking.');
}

export function registerCursorHook(command: string): void {
  const configPath = path.join(os.homedir(), '.cursor', 'hooks.json');
  let config: any = {};

  if (fs.existsSync(configPath)) {
    try {
      config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    } catch { /* start fresh */ }
  }

  if (typeof config !== 'object' || config === null) config = {};

  if (!config.version) config.version = 1;
  if (!config.hooks) config.hooks = {};
  if (!config.hooks.sessionStart) config.hooks.sessionStart = [];

  const exists = config.hooks.sessionStart.some(
    (h: any) => typeof h === 'object' && h.command && h.command.includes('lapsh check')
  );
  if (exists) {
    console.log('Session hook already registered.');
    return;
  }

  config.hooks.sessionStart.push({ command, timeout: 10 });

  const dir = path.dirname(configPath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const tmp = configPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(config, null, 2), 'utf-8');
  try { fs.renameSync(tmp, configPath); } catch { try { fs.unlinkSync(configPath); } catch {} fs.renameSync(tmp, configPath); }
  console.log('Registered session-start hook for update checking.');
}

async function cmdSkillInstall(args: string[]): Promise<void> {
  let name = '';
  let dir = '';
  let target: SkillTarget | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--dir') { dir = args[++i]; }
    else if (args[i] === '--target') { target = parseTargetArg(args, i); i++; }
    else if (!args[i].startsWith('-')) { name = args[i]; }
  }

  if (!name) error('Missing skill name. Usage: lapsh skill-install <name> [--dir <path>] [--target t]');
  if (!isValidSkillName(name)) error(`Invalid skill name: ${name}`);

  const resolvedTarget = target ?? detectTarget();

  console.log(`Fetching spec for ${name} (target: ${resolvedTarget})...`);

  // Fetch LAP spec from registry
  const registryUrl = getRegistryUrl();
  validateRegistryUrl(registryUrl);
  const http = await import('http');
  const https = await import('https');
  const url = `${registryUrl}/v1/apis/${encodeURIComponent(name)}`;
  const fetcher = url.startsWith('https') ? https : http;

  const specText = await new Promise<string>((resolve, reject) => {
    const req = fetcher.get(url, { headers: { 'Accept': 'text/lap', 'User-Agent': 'lapsh' } }, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        reject(new Error(`HTTP ${res.statusCode} fetching '${name}'`));
        res.resume();
        return;
      }
      const chunks: Buffer[] = [];
      res.on('data', (chunk: Buffer) => chunks.push(chunk));
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    });
    req.on('error', reject);
  }).catch(() => {
    error(`Failed to fetch spec for '${name}' from ${registryUrl}.`);
  });

  if (!specText || !specText.trim()) error(`No spec found for '${name}'.`);

  // Parse and generate skill with target
  const spec = parse(specText);
  const skill = generateSkill(spec, { target: resolvedTarget });

  // Determine install directory
  const installDir = resolveInstallDir(resolvedTarget, skill.name, dir || undefined);

  for (const [relPath, content] of Object.entries(skill.fileMap)) {
    const out = path.join(installDir, relPath);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, content, 'utf-8');
  }

  info(`Installed ${Object.keys(skill.fileMap).length} files to ${installDir} (${skill.tokenCount.toLocaleString()} tokens)`);

  // Write metadata
  try {
    const specHash = computeSpecHash(specText);

    // Fetch version from registry JSON endpoint
    let registryVersion = 'unknown';
    try {
      const jsonUrl = `${registryUrl}/v1/apis/${encodeURIComponent(name)}`;
      const jsonFetcher = jsonUrl.startsWith('https') ? https : http;
      const jsonBody = await new Promise<string>((resolve, reject) => {
        const req = jsonFetcher.get(jsonUrl, { headers: { 'Accept': 'application/json', 'User-Agent': 'lapsh' } }, (res) => {
          if (res.statusCode && res.statusCode >= 400) { reject(new Error(`HTTP ${res.statusCode}`)); res.resume(); return; }
          const chunks: Buffer[] = [];
          res.on('data', (chunk: Buffer) => chunks.push(chunk));
          res.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
        });
        req.on('error', reject);
      });
      const apiInfo = JSON.parse(jsonBody);
      registryVersion = apiInfo.version || 'unknown';
    } catch { /* best effort */ }

    const meta = readMetadata(resolvedTarget);
    meta.skills[name] = {
      registryVersion,
      specHash,
      installedAt: new Date().toISOString(),
      pinned: false,
    };
    writeMetadata(resolvedTarget, meta);
  } catch (e) {
    console.error(`Warning: could not write metadata: ${e}`);
  }
}

// ── Check / Pin / Unpin Commands ────────────────────────────────────

async function cmdCheck(args: string[]): Promise<void> {
  let silentIfClean = false;
  let jsonOutput = false;
  let targetArg = 'auto';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--silent-if-clean') silentIfClean = true;
    else if (args[i] === '--json') jsonOutput = true;
    else if (args[i] === '--target') targetArg = args[++i];
  }

  const targets: SkillTarget[] = [];
  if (targetArg && targetArg !== 'auto') {
    if (!(VALID_TARGETS as readonly string[]).includes(targetArg)) {
      error(`Invalid --target value: ${targetArg}. Must be one of: ${VALID_TARGETS.join(', ')}`);
    }
    targets.push(targetArg as SkillTarget);
  } else {
    for (const t of VALID_TARGETS) {
      if (fs.existsSync(metadataPath(t))) targets.push(t);
    }
  }

  if (!targets.length) {
    if (!silentIfClean) console.log('No LAP metadata found. Install skills first with: lapsh skill-install <name>');
    return;
  }

  const skillsToCheck: { name: string; version: string }[] = [];
  const skillTargets: Record<string, SkillTarget> = {};

  for (const t of targets) {
    const meta = readMetadata(t);
    for (const [name, info] of Object.entries(meta.skills)) {
      if (info.pinned) continue;
      skillsToCheck.push({ name, version: info.registryVersion || '' });
      skillTargets[name] = t;
    }
  }

  if (!skillsToCheck.length) {
    if (!silentIfClean) console.log('All skills are up to date (or pinned).');
    return;
  }

  let registryUrl: string;
  try {
    registryUrl = getRegistryUrl();
    validateRegistryUrl(registryUrl);
  } catch (e: unknown) {
    if (!silentIfClean) console.error(`Error: ${e instanceof Error ? e.message : String(e)}`);
    return;
  }

  let result: { results?: { name: string; has_update: boolean; installed_version: string; latest_version: string }[] };
  try {
    const httpMod = await import('http');
    const httpsMod = await import('https');
    const checkUrl = `${registryUrl}/v1/skills/check`;
    const checkFetcher = checkUrl.startsWith('https') ? httpsMod : httpMod;
    const payload = JSON.stringify({ skills: skillsToCheck });
    const parsedUrl = new URL(checkUrl);
    const checkBody = await new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => { req.destroy(); reject(new Error('timeout')); }, 10000);
      const req = checkFetcher.request({
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
        path: parsedUrl.pathname,
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'User-Agent': 'lapsh', 'Content-Length': Buffer.byteLength(payload) },
      }, (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => { clearTimeout(timer); resolve(Buffer.concat(chunks).toString('utf-8')); });
      });
      req.on('error', (e) => { clearTimeout(timer); reject(e); });
      req.write(payload);
      req.end();
    });
    result = JSON.parse(checkBody) as typeof result;
  } catch {
    if (silentIfClean) return;
    console.error('Warning: Could not reach LAP registry for update check.');
    return;
  }

  const updates = (result.results || []).filter((r) => r.has_update);

  if (!updates.length) {
    if (jsonOutput) console.log(JSON.stringify({ updates: [] }, null, 2));
    else if (!silentIfClean) console.log('All skills are up to date.');
    return;
  }

  if (jsonOutput) {
    console.log(JSON.stringify({ updates }, null, 2));
    return;
  }

  if (updates.length === 1) {
    const u = updates[0];
    console.log('LAP skill update available:');
    console.log(`  ${u.name}: ${u.installed_version} -> ${u.latest_version}`);
    console.log();
    console.log(`  Update:  lapsh skill-install ${u.name}`);
    console.log(`  Changes: lapsh diff ${u.name}`);
    console.log(`  Pin:     lapsh pin ${u.name}`);
  } else {
    console.log(`${updates.length} LAP skills have updates:`);
    const names: string[] = [];
    for (const u of updates) {
      names.push(u.name);
      console.log(`  ${u.name.padEnd(20)} ${u.installed_version} -> ${u.latest_version}`);
    }
    console.log();
    console.log(`  Update all: lapsh skill-install ${names.join(' ')}`);
    console.log(`  See changes: lapsh diff <skill>`);
    console.log(`  Pin a skill: lapsh pin <skill>`);
  }
}

async function cmdSetPinned(args: string[], pinned: boolean): Promise<void> {
  let name = '';
  let target: string | undefined;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--target') target = args[++i];
    else if (!args[i].startsWith('-')) name = args[i];
  }
  const verb = pinned ? 'pin' : 'unpin';
  if (!name) error(`Missing skill name. Usage: lapsh ${verb} <skill>`);
  if (!isValidSkillName(name)) error(`Invalid skill name: ${name}`);
  if (target && !(VALID_TARGETS as readonly string[]).includes(target)) {
    error(`Invalid --target value: ${target}. Must be one of: ${VALID_TARGETS.join(', ')}`);
  }
  const resolvedTarget = (target as SkillTarget) ?? detectTarget();
  const meta = readMetadata(resolvedTarget);
  if (!meta.skills[name]) error(`Skill '${name}' is not installed. Install it first: lapsh skill-install ${name}`);
  meta.skills[name].pinned = pinned;
  writeMetadata(resolvedTarget, meta);
  const msg = pinned ? 'skipped during update checks' : 'included in update checks';
  console.log(`${pinned ? 'Pinned' : 'Unpinned'} '${name}'. It will be ${msg}.`);
}

// ── Diff Command ────────────────────────────────────────────────────

export function printSpecDiff(oldSpec: any, newSpec: any, oldLabel: string, newLabel: string): void {
  const oldEndpoints = new Set((oldSpec.endpoints || []).map((e: any) => `${e.method.toUpperCase()} ${e.path}`));
  const newEndpoints = new Set((newSpec.endpoints || []).map((e: any) => `${e.method.toUpperCase()} ${e.path}`));

  const added = [...newEndpoints].filter(e => !oldEndpoints.has(e));
  const removed = [...oldEndpoints].filter(e => !newEndpoints.has(e));

  if (added.length) {
    console.log(`  Added (${added.length}):`);
    for (const ep of added) console.log(`    + ${ep}`);
  }

  if (removed.length) {
    console.log(`  Removed (${removed.length}):`);
    for (const ep of removed) console.log(`    - ${ep}`);
  }

  if (!added.length && !removed.length) {
    console.log('  No endpoint differences found.');
  }

  // Token impact
  const oldTokens = Math.ceil(JSON.stringify(oldSpec).length / 4);
  const newTokens = Math.ceil(JSON.stringify(newSpec).length / 4);
  const delta = newTokens - oldTokens;
  const pct = oldTokens ? ((delta / oldTokens) * 100) : 0;
  const sign = delta >= 0 ? '+' : '';
  console.log(`\n  Token impact: ${oldTokens.toLocaleString()} -> ${newTokens.toLocaleString()} tokens (${sign}${pct.toFixed(0)}%)`);
}

async function diffSkill(name: string): Promise<void> {
  if (!isValidSkillName(name)) error(`Invalid skill name: ${name}`);

  const target = detectTarget();
  const home = os.homedir();

  // Find installed spec
  let specFile = '';
  for (const t of VALID_TARGETS) {
    const dir = t === 'cursor'
      ? path.join(home, '.cursor', 'rules', name)
      : path.join(home, '.claude', 'skills', name);
    const candidate = path.join(dir, 'references', 'api-spec.lap');
    if (fs.existsSync(candidate)) {
      specFile = candidate;
      break;
    }
  }

  if (!specFile) error(`No installed spec found for '${name}'. Install it first: lapsh skill-install ${name}`);

  const oldText = fs.readFileSync(specFile, 'utf-8');

  // Fetch latest from registry
  const registryUrl = getRegistryUrl();
  validateRegistryUrl(registryUrl);
  let newText: string;
  try {
    const httpMod = await import('http');
    const httpsMod = await import('https');
    const diffUrl = `${registryUrl}/v1/apis/${encodeURIComponent(name)}`;
    const diffFetcher = diffUrl.startsWith('https') ? httpsMod : httpMod;
    newText = await new Promise<string>((resolve, reject) => {
      const req = diffFetcher.get(diffUrl, { headers: { 'Accept': 'text/lap', 'User-Agent': 'lapsh' } }, (res) => {
        if (res.statusCode && res.statusCode >= 400) { reject(new Error(`HTTP ${res.statusCode}`)); res.resume(); return; }
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
      });
      req.on('error', reject);
    });
  } catch {
    error(`Failed to fetch latest spec for '${name}' from registry.`);
    return; // unreachable but helps TS
  }

  const oldSpec = parse(oldText);
  const newSpec = parse(newText);

  // Get version info from metadata
  const meta = readMetadata(target);
  const oldVersion = meta.skills[name]?.registryVersion || 'installed';

  console.log(`${name}: ${oldVersion} -> latest\n`);
  printSpecDiff(oldSpec, newSpec, `installed (${oldVersion})`, 'registry (latest)');
}

async function cmdDiff(args: string[]): Promise<void> {
  let firstArg = '';
  let secondArg = '';

  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('-')) continue;
    if (!firstArg) firstArg = args[i];
    else secondArg = args[i];
  }

  if (!firstArg) error('Usage: lapsh diff <skill> or lapsh diff old.lap new.lap');

  // Smart detection: single arg, no file extension, no path separators = skill name
  if (!secondArg) {
    if (firstArg.endsWith('.lap') || firstArg.includes('/') || firstArg.includes('\\')) {
      error('Need two files to diff. Usage: lapsh diff old.lap new.lap');
    }
    await diffSkill(firstArg);
    return;
  }

  // Two-file diff
  if (!fs.existsSync(firstArg)) error(`File not found: ${firstArg}`);
  if (!fs.existsSync(secondArg)) error(`File not found: ${secondArg}`);

  const oldSpec = parse(fs.readFileSync(firstArg, 'utf-8'));
  const newSpec = parse(fs.readFileSync(secondArg, 'utf-8'));

  printSpecDiff(oldSpec, newSpec, firstArg, secondArg);
}

// ── Main ────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === '--help' || command === '-h') usage();
  if (command === '--version' || command === '-v') {
    console.log(`lapsh ${pkg.version}`);
    process.exit(0);
  }

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
      case 'init':
        await cmdInit(args.slice(1));
        break;
      case 'skill-install':
        await cmdSkillInstall(args.slice(1));
        break;
      case 'get':
        await cmdGet(args.slice(1));
        break;
      case 'search':
        await cmdSearch(args.slice(1));
        break;
      case 'check':
        await cmdCheck(args.slice(1));
        break;
      case 'pin':
        await cmdSetPinned(args.slice(1), true);
        break;
      case 'unpin':
        await cmdSetPinned(args.slice(1), false);
        break;
      case 'diff':
        await cmdDiff(args.slice(1));
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

if (require.main === module) {
  main();
}
