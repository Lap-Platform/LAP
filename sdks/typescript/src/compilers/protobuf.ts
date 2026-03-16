/**
 * Protobuf (.proto) -> LAPSpec.
 * Regex-based parser -- no external protobuf library needed.
 * Maps each `rpc Method(Request) returns (Response)` to POST /Service/Method.
 *
 * Ported from the registry compiler (TypeScript) and Python compiler.
 */

import * as fs from 'fs';
import * as path from 'path';
import type {
  LAPSpec,
  Endpoint,
  Param,
  ResponseSchema,
  ResponseField,
} from '../parser';

// ---- Proto type mapping ----

const PROTO_TYPE_MAP: Record<string, string> = {
  string: 'str',
  bytes: 'str(bytes)',
  bool: 'bool',
  int32: 'int',
  int64: 'int(int64)',
  uint32: 'int',
  uint64: 'int(int64)',
  sint32: 'int',
  sint64: 'int(int64)',
  fixed32: 'int',
  fixed64: 'int(int64)',
  sfixed32: 'int',
  sfixed64: 'int(int64)',
  float: 'num(float)',
  double: 'num',
};

function protoTypeToLap(protoType: string, repeated: boolean): string {
  const mapped = PROTO_TYPE_MAP[protoType] || 'map';
  return repeated ? `[${mapped}]` : mapped;
}

// ---- Message parsing ----

interface ProtoField {
  name: string;
  type: string;
  repeated: boolean;
}

type MessageMap = Map<string, ProtoField[]>;

function parseMessageFields(body: string): ProtoField[] {
  const fields: ProtoField[] = [];
  // Remove nested message/enum blocks to avoid parsing their fields
  const cleaned = body
    .replace(/\b(message|enum)\s+\w+\s*\{[^}]*\}/g, '')
    .replace(/\boneof\s+\w+\s*\{([^}]*)\}/g, '$1'); // flatten oneof

  const fieldRegex = /(?:(repeated)\s+)?(\w[\w.]*)\s+(\w+)\s*=\s*\d+/g;
  let m: RegExpExecArray | null;

  while ((m = fieldRegex.exec(cleaned)) !== null) {
    // Skip reserved/option lines
    if (m[2] === 'option' || m[2] === 'reserved') continue;
    fields.push({
      name: m[3],
      type: m[2],
      repeated: m[1] === 'repeated',
    });
  }

  return fields;
}

function parseMessages(src: string): MessageMap {
  const messages: MessageMap = new Map();
  // Match top-level and nested message blocks (single level of nesting)
  const msgRegex = /message\s+(\w+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/g;
  let match: RegExpExecArray | null;

  while ((match = msgRegex.exec(src)) !== null) {
    const name = match[1];
    const body = match[2];
    const fields = parseMessageFields(body);
    messages.set(name, fields);
  }

  return messages;
}

// ---- Param / Response builders ----

function makeParam(name: string, type: string, required: boolean, description: string): Param {
  return {
    name,
    type,
    required,
    description,
    nullable: !required,
    enumValues: undefined,
    defaultValue: undefined,
    format: undefined,
    isArray: type.startsWith('['),
    nested: undefined,
  };
}

function messageToParams(messages: MessageMap, msgName: string): Param[] {
  const fields = messages.get(msgName);
  if (!fields) return [];

  return fields.map((f) =>
    makeParam(f.name, protoTypeToLap(f.type, f.repeated), true, ''),
  );
}

function messageToResponse(messages: MessageMap, msgName: string): ResponseSchema[] {
  const fields = messages.get(msgName);
  if (!fields || !fields.length) return [];

  const responseFields: ResponseField[] = fields.map((f) => ({
    name: f.name,
    type: protoTypeToLap(f.type, f.repeated),
    nullable: false,
  }));

  return [{
    statusCode: '200',
    description: undefined,
    fields: responseFields,
  }];
}

// ---- Main entry ----

/**
 * Compile a .proto file (or directory of .proto files) to a LAPSpec.
 *
 * @param specPath - Path to a .proto file or a directory containing .proto files.
 */
export function compileProtobuf(specPath: string): LAPSpec {
  const filePath = path.resolve(specPath);
  let content: string;

  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    // Directory: find all .proto files and concatenate
    const entries = fs.readdirSync(filePath)
      .filter((f) => f.endsWith('.proto'))
      .sort();
    if (entries.length === 0) {
      throw new Error(`No .proto files found in directory '${specPath}'.`);
    }
    content = entries
      .map((f) => fs.readFileSync(path.join(filePath, f), 'utf-8'))
      .join('\n');
  } else {
    content = fs.readFileSync(filePath, 'utf-8');
  }

  // Strip comments
  let src = content
    .replace(/\/\/[^\n]*/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '');

  // Package name
  const pkgMatch = src.match(/package\s+([\w.]+)\s*;/);
  const apiName = pkgMatch
    ? pkgMatch[1]
    : path.basename(filePath, path.extname(filePath)) || 'Untitled Proto API';

  // Parse all message blocks into a type map
  const messages = parseMessages(src);

  // Parse all service blocks
  const endpoints: Endpoint[] = [];
  const serviceRegex = /service\s+(\w+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/g;
  let svcMatch: RegExpExecArray | null;

  while ((svcMatch = serviceRegex.exec(src)) !== null) {
    const serviceName = svcMatch[1];
    const serviceBody = svcMatch[2];

    // Parse rpc declarations
    const rpcRegex = /rpc\s+(\w+)\s*\(\s*(stream\s+)?(\w+)\s*\)\s*returns\s*\(\s*(stream\s+)?(\w+)\s*\)/g;
    let rpcMatch: RegExpExecArray | null;

    while ((rpcMatch = rpcRegex.exec(serviceBody)) !== null) {
      const methodName = rpcMatch[1];
      const clientStream = !!rpcMatch[2];
      const requestType = rpcMatch[3];
      const serverStream = !!rpcMatch[4];
      const responseType = rpcMatch[5];

      // Streaming prefix
      let streamPrefix = '';
      if (clientStream && serverStream) streamPrefix = '[BIDI_STREAM] ';
      else if (serverStream) streamPrefix = '[SERVER_STREAM] ';
      else if (clientStream) streamPrefix = '[CLIENT_STREAM] ';

      // Request message -> body params
      const requestBody = messageToParams(messages, requestType);

      // Response message -> response schema
      const responseSchemas = messageToResponse(messages, responseType);

      const allParams = [...requestBody];

      endpoints.push({
        method: 'POST',
        path: `/${serviceName}/${methodName}`,
        description: `${streamPrefix}${serviceName}.${methodName}`,
        requiredParams: [],
        optionalParams: [],
        allParams,
        requestBody: requestBody.length > 0 ? requestBody : undefined,
        responses: responseSchemas,
        errors: [],
      });
    }
  }

  return {
    version: 'v0.3',
    apiName,
    baseUrl: '',
    endpoints,
    getEndpoint(method: string, p: string): Endpoint | undefined {
      return this.endpoints.find((e) => e.method === method && e.path === p);
    },
  };
}
