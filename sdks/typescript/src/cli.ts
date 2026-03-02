#!/usr/bin/env node
/**
 * LAP CLI (Node.js) -- authenticate with the LAP registry and publish specs.
 *
 * Usage:
 *   lap-js login                           # Browser OAuth, store token
 *   lap-js logout                          # Revoke + delete local creds
 *   lap-js whoami                          # Show current user
 *   lap-js publish <spec> --provider <p>   # Compile + publish spec
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

// ── Helpers ─────────────────────────────────────────────────────────

function info(msg: string): void {
  console.log(`\x1b[32m✓\x1b[0m ${msg}`);
}

function error(msg: string): never {
  console.error(`\x1b[31m✗\x1b[0m ${msg}`);
  process.exit(1);
}

function usage(): never {
  console.log(`LAP CLI (Node.js)

Commands:
  login [--name <token-name>]        Authenticate with the LAP registry via GitHub
  logout                             Log out and revoke API token
  whoami                             Show current authenticated user
  publish <spec> --provider <slug>   Compile and publish a spec to the registry
    [--name <name>]                  Override spec name
    [--source-url <url>]             Upstream spec URL

Environment:
  LAP_REGISTRY                       Registry URL (default: https://registry.lap.sh)`);
  process.exit(0);
}

// ── Commands ────────────────────────────────────────────────────────

async function cmdLogin(tokenName?: string): Promise<void> {
  const creds = loadCredentials();
  if (creds) {
    info(`Already logged in as ${creds.username}. Run 'lap-js logout' first to switch accounts.`);
    return;
  }

  console.log(`Authenticating with ${getRegistryUrl()}...`);

  const body = tokenName ? { name: tokenName } : undefined;
  const result = await apiRequest('POST', '/auth/cli/session', body);
  const sessionId = result.session_id as string;
  const authUrl = result.auth_url as string;

  console.log('Opening browser for GitHub authorization...');
  openBrowser(authUrl);
  console.log('Waiting for authentication (press Ctrl+C to cancel)...');

  const { token, username } = await pollSseStream(sessionId);
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
    console.log("Not logged in. Run 'lap-js login' to authenticate.");
    return;
  }

  const result = await apiRequest('GET', '/auth/me', undefined, token);
  const user = (result.user || {}) as Record<string, unknown>;
  info(`Logged in as ${user.username || 'unknown'}`);
}

async function cmdPublish(args: string[]): Promise<void> {
  const token = getToken();
  if (!token) {
    error("Not logged in. Run 'lap-js login' first.");
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

  if (!specPath) error('Missing spec file path. Usage: lap-js publish <spec> --provider <slug>');
  if (!provider) error('Missing --provider flag. Usage: lap-js publish <spec> --provider <slug>');
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
    token
  );

  info(`Published ${name} v${result.version || '?'} (provider: ${result.provider || provider})`);
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
