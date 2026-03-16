import { describe, it } from 'node:test';
import * as assert from 'node:assert';
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

console.log('\n-- Protobuf compiler tests complete --');
