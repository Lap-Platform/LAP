/**
 * Smithy JSON AST compiler for LAP format -- port of smithy.py (663 lines).
 *
 * Compiles Smithy JSON AST (and optionally .smithy IDL via Smithy CLI) into LAP format.
 * Focuses on HTTP-bound operations (operations with @http trait).
 *
 * Smithy -> LAP mapping:
 * - Service -> LAPSpec (apiName, version, auth)
 * - Operation -> Endpoint (method, path from @http trait)
 * - Operation input -> requiredParams, optionalParams, requestBody (based on HTTP binding traits)
 * - Operation output -> responses
 * - Operation errors -> errors
 * - @httpLabel -> requiredParams (path parameters)
 * - @httpQuery -> optionalParams or requiredParams (based on @required trait)
 * - @httpHeader -> optionalParams or requiredParams
 * - @httpPayload -> requestBody
 * - Unbound members -> requestBody (JSON body)
 */

import * as fs from 'fs';
import * as childProcess from 'child_process';
import {
  LAPSpec,
  Endpoint,
  Param,
  ResponseSchema,
  ResponseField,
  ErrorSchema,
} from '../parser';

// ── HTML stripping ──────────────────────────────────────────────────────────

function stripHtml(text: string): string {
  return text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/<[^>]+>/g, '');
}

// ── Smithy scalar types -> LAP types ────────────────────────────────────────

const SMITHY_SCALAR_MAP: Record<string, string> = {
  'smithy.api#String': 'str',
  'smithy.api#Integer': 'int',
  'smithy.api#Long': 'int(i64)',
  'smithy.api#Short': 'int',
  'smithy.api#Byte': 'int',
  'smithy.api#Boolean': 'bool',
  'smithy.api#Float': 'num(f32)',
  'smithy.api#Double': 'num(f64)',
  'smithy.api#BigInteger': 'int(big)',
  'smithy.api#BigDecimal': 'num(big)',
  'smithy.api#Timestamp': 'str(timestamp)',
  'smithy.api#Blob': 'bytes',
  'smithy.api#Document': 'any',
};

// ── Smithy auth traits -> LAP auth strings ──────────────────────────────────

const AUTH_TRAIT_MAP: Record<string, string> = {
  'smithy.api#httpBasicAuth': 'HTTP Basic',
  'smithy.api#httpBearerAuth': 'Bearer token',
  'smithy.api#httpApiKeyAuth': 'ApiKey',
  'aws.auth#sigv4': 'AWS SigV4',
  'aws.auth#sigv4a': 'AWS SigV4',
};

// ── Types for Smithy JSON AST structures ────────────────────────────────────

interface SmithyShape {
  type?: string;
  version?: string;
  members?: Record<string, SmithyMember>;
  member?: SmithyTargetRef;
  key?: SmithyTargetRef;
  value?: SmithyTargetRef;
  operations?: SmithyTargetRef[];
  input?: SmithyTargetRef;
  output?: SmithyTargetRef;
  errors?: SmithyTargetRef[];
  traits?: Record<string, unknown>;
}

interface SmithyMember {
  target: string;
  traits?: Record<string, unknown>;
}

interface SmithyTargetRef {
  target: string;
}

// ── Main entry point ────────────────────────────────────────────────────────

/**
 * Compile a Smithy spec file into a LAPSpec.
 *
 * Accepts:
 * - .json files (Smithy JSON AST) -- parse directly
 * - .smithy files (Smithy IDL) -- convert via Smithy CLI then parse JSON AST
 */
export function compileSmithySpec(specPath: string): LAPSpec {
  let jsonAst: Record<string, unknown>;

  if (specPath.endsWith('.smithy')) {
    jsonAst = smithyIdlToJson(specPath);
  } else if (specPath.endsWith('.json')) {
    jsonAst = loadJsonAst(specPath);
  } else {
    throw new Error(`Unsupported file type: expected .json or .smithy, got '${specPath}'`);
  }

  const shapes = (jsonAst['shapes'] as Record<string, SmithyShape>) ?? {};

  // Find service shape
  const [serviceId, serviceShape] = findService(shapes);

  // Extract service metadata
  const apiName = serviceId.includes('#') ? serviceId.split('#')[1] : serviceId;
  const metadata = extractServiceMetadata(serviceShape);
  const auth = extractAuthScheme(serviceShape, shapes);

  // Convert operations to endpoints
  const endpoints: Endpoint[] = [];
  const operations = serviceShape.operations ?? [];
  for (const opRef of operations) {
    const opId = opRef.target;
    if (opId in shapes) {
      const endpoint = operationToEndpoint(opId, shapes[opId], shapes);
      if (endpoint) {
        endpoints.push(endpoint);
      }
    }
  }

  return {
    version: 'v0.3',
    apiName,
    baseUrl: '',
    apiVersion: metadata.version ?? '',
    auth,
    endpoints,
    getEndpoint(method: string, path: string) {
      return this.endpoints.find((e) => e.method === method && e.path === path);
    },
  };
}

// ── Load and validate ───────────────────────────────────────────────────────

function loadJsonAst(specPath: string): Record<string, unknown> {
  let text: string;
  try {
    text = fs.readFileSync(specPath, 'utf-8');
  } catch {
    throw new Error(`Could not read file: ${specPath}`);
  }

  let jsonAst: Record<string, unknown>;
  try {
    jsonAst = JSON.parse(text) as Record<string, unknown>;
  } catch (e) {
    throw new Error(`Invalid JSON in ${specPath}: ${e}`);
  }

  if (!('smithy' in jsonAst)) {
    throw new Error("Not a valid Smithy JSON AST: missing 'smithy' version field");
  }
  if (!('shapes' in jsonAst)) {
    throw new Error("Not a valid Smithy JSON AST: missing 'shapes' field");
  }

  return jsonAst;
}

function smithyIdlToJson(smithyPath: string): Record<string, unknown> {
  let result: string;
  try {
    // Use execFileSync instead of execSync to avoid shell injection.
    // execFileSync passes arguments directly to the process without a shell,
    // so crafted file paths cannot escape into shell commands.
    result = childProcess.execFileSync('smithy', ['ast', smithyPath], {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
  } catch (e: unknown) {
    const err = e as { status?: number; stderr?: string; message?: string };
    if (err.message && err.message.includes('ENOENT')) {
      throw new Error(
        'Smithy CLI not found. To compile .smithy files, install Smithy CLI:\n' +
          'https://smithy.io/2.0/guides/smithy-cli.html\n\n' +
          'Alternatively, provide a JSON AST file (.json) directly.',
      );
    }
    throw new Error(`Smithy CLI failed: ${err.stderr ?? err.message ?? 'unknown error'}`);
  }

  let jsonAst: Record<string, unknown>;
  try {
    jsonAst = JSON.parse(result) as Record<string, unknown>;
  } catch (e) {
    throw new Error(`Smithy CLI produced invalid JSON: ${e}`);
  }

  return jsonAst;
}

// ── Service & metadata extraction ───────────────────────────────────────────

function findService(shapes: Record<string, SmithyShape>): [string, SmithyShape] {
  for (const [shapeId, shapeDef] of Object.entries(shapes)) {
    if (shapeDef.type === 'service') {
      return [shapeId, shapeDef];
    }
  }
  throw new Error('No service found in Smithy model');
}

function extractServiceMetadata(
  serviceShape: SmithyShape,
): { version?: string; description?: string } {
  const metadata: { version?: string; description?: string } = {};

  if (serviceShape.version) {
    metadata.version = serviceShape.version;
  }

  const traits = serviceShape.traits ?? {};
  if ('smithy.api#documentation' in traits) {
    metadata.description = stripHtml(String(traits['smithy.api#documentation']));
  } else if ('smithy.api#title' in traits) {
    metadata.description = stripHtml(String(traits['smithy.api#title']));
  }

  return metadata;
}

function extractAuthScheme(
  serviceShape: SmithyShape,
  _shapes: Record<string, SmithyShape>,
): string {
  const traits = serviceShape.traits ?? {};
  const authSchemes: string[] = [];

  for (const traitId of Object.keys(traits)) {
    if (traitId in AUTH_TRAIT_MAP) {
      authSchemes.push(AUTH_TRAIT_MAP[traitId]);
    } else if (traitId === 'smithy.api#auth') {
      const authRefs = traits[traitId];
      if (Array.isArray(authRefs)) {
        for (const authRef of authRefs) {
          const authId =
            typeof authRef === 'object' && authRef !== null && 'target' in authRef
              ? (authRef as { target: string }).target
              : String(authRef);
          if (authId in AUTH_TRAIT_MAP) {
            authSchemes.push(AUTH_TRAIT_MAP[authId]);
          }
        }
      }
    }
  }

  return authSchemes.length > 0 ? authSchemes.join(' | ') : '';
}

// ── Type resolution ─────────────────────────────────────────────────────────

function smithyTypeToLap(
  shapeId: string,
  shapes: Record<string, SmithyShape>,
  visited?: Set<string>,
): string {
  if (!visited) visited = new Set();

  // Cycle detection
  if (visited.has(shapeId)) return 'any';

  // Check scalar map first
  if (shapeId in SMITHY_SCALAR_MAP) return SMITHY_SCALAR_MAP[shapeId];

  // Resolve shape definition
  if (!(shapeId in shapes)) return 'any';

  const shapeDef = shapes[shapeId];
  const shapeType = shapeDef.type;

  const visitedCopy = new Set(visited);
  visitedCopy.add(shapeId);

  if (shapeType === 'list') {
    const member = shapeDef.member ?? { target: 'smithy.api#String' };
    const memberTarget = member.target ?? 'smithy.api#String';
    const elementType = smithyTypeToLap(memberTarget, shapes, visitedCopy);
    return `[${elementType}]`;
  }

  if (shapeType === 'map') {
    const key = shapeDef.key ?? { target: 'smithy.api#String' };
    const value = shapeDef.value ?? { target: 'smithy.api#String' };
    const keyTarget = key.target ?? 'smithy.api#String';
    const valueTarget = value.target ?? 'smithy.api#String';
    const keyType = smithyTypeToLap(keyTarget, shapes, visitedCopy);
    const valueType = smithyTypeToLap(valueTarget, shapes, visitedCopy);
    return `map<${keyType},${valueType}>`;
  }

  if (shapeType === 'structure') {
    const name = shapeId.includes('#') ? shapeId.split('#')[1] : shapeId;
    return name;
  }

  if (shapeType === 'enum') {
    const members = shapeDef.members ?? {};
    const enumValues: string[] = [];
    for (const [memberName, memberDef] of Object.entries(members)) {
      const memberTraits = memberDef.traits ?? {};
      if ('smithy.api#enumValue' in memberTraits) {
        enumValues.push(String(memberTraits['smithy.api#enumValue']));
      } else {
        enumValues.push(memberName);
      }
    }
    return enumValues.length > 0 ? `enum(${enumValues.join('/')})` : 'str';
  }

  if (shapeType === 'union') {
    const name = shapeId.includes('#') ? shapeId.split('#')[1] : shapeId;
    return name;
  }

  return 'any';
}

// ── Structure to response fields ────────────────────────────────────────────

function structureToResponseFields(
  structShape: SmithyShape,
  shapes: Record<string, SmithyShape>,
  depth: number = 0,
  visited?: Set<string>,
): ResponseField[] {
  if (!visited) visited = new Set();
  if (depth > 3) return [];

  const fields: ResponseField[] = [];
  const members = structShape.members ?? {};

  for (const [memberName, memberDef] of Object.entries(members)) {
    const memberTarget = memberDef.target ?? 'smithy.api#String';
    const traits = memberDef.traits ?? {};

    // Check if nullable (opposite of required in Smithy)
    const nullable = !('smithy.api#required' in traits);

    // Get type
    const fieldType = smithyTypeToLap(memberTarget, shapes, visited);

    // Check if nested structure
    let nested: ResponseField[] | undefined;
    if (memberTarget in shapes) {
      const targetShape = shapes[memberTarget];
      if (targetShape.type === 'structure' && !visited.has(memberTarget)) {
        const visitedCopy = new Set(visited);
        visitedCopy.add(memberTarget);
        const children = structureToResponseFields(
          targetShape,
          shapes,
          depth + 1,
          visitedCopy,
        );
        if (children.length > 0) {
          nested = children;
        }
      }
    }

    fields.push({
      name: memberName,
      type: fieldType,
      nullable,
      nested,
    });
  }

  return fields;
}

// ── HTTP binding extraction ─────────────────────────────────────────────────

function parseHttpTrait(traits: Record<string, unknown>): {
  method: string;
  uri: string;
  code: number;
} {
  const httpTrait = (traits['smithy.api#http'] as Record<string, unknown>) ?? {};
  const method = (httpTrait['method'] as string) ?? 'GET';
  const uri = (httpTrait['uri'] as string) ?? '/';
  const code = (httpTrait['code'] as number) ?? 200;
  return { method, uri, code };
}

function extractHttpBindings(
  inputShapeId: string | undefined,
  _httpTrait: Record<string, unknown>,
  shapes: Record<string, SmithyShape>,
): { requiredParams: Param[]; optionalParams: Param[]; bodyFields: Param[] } {
  if (!inputShapeId || !(inputShapeId in shapes)) {
    return { requiredParams: [], optionalParams: [], bodyFields: [] };
  }

  const inputShape = shapes[inputShapeId];
  const members = inputShape.members ?? {};

  const requiredParams: Param[] = [];
  const optionalParams: Param[] = [];
  const bodyFields: Param[] = [];
  let payloadMember: string | null = null;

  // Check if there's a designated @httpPayload member
  for (const [memberName, memberDef] of Object.entries(members)) {
    if ('smithy.api#httpPayload' in (memberDef.traits ?? {})) {
      payloadMember = memberName;
      break;
    }
  }

  for (const [memberName, memberDef] of Object.entries(members)) {
    const memberTarget = memberDef.target ?? 'smithy.api#String';
    const traits = memberDef.traits ?? {};
    const required = 'smithy.api#required' in traits;
    const description = stripHtml(String(traits['smithy.api#documentation'] ?? ''));
    const fieldType = smithyTypeToLap(memberTarget, shapes);
    const isArray = fieldType.startsWith('[') && fieldType.endsWith(']');

    if ('smithy.api#httpLabel' in traits) {
      // Path parameter (always required)
      requiredParams.push({
        name: memberName,
        type: fieldType,
        description,
        required: true,
        nullable: false,
        isArray,
      });
    } else if ('smithy.api#httpQuery' in traits) {
      // Query parameter
      let queryName: string = memberName;
      const queryTrait = traits['smithy.api#httpQuery'];
      if (typeof queryTrait === 'object' && queryTrait !== null && 'value' in queryTrait) {
        queryName = String((queryTrait as { value: unknown }).value);
      } else if (typeof queryTrait === 'string') {
        queryName = queryTrait;
      } else if (queryTrait === true) {
        queryName = memberName;
      }

      const param: Param = {
        name: queryName,
        type: fieldType,
        description,
        required,
        nullable: !required,
        isArray,
      };
      if (required) {
        requiredParams.push(param);
      } else {
        optionalParams.push(param);
      }
    } else if ('smithy.api#httpHeader' in traits) {
      // Header parameter
      let headerName: string = memberName;
      const headerTrait = traits['smithy.api#httpHeader'];
      if (typeof headerTrait === 'object' && headerTrait !== null && 'value' in headerTrait) {
        headerName = String((headerTrait as { value: unknown }).value);
      } else if (typeof headerTrait === 'string') {
        headerName = headerTrait;
      } else if (headerTrait === true) {
        headerName = memberName;
      }

      const param: Param = {
        name: headerName,
        type: fieldType,
        description,
        required,
        nullable: !required,
        isArray,
      };
      if (required) {
        requiredParams.push(param);
      } else {
        optionalParams.push(param);
      }
    } else if (memberName === payloadMember) {
      // Explicit @httpPayload member -> entire body
      bodyFields.push({
        name: memberName,
        type: fieldType,
        description,
        required,
        nullable: !required,
        isArray,
      });
    } else {
      // Unbound member -> JSON body
      bodyFields.push({
        name: memberName,
        type: fieldType,
        description,
        required,
        nullable: !required,
        isArray,
      });
    }
  }

  return { requiredParams, optionalParams, bodyFields };
}

// ── Operation conversion ────────────────────────────────────────────────────

function operationToEndpoint(
  opId: string,
  opShape: SmithyShape,
  shapes: Record<string, SmithyShape>,
): Endpoint | null {
  const traits = opShape.traits ?? {};

  // Check for @http trait -- skip non-HTTP operations
  if (!('smithy.api#http' in traits)) {
    return null;
  }

  // Extract HTTP metadata
  const { method, uri: uriPattern, code: statusCode } = parseHttpTrait(traits);

  // Extract operation name and description
  const opName = opId.includes('#') ? opId.split('#')[1] : opId;
  const description = stripHtml(String(traits['smithy.api#documentation'] ?? ''));

  // Extract input bindings
  const inputRef = opShape.input?.target;
  const httpTraitValue = (traits['smithy.api#http'] as Record<string, unknown>) ?? {};
  const { requiredParams, optionalParams, bodyFields } = extractHttpBindings(
    inputRef,
    httpTraitValue,
    shapes,
  );

  // Extract output
  const outputRef = opShape.output?.target;
  const responses = extractOperationOutput(outputRef, shapes, statusCode);

  // Extract errors
  const errorRefs = opShape.errors ?? [];
  const errors = extractOperationErrors(errorRefs, shapes);

  return {
    method,
    path: uriPattern,
    description: description || opName,
    requiredParams,
    optionalParams,
    allParams: [...requiredParams, ...optionalParams],
    requestBody: bodyFields.length > 0 ? bodyFields : undefined,
    responses,
    errors,
  };
}

function extractOperationOutput(
  outputRef: string | undefined,
  shapes: Record<string, SmithyShape>,
  defaultStatus: number = 200,
): ResponseSchema[] {
  if (!outputRef || !(outputRef in shapes)) {
    return [];
  }

  const outputShape = shapes[outputRef];
  const responseFields = structureToResponseFields(outputShape, shapes);

  if (responseFields.length === 0) {
    return [];
  }

  return [
    {
      statusCode: String(defaultStatus),
      fields: responseFields,
    },
  ];
}

function extractOperationErrors(
  errorRefs: SmithyTargetRef[],
  shapes: Record<string, SmithyShape>,
): ErrorSchema[] {
  const errors: ErrorSchema[] = [];

  for (const errorRef of errorRefs) {
    const errorId =
      typeof errorRef === 'object' && errorRef !== null && 'target' in errorRef
        ? errorRef.target
        : String(errorRef);

    if (!(errorId in shapes)) {
      continue;
    }

    const errorShape = shapes[errorId];
    const traits = errorShape.traits ?? {};

    // Get HTTP status code from @httpError trait
    const statusCode = String(traits['smithy.api#httpError'] ?? 500);

    // Get error type from shape name
    const errorType = errorId.includes('#') ? errorId.split('#')[1] : errorId;

    // Get description
    const errorDescription = stripHtml(String(traits['smithy.api#documentation'] ?? ''));

    errors.push({
      statusCode,
      type: errorType,
      description: errorDescription,
    });
  }

  return errors;
}
