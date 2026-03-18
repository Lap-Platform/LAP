import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { compileProtobuf } from '../src/compilers/protobuf';
import { detectFormat } from '../src/compilers/index';

// When compiled, __dirname = sdks/typescript/dist/tests
const EXAMPLES_DIR = path.resolve(__dirname, '../../../../examples/verbose/protobuf');

describe('Protobuf Compiler', () => {
  describe('Chat service', () => {
    it('should detect protobuf format from .proto extension', () => {
      const specPath = path.join(EXAMPLES_DIR, 'chat.proto');
      const format = detectFormat(specPath);
      assert.strictEqual(format, 'protobuf');
    });

    it('should compile chat.proto with correct metadata', () => {
      const specPath = path.join(EXAMPLES_DIR, 'chat.proto');
      const spec = compileProtobuf(specPath);

      // Package is chat.v1
      assert.strictEqual(spec.apiName, 'chat.v1');
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
    });

    it('should map RPC methods to POST endpoints', () => {
      const specPath = path.join(EXAMPLES_DIR, 'chat.proto');
      const spec = compileProtobuf(specPath);

      // All RPC methods should be POST
      for (const ep of spec.endpoints) {
        assert.strictEqual(ep.method, 'POST', `Endpoint ${ep.path} should be POST`);
      }

      // Check specific RPCs
      const sendMsg = spec.getEndpoint('POST', '/ChatService/SendMessage');
      assert.ok(sendMsg, 'Should find POST /ChatService/SendMessage');

      const listRooms = spec.getEndpoint('POST', '/ChatService/ListRooms');
      assert.ok(listRooms, 'Should find POST /ChatService/ListRooms');

      const getHistory = spec.getEndpoint('POST', '/ChatService/GetHistory');
      assert.ok(getHistory, 'Should find POST /ChatService/GetHistory');
    });

    it('should extract request message fields as params', () => {
      const specPath = path.join(EXAMPLES_DIR, 'chat.proto');
      const spec = compileProtobuf(specPath);

      // SendMessage takes SendMessageRequest with room_id, type, content, etc.
      const sendMsg = spec.getEndpoint('POST', '/ChatService/SendMessage')!;
      const bodyParams = sendMsg.requestBody || sendMsg.allParams;
      const paramNames = bodyParams.map(p => p.name);
      assert.ok(paramNames.includes('room_id'), 'Should have room_id param from SendMessageRequest');
      assert.ok(paramNames.includes('content'), 'Should have content param from SendMessageRequest');
    });

    it('should extract response message fields in response schema', () => {
      const specPath = path.join(EXAMPLES_DIR, 'chat.proto');
      const spec = compileProtobuf(specPath);

      // SendMessage returns ChatMessage
      const sendMsg = spec.getEndpoint('POST', '/ChatService/SendMessage')!;
      assert.ok(sendMsg.responses.length > 0, 'Should have response schemas');
      const fields = sendMsg.responses[0].fields;
      const fieldNames = fields.map(f => f.name);
      assert.ok(fieldNames.includes('id'), 'ChatMessage response should have id field');
      assert.ok(fieldNames.includes('room_id'), 'ChatMessage response should have room_id field');
      assert.ok(fieldNames.includes('content'), 'ChatMessage response should have content field');
    });

    it('should annotate streaming RPCs in description', () => {
      const specPath = path.join(EXAMPLES_DIR, 'chat.proto');
      const spec = compileProtobuf(specPath);

      // StreamMessages returns stream ChatMessage -> SERVER_STREAM
      const streamMsgs = spec.getEndpoint('POST', '/ChatService/StreamMessages');
      assert.ok(streamMsgs, 'Should find StreamMessages endpoint');
      assert.ok(
        streamMsgs.description?.includes('SERVER_STREAM'),
        `StreamMessages should be annotated as SERVER_STREAM, got: ${streamMsgs.description}`
      );

      // Chat(stream ChatEvent) returns (stream ChatEvent) -> BIDI_STREAM
      const chat = spec.getEndpoint('POST', '/ChatService/Chat');
      assert.ok(chat, 'Should find Chat endpoint');
      assert.ok(
        chat.description?.includes('BIDI_STREAM'),
        `Chat should be annotated as BIDI_STREAM, got: ${chat.description}`
      );
    });

    it('should have correct endpoint count for ChatService', () => {
      const specPath = path.join(EXAMPLES_DIR, 'chat.proto');
      const spec = compileProtobuf(specPath);

      // ChatService has 5 RPCs: SendMessage, StreamMessages, Chat, ListRooms, GetHistory
      assert.strictEqual(spec.endpoints.length, 5, `Expected 5 endpoints, got ${spec.endpoints.length}`);
    });
  });

  describe('Analytics service', () => {
    it('should compile analytics_service.proto', () => {
      const specPath = path.join(EXAMPLES_DIR, 'analytics_service.proto');
      const spec = compileProtobuf(specPath);

      assert.ok(spec.apiName, 'Should have API name');
      assert.ok(spec.endpoints.length > 0, 'Should have endpoints');
    });
  });

  describe('Negative tests', () => {
    it('should throw on non-existent file', () => {
      assert.throws(
        () => compileProtobuf('/nonexistent/path/to/service.proto'),
        /ENOENT|no such file/i,
      );
    });
  });
});

describe('Protobuf parser units', () => {
  // Helper to write a temp .proto file, compile it, and clean up
  function withProto(content: string, fn: (specPath: string) => void): void {
    const tmpFile = path.join(os.tmpdir(), `lap-proto-test-${Date.now()}-${Math.random().toString(36).slice(2)}.proto`);
    fs.writeFileSync(tmpFile, content, 'utf-8');
    try {
      fn(tmpFile);
    } finally {
      if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
    }
  }

  it('parses simple message with scalar fields', () => {
    withProto(`
      syntax = "proto3";
      package svc.v1;
      message Req { string id = 1; }
      message Res { string name = 1; int32 age = 2; }
      service Svc { rpc Get(Req) returns (Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      assert.strictEqual(spec.endpoints.length, 1, 'Should have 1 endpoint');
      const ep = spec.getEndpoint('POST', '/Svc/Get');
      assert.ok(ep, 'Should find POST /Svc/Get');
      // Response should have name and age fields
      assert.ok(ep.responses.length > 0, 'Should have response schema');
      const fieldNames = ep.responses[0].fields.map(f => f.name);
      assert.ok(fieldNames.includes('name'), 'Response should have name field');
      assert.ok(fieldNames.includes('age'), 'Response should have age field');
    });
  });

  it('parses repeated field as array type', () => {
    withProto(`
      syntax = "proto3";
      package arr.v1;
      message Req { string query = 1; }
      message Res { repeated string tags = 1; }
      service TagSvc { rpc List(Req) returns (Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      const ep = spec.getEndpoint('POST', '/TagSvc/List');
      assert.ok(ep, 'Should find POST /TagSvc/List');
      assert.ok(ep.responses.length > 0, 'Should have response schema');
      const tagsField = ep.responses[0].fields.find(f => f.name === 'tags');
      assert.ok(tagsField, 'Should have tags field');
      assert.ok(tagsField.type.startsWith('['), `tags field type should be array, got: ${tagsField.type}`);
    });
  });

  it('parses message with map field -- endpoint is created, scalar siblings extracted', () => {
    // The regex-based parser does not parse map<K,V> field syntax, so map fields
    // are silently skipped. The endpoint and any scalar sibling fields are still parsed.
    withProto(`
      syntax = "proto3";
      package map.v1;
      message Req { map<string, int32> counts = 1; string name = 2; }
      message Res { string result = 1; }
      service MapSvc { rpc SetCounts(Req) returns (Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      const ep = spec.getEndpoint('POST', '/MapSvc/SetCounts');
      assert.ok(ep, 'Should find POST /MapSvc/SetCounts even when request has map field');
      // Scalar sibling 'name' should be extracted; 'counts' (map) is skipped
      const paramNames = (ep.requestBody || ep.allParams).map(p => p.name);
      assert.ok(paramNames.includes('name'), 'Scalar sibling name should be extracted');
      // Response scalar field is still parsed correctly
      assert.ok(ep.responses.length > 0, 'Response schema should be present');
      const resultField = ep.responses[0].fields.find(f => f.name === 'result');
      assert.ok(resultField, 'Response should have result field');
    });
  });

  it('parses enum values are accessible as fields when used in message', () => {
    withProto(`
      syntax = "proto3";
      package enum.v1;
      enum Status { UNKNOWN = 0; ACTIVE = 1; INACTIVE = 2; }
      message Req { string id = 1; }
      message Res { Status status = 1; string name = 2; }
      service EnumSvc { rpc Get(Req) returns (Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      assert.ok(spec.endpoints.length > 0, 'Should have at least 1 endpoint');
      const ep = spec.getEndpoint('POST', '/EnumSvc/Get');
      assert.ok(ep, 'Should find POST /EnumSvc/Get');
      assert.ok(ep.responses.length > 0, 'Should have response schema');
      const fieldNames = ep.responses[0].fields.map(f => f.name);
      assert.ok(fieldNames.includes('status'), 'Response should have status field from enum reference');
      assert.ok(fieldNames.includes('name'), 'Response should have name field');
    });
  });

  it('parses oneof fields -- both alternatives appear as params', () => {
    withProto(`
      syntax = "proto3";
      package oneof.v1;
      message Req {
        oneof choice {
          string text = 1;
          int32 number = 2;
        }
      }
      message Res { string result = 1; }
      service OneofSvc { rpc Process(Req) returns (Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      const ep = spec.getEndpoint('POST', '/OneofSvc/Process');
      assert.ok(ep, 'Should find POST /OneofSvc/Process');
      const paramNames = (ep.requestBody || ep.allParams).map(p => p.name);
      assert.ok(paramNames.includes('text'), 'Oneof should expose text field as param');
      assert.ok(paramNames.includes('number'), 'Oneof should expose number field as param');
    });
  });

  it('strips line and block comments from source', () => {
    withProto(`
      // This is a top-level comment
      syntax = "proto3";
      /* block comment about package */
      package clean.v1;
      message Req { /* field comment */ string id = 1; // trailing comment
      }
      message Res { string value = 1; }
      // Service comment
      service CleanSvc {
        /* rpc comment */
        rpc Fetch(Req) returns (Res);
      }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      assert.ok(spec.apiName === 'clean.v1', `API name should be clean.v1, got: ${spec.apiName}`);
      const ep = spec.getEndpoint('POST', '/CleanSvc/Fetch');
      assert.ok(ep, 'Should find POST /CleanSvc/Fetch despite comments');
      // Description should not contain comment text
      assert.ok(!ep.description?.includes('//'), 'Description should not contain comment syntax');
      assert.ok(!ep.description?.includes('/*'), 'Description should not contain block comment syntax');
    });
  });

  it('handles multiple services in one proto file', () => {
    withProto(`
      syntax = "proto3";
      package multi.v1;
      message Req { string id = 1; }
      message Res { string data = 1; }
      service ServiceA { rpc DoA(Req) returns (Res); }
      service ServiceB { rpc DoB(Req) returns (Res); rpc DoC(Req) returns (Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      assert.strictEqual(spec.endpoints.length, 3, 'Should have 3 endpoints across 2 services');
      assert.ok(spec.getEndpoint('POST', '/ServiceA/DoA'), 'Should have ServiceA/DoA');
      assert.ok(spec.getEndpoint('POST', '/ServiceB/DoB'), 'Should have ServiceB/DoB');
      assert.ok(spec.getEndpoint('POST', '/ServiceB/DoC'), 'Should have ServiceB/DoC');
    });
  });

  it('handles server streaming rpc', () => {
    withProto(`
      syntax = "proto3";
      package stream.v1;
      message Req { string filter = 1; }
      message Res { string item = 1; }
      service StreamSvc { rpc List(Req) returns (stream Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      const ep = spec.getEndpoint('POST', '/StreamSvc/List');
      assert.ok(ep, 'Should find POST /StreamSvc/List');
      assert.ok(ep.description?.includes('SERVER_STREAM'), `Server streaming rpc should be annotated SERVER_STREAM, got: ${ep.description}`);
    });
  });

  it('handles client streaming rpc', () => {
    withProto(`
      syntax = "proto3";
      package upload.v1;
      message Req { string chunk = 1; }
      message Res { int32 total = 1; }
      service UploadSvc { rpc Upload(stream Req) returns (Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      const ep = spec.getEndpoint('POST', '/UploadSvc/Upload');
      assert.ok(ep, 'Should find POST /UploadSvc/Upload');
      assert.ok(ep.description?.includes('CLIENT_STREAM'), `Client streaming rpc should be annotated CLIENT_STREAM, got: ${ep.description}`);
    });
  });

  it('handles bidi streaming rpc', () => {
    withProto(`
      syntax = "proto3";
      package chat.v1;
      message Req { string msg = 1; }
      message Res { string reply = 1; }
      service ChatSvc { rpc Chat(stream Req) returns (stream Res); }
    `, (specPath) => {
      const spec = compileProtobuf(specPath);
      const ep = spec.getEndpoint('POST', '/ChatSvc/Chat');
      assert.ok(ep, 'Should find POST /ChatSvc/Chat');
      assert.ok(ep.description?.includes('BIDI_STREAM'), `Bidi streaming rpc should be annotated BIDI_STREAM, got: ${ep.description}`);
    });
  });
});

console.log('\n-- Protobuf compiler tests complete --');
