/**
 * AWS SDK JSON compiler for LAP format.
 *
 * Compiles AWS SDK service definitions (used by aws-sdk-js and other AWS SDKs) into LAP format.
 * This format is different from standard Smithy -- it's AWS's proprietary service definition format.
 *
 * AWS SDK JSON structure:
 * - version: "2.0" (optional, absent in newer specs)
 * - metadata: {apiVersion, serviceFullName, protocol, signatureVersion, etc.}
 * - operations: {OperationName: {name, http, input, output, errors}}
 * - shapes: {ShapeName: {type, members, required, etc.}}
 *
 * AWS SDK -> LAP mapping:
 * - metadata -> LAPSpec (apiName, version, auth)
 * - operations -> Endpoints (method, path from http trait)
 * - shapes -> Parameters and response schemas
 */

import * as fs from 'fs';
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

// ── AWS SDK scalar types -> LAP types ───────────────────────────────────────

const AWS_SDK_TYPE_MAP: Record<string, string> = {
  string: 'str',
  integer: 'int',
  long: 'int(i64)',
  boolean: 'bool',
  double: 'num(f64)',
  float: 'num(f32)',
  timestamp: 'str(timestamp)',
  blob: 'bytes',
};

// ── Types for internal AWS SDK JSON structures ──────────────────────────────

interface AwsSdkShape {
  type?: string;
  members?: Record<string, AwsSdkMember>;
  required?: string[];
  member?: AwsSdkShapeRef;
  key?: AwsSdkShapeRef;
  value?: AwsSdkShapeRef;
  documentation?: string;
}

interface AwsSdkShapeRef {
  shape?: string;
}

interface AwsSdkMember {
  shape?: string;
  location?: string;
  locationName?: string;
  documentation?: string;
}

interface AwsSdkOperation {
  name?: string;
  http?: { method?: string; requestUri?: string };
  input?: AwsSdkShapeRef;
  output?: AwsSdkShapeRef;
  errors?: AwsSdkShapeRef[];
  documentation?: string;
}

interface AwsSdkModel {
  version?: string;
  metadata?: Record<string, unknown>;
  operations?: Record<string, AwsSdkOperation>;
  shapes?: Record<string, AwsSdkShape>;
}

// ── Main entry point ────────────────────────────────────────────────────────

/**
 * Compile an AWS SDK JSON file into a LAPSpec.
 */
export function compileAwsSdk(specPath: string): LAPSpec {
  if (!specPath.endsWith('.json') || !fs.existsSync(specPath) || fs.statSync(specPath).isDirectory()) {
    throw new Error(`AWS SDK format requires a .json file, got: ${specPath}`);
  }

  const model = loadAwsSdkJson(specPath);

  const metadata = (model.metadata ?? {}) as Record<string, unknown>;
  const apiName = (metadata.serviceFullName ?? metadata.serviceId ?? 'UnknownService') as string;
  const version = (metadata.apiVersion ?? '') as string;
  const auth = extractAuthScheme(metadata);

  const shapes = model.shapes ?? {};

  const endpoints: Endpoint[] = [];
  const operations = model.operations ?? {};

  for (const [opName, opDef] of Object.entries(operations)) {
    const endpoint = operationToEndpoint(opName, opDef, shapes);
    if (endpoint) {
      endpoints.push(endpoint);
    }
  }

  return {
    version: 'v0.3',
    apiName,
    baseUrl: '',
    apiVersion: version,
    auth,
    endpoints,
    getEndpoint(method: string, path: string) {
      return this.endpoints.find((e) => e.method === method && e.path === path);
    },
  };
}

// ── Load and validate ───────────────────────────────────────────────────────

function loadAwsSdkJson(specPath: string): AwsSdkModel {
  let text: string;
  try {
    text = fs.readFileSync(specPath, 'utf-8');
  } catch {
    throw new Error(`Could not read file: ${specPath}`);
  }

  let model: AwsSdkModel;
  try {
    model = JSON.parse(text) as AwsSdkModel;
  } catch (e) {
    throw new Error(`Invalid JSON in ${specPath}: ${e}`);
  }

  // Validate AWS SDK JSON structure
  // Accept either version "2.0" or metadata-based (newer specs omit version key)
  const ver = model.version;
  const meta = model.metadata;
  const hasVersion = ver === '2.0';
  const hasMeta =
    meta !== undefined &&
    typeof meta === 'object' &&
    !Array.isArray(meta) &&
    'apiVersion' in meta &&
    'protocol' in meta;

  if (!hasVersion && !hasMeta) {
    throw new Error(
      `Not a valid AWS SDK JSON: expected version '2.0' or metadata with apiVersion/protocol, got version=${JSON.stringify(ver)}`,
    );
  }
  if (!model.shapes) {
    throw new Error('Not a valid AWS SDK JSON: missing \'shapes\' field');
  }
  if (!model.operations) {
    throw new Error('Not a valid AWS SDK JSON: missing \'operations\' field');
  }

  return model;
}

// ── Auth extraction ─────────────────────────────────────────────────────────

function extractAuthScheme(metadata: Record<string, unknown>): string {
  const sigVersion = metadata.signatureVersion;
  if (sigVersion === 'v4') return 'AWS SigV4';

  const auth = metadata.auth;
  if (Array.isArray(auth) && auth.includes('aws.auth#sigv4')) return 'AWS SigV4';

  return '';
}

// ── Type mapping ────────────────────────────────────────────────────────────

function awsSdkTypeToLap(
  shapeName: string,
  shapes: Record<string, AwsSdkShape>,
  visited?: Set<string>,
): string {
  if (!visited) visited = new Set();

  // Cycle detection
  if (visited.has(shapeName)) return 'any';
  if (!(shapeName in shapes)) return 'any';

  const shape = shapes[shapeName];
  const shapeType = shape.type ?? '';
  const visitedCopy = new Set(visited);
  visitedCopy.add(shapeName);

  // Primitive types
  if (shapeType in AWS_SDK_TYPE_MAP) return AWS_SDK_TYPE_MAP[shapeType];

  // List type
  if (shapeType === 'list') {
    const memberName = shape.member?.shape ?? 'string';
    const elementType = awsSdkTypeToLap(memberName, shapes, visitedCopy);
    return `[${elementType}]`;
  }

  // Map type
  if (shapeType === 'map') {
    const keyName = shape.key?.shape ?? 'string';
    const valueName = shape.value?.shape ?? 'string';
    const keyType = awsSdkTypeToLap(keyName, shapes, visitedCopy);
    const valueType = awsSdkTypeToLap(valueName, shapes, visitedCopy);
    return `map<${keyType},${valueType}>`;
  }

  // Structure type
  if (shapeType === 'structure') return shapeName;

  return 'any';
}

// ── Structure to response fields ────────────────────────────────────────────

function structureToResponseFields(
  shapeName: string,
  shapes: Record<string, AwsSdkShape>,
  depth: number = 0,
  visited?: Set<string>,
): ResponseField[] {
  if (!visited) visited = new Set();
  if (depth > 3 || visited.has(shapeName)) return [];
  if (!(shapeName in shapes)) return [];

  const shape = shapes[shapeName];
  if (shape.type !== 'structure') return [];

  const members = shape.members ?? {};
  const requiredSet = new Set(shape.required ?? []);
  const fields: ResponseField[] = [];

  for (const [memberName, memberDef] of Object.entries(members)) {
    const memberShape = memberDef.shape ?? 'string';
    const nullable = !requiredSet.has(memberName);
    const fieldType = awsSdkTypeToLap(memberShape, shapes, visited);

    // Check if nested structure
    let nested: ResponseField[] | undefined;
    if (memberShape in shapes) {
      const targetShape = shapes[memberShape];
      if (targetShape.type === 'structure') {
        const visitedCopy = new Set(visited);
        visitedCopy.add(shapeName);
        const children = structureToResponseFields(memberShape, shapes, depth + 1, visitedCopy);
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

// ── Parameter extraction ────────────────────────────────────────────────────

function extractOperationParams(
  inputShapeName: string | undefined,
  httpConfig: { method?: string; requestUri?: string },
  shapes: Record<string, AwsSdkShape>,
): { requiredParams: Param[]; optionalParams: Param[]; bodyFields: Param[] } {
  if (!inputShapeName || !(inputShapeName in shapes)) {
    return { requiredParams: [], optionalParams: [], bodyFields: [] };
  }

  const inputShape = shapes[inputShapeName];
  const members = inputShape.members ?? {};
  const requiredSet = new Set(inputShape.required ?? []);

  const requiredParams: Param[] = [];
  const optionalParams: Param[] = [];
  const bodyFields: Param[] = [];

  // Get URI pattern to identify path parameters
  const uri = httpConfig.requestUri ?? '/';
  const pathParamMatches = uri.match(/\{(\w+)\}/g) ?? [];
  const pathParams = new Set(pathParamMatches.map((m) => m.slice(1, -1)));

  for (const [memberName, memberDef] of Object.entries(members)) {
    const memberShape = memberDef.shape ?? 'string';
    const location = memberDef.location ?? '';
    const locationName = memberDef.locationName ?? memberName;
    const required = requiredSet.has(memberName);
    const fieldType = awsSdkTypeToLap(memberShape, shapes);
    const isArray = fieldType.startsWith('[') && fieldType.endsWith(']');

    if (location === 'uri' || pathParams.has(memberName)) {
      // Path parameter (always required)
      requiredParams.push({
        name: memberName,
        type: fieldType,
        description: '',
        required: true,
        nullable: false,
        isArray,
      });
    } else if (location === 'querystring') {
      const param: Param = {
        name: locationName,
        type: fieldType,
        description: '',
        required,
        nullable: !required,
        isArray,
      };
      if (required) {
        requiredParams.push(param);
      } else {
        optionalParams.push(param);
      }
    } else if (location === 'header') {
      const param: Param = {
        name: locationName,
        type: fieldType,
        description: '',
        required,
        nullable: !required,
        isArray,
      };
      if (required) {
        requiredParams.push(param);
      } else {
        optionalParams.push(param);
      }
    } else {
      // Body field
      bodyFields.push({
        name: memberName,
        type: fieldType,
        description: '',
        required,
        nullable: !required,
        isArray,
      });
    }
  }

  return { requiredParams, optionalParams, bodyFields };
}

// ── Operation to endpoint ───────────────────────────────────────────────────

function operationToEndpoint(
  opName: string,
  opDef: AwsSdkOperation,
  shapes: Record<string, AwsSdkShape>,
): Endpoint | null {
  const httpConfig = opDef.http ?? {};
  const method = httpConfig.method ?? 'POST';
  const endpointPath = httpConfig.requestUri ?? '/';

  // Extract documentation
  let description: string | undefined;
  if (opDef.documentation) {
    description = stripHtml(opDef.documentation).trim();
  }

  // Extract input parameters
  const inputShape = opDef.input?.shape;
  const { requiredParams, optionalParams, bodyFields } = extractOperationParams(
    inputShape,
    httpConfig,
    shapes,
  );

  // Extract output
  const outputShape = opDef.output?.shape;
  const responses: ResponseSchema[] = [];
  if (outputShape && outputShape in shapes) {
    const responseFields = structureToResponseFields(outputShape, shapes);
    if (responseFields.length > 0) {
      responses.push({
        statusCode: '200',
        fields: responseFields,
      });
    }
  }

  // Extract errors
  const errors: ErrorSchema[] = [];
  const opErrors = opDef.errors ?? [];
  for (const error of opErrors) {
    const errorShape = error.shape ?? '';
    if (errorShape in shapes) {
      const errorDef = shapes[errorShape];
      // AWS SDK doesn't always include HTTP status code;
      // default to 400 for client errors, 500 for server errors
      const statusCode = errorShape.includes('Client') ? '400' : '500';
      let errorDescription: string | undefined;
      if (errorDef.documentation) {
        errorDescription = stripHtml(errorDef.documentation).trim();
      }

      errors.push({
        statusCode,
        type: errorShape,
        description: errorDescription,
      });
    }
  }

  return {
    method,
    path: endpointPath,
    description,
    requiredParams,
    optionalParams,
    allParams: [...requiredParams, ...optionalParams],
    requestBody: bodyFields.length > 0 ? bodyFields : undefined,
    responses,
    errors,
  };
}
