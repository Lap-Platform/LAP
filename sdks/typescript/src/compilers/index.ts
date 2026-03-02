import * as fs from 'fs';
import * as path from 'path';
import { LAPSpec } from '../parser';

/**
 * Auto-detect API spec format from file extension and content.
 * Returns one of: openapi, graphql, asyncapi, protobuf, postman, smithy.
 * Throws if the format cannot be determined.
 */
export function detectFormat(specPath: string): string {
  const ext = path.extname(specPath).toLowerCase();

  // Extension-based detection
  if (ext === '.graphql' || ext === '.gql') return 'graphql';
  if (ext === '.proto') return 'protobuf';
  if (ext === '.smithy') return 'smithy';

  // Directory: look for .proto files
  if (fs.existsSync(specPath) && fs.statSync(specPath).isDirectory()) {
    const entries = fs.readdirSync(specPath);
    if (entries.some((f) => f.endsWith('.proto'))) return 'protobuf';
    if (entries.some((f) => f === 'smithy-build.json')) return 'smithy';
    throw new Error(
      `Directory '${specPath}' has no recognized spec files. Use the format option to specify the format.`,
    );
  }

  // Content-based detection for YAML/JSON
  if (ext === '.yaml' || ext === '.yml' || ext === '.json') {
    const text = fs.readFileSync(specPath, 'utf-8');
    let data: Record<string, unknown>;

    try {
      if (ext === '.json') {
        data = JSON.parse(text) as Record<string, unknown>;
      } else {
        // Dynamic import to avoid loading yaml for non-YAML files
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const yaml = require('js-yaml') as typeof import('js-yaml');
        data = yaml.load(text) as Record<string, unknown>;
      }
    } catch {
      throw new Error(
        `Cannot parse '${specPath}' as ${ext === '.json' ? 'JSON' : 'YAML'}. Use the format option to specify the format.`,
      );
    }

    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error(
        `Expected a mapping in '${specPath}'. Use the format option to specify the format.`,
      );
    }

    // Smithy JSON AST
    if ('smithy' in data && 'shapes' in data) return 'smithy';

    // AsyncAPI
    if ('asyncapi' in data) return 'asyncapi';

    // OpenAPI / Swagger
    if ('openapi' in data || 'swagger' in data) return 'openapi';

    // Postman Collection (top-level)
    const info = data['info'];
    if (info && typeof info === 'object' && !Array.isArray(info)) {
      const infoObj = info as Record<string, unknown>;
      if (infoObj['_postman_id']) return 'postman';
      const schema = infoObj['schema'];
      if (typeof schema === 'string' && schema.toLowerCase().includes('postman')) return 'postman';
    }

    // Wrapped Postman: {"collection": {...}}
    const coll = data['collection'];
    if (coll && typeof coll === 'object' && !Array.isArray(coll)) {
      const collInfo = (coll as Record<string, unknown>)['info'];
      if (collInfo && typeof collInfo === 'object') {
        const schema = (collInfo as Record<string, unknown>)['schema'];
        if (typeof schema === 'string' && schema.toLowerCase().includes('postman')) return 'postman';
      }
    }

    // GraphQL introspection JSON
    if ('__schema' in data) return 'graphql';
    const inner = data['data'];
    if (inner && typeof inner === 'object' && '__schema' in (inner as Record<string, unknown>)) {
      return 'graphql';
    }

    throw new Error(
      `Cannot detect format of '${specPath}'. Use the format option to specify (openapi, graphql, asyncapi, protobuf, postman, smithy).`,
    );
  }

  throw new Error(
    `Unsupported file extension '${ext}' for '${specPath}'. Use the format option to specify (openapi, graphql, asyncapi, protobuf, postman, smithy).`,
  );
}

/**
 * Compile an API spec to a LAPSpec object.
 *
 * @param specPath - Path to the spec file or directory.
 * @param options.format - One of: openapi, graphql, asyncapi, protobuf, postman, smithy.
 *                         Auto-detected from file extension/content when omitted.
 */
export function compile(specPath: string, options?: { format?: string }): LAPSpec {
  const format = options?.format ?? detectFormat(specPath);

  if (format === 'openapi') {
    const { compileOpenapi } = require('./openapi') as typeof import('./openapi');
    return compileOpenapi(specPath);
  }

  throw new Error(
    `Format '${format}' is not yet supported in the TypeScript SDK. Use the Python CLI instead.`,
  );
}
