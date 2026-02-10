#!/usr/bin/env python3
"""Tests for AsyncAPI → DocLean compiler."""

import sys
from pathlib import Path

import pytest


from core.compilers.asyncapi import compile_asyncapi, resolve_ref, extract_type, _detect_version


SPECS_DIR = Path(__file__).parent.parent / "examples" / "verbose" / "asyncapi"


# ── Helpers ──────────────────────────────────────────────────────────

def get_spec(name):
    return str(SPECS_DIR / name)


# ── Basic compile tests ─────────────────────────────────────────────

class TestIoTMQTT:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doclean = compile_asyncapi(get_spec("iot-mqtt.yaml"))

    def test_api_name(self):
        assert self.doclean.api_name == "IoT Sensor Network"

    def test_version(self):
        assert self.doclean.version == "1.0.0"

    def test_base_url(self):
        assert "mqtt" in self.doclean.base_url

    def test_protocol(self):
        assert self.doclean.auth_scheme == "mqtt"

    def test_endpoint_count(self):
        assert len(self.doclean.endpoints) == 4

    def test_has_pub_and_sub(self):
        methods = {ep.method for ep in self.doclean.endpoints}
        assert "PUB" in methods
        assert "SUB" in methods

    def test_telemetry_channel(self):
        eps = [e for e in self.doclean.endpoints if "telemetry" in e.path]
        assert len(eps) == 1
        ep = eps[0]
        assert ep.method == "SUB"
        req_names = {p.name for p in ep.required_params}
        assert "sensorId" in req_names
        assert "timestamp" in req_names
        assert "temperature" in req_names

    def test_command_channel(self):
        eps = [e for e in self.doclean.endpoints if "commands" in e.path]
        assert len(eps) == 1
        ep = eps[0]
        assert ep.method == "PUB"
        req_names = {p.name for p in ep.required_params}
        assert "command" in req_names

    def test_mqtt_bindings_in_summary(self):
        eps = [e for e in self.doclean.endpoints if "telemetry" in e.path]
        assert "mqtt" in eps[0].summary.lower()

    def test_optional_params(self):
        eps = [e for e in self.doclean.endpoints if "telemetry" in e.path]
        opt_names = {p.name for p in eps[0].optional_params}
        assert "humidity" in opt_names or "battery" in opt_names

    def test_doclean_output(self):
        output = self.doclean.to_doclean()
        assert "@doclean" in output
        assert "@api IoT Sensor Network" in output
        assert "@endpoint" in output

    def test_lean_output_shorter(self):
        normal = self.doclean.to_doclean(lean=False)
        lean = self.doclean.to_doclean(lean=True)
        assert len(lean) < len(normal)


class TestChatWebSocket:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doclean = compile_asyncapi(get_spec("chat-websocket.yaml"))

    def test_api_name(self):
        assert self.doclean.api_name == "Real-time Chat"

    def test_endpoint_count(self):
        # messages(pub+sub), typing(pub), presence(sub), reactions(pub) = 5
        assert len(self.doclean.endpoints) == 5

    def test_ws_protocol(self):
        assert "ws" in self.doclean.base_url

    def test_message_send_endpoint(self):
        pubs = [e for e in self.doclean.endpoints if e.method == "PUB" and "messages" in e.path]
        assert len(pubs) == 1
        req_names = {p.name for p in pubs[0].required_params}
        assert "content" in req_names
        assert "senderId" in req_names

    def test_presence_subscribe(self):
        subs = [e for e in self.doclean.endpoints if "presence" in e.path]
        assert len(subs) == 1
        assert subs[0].method == "SUB"


class TestECommerceKafka:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doclean = compile_asyncapi(get_spec("ecommerce-kafka.yaml"))

    def test_api_name(self):
        assert self.doclean.api_name == "E-Commerce Event Stream"

    def test_kafka_base_url(self):
        assert "kafka" in self.doclean.base_url

    def test_endpoint_count(self):
        # orders.created, orders.updated, payments.processed, inventory.updated,
        # customers.events (2 oneOf messages) = 6
        assert len(self.doclean.endpoints) == 6

    def test_oneof_messages(self):
        cust_eps = [e for e in self.doclean.endpoints if "customers" in e.path]
        assert len(cust_eps) == 2

    def test_order_created_fields(self):
        eps = [e for e in self.doclean.endpoints if "orders.created" in e.path]
        assert len(eps) == 1
        req_names = {p.name for p in eps[0].required_params}
        assert "orderId" in req_names
        assert "items" in req_names

    def test_kafka_bindings(self):
        eps = [e for e in self.doclean.endpoints if "orders.created" in e.path]
        assert "kafka" in eps[0].summary.lower()

    def test_headers_extracted(self):
        eps = [e for e in self.doclean.endpoints if "orders.created" in e.path]
        opt_names = {p.name for p in eps[0].optional_params}
        assert "header:correlationId" in opt_names


class TestNotificationsV3:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doclean = compile_asyncapi(get_spec("notifications.yaml"))

    def test_api_name(self):
        assert self.doclean.api_name == "Notification Service"

    def test_version(self):
        assert self.doclean.version == "1.5.0"

    def test_protocol(self):
        assert self.doclean.auth_scheme == "amqp"

    def test_endpoint_count(self):
        assert len(self.doclean.endpoints) == 4

    def test_operations_mapped(self):
        methods = {ep.method for ep in self.doclean.endpoints}
        assert "PUB" in methods
        assert "SUB" in methods

    def test_email_operation(self):
        eps = [e for e in self.doclean.endpoints if "email" in e.path]
        assert len(eps) == 1
        assert eps[0].method == "PUB"
        req_names = {p.name for p in eps[0].required_params}
        assert "to" in req_names
        assert "subject" in req_names

    def test_status_receive(self):
        eps = [e for e in self.doclean.endpoints if "status" in e.path]
        assert len(eps) == 1
        assert eps[0].method == "SUB"

    def test_channel_addresses_used(self):
        paths = {ep.path for ep in self.doclean.endpoints}
        assert "notifications/email" in paths
        assert "notifications/sms" in paths


class TestStreamingAnalytics:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doclean = compile_asyncapi(get_spec("streaming-analytics.yaml"))

    def test_api_name(self):
        assert self.doclean.api_name == "Streaming Analytics Pipeline"

    def test_endpoint_count(self):
        assert len(self.doclean.endpoints) == 5

    def test_aggregates_is_pub(self):
        eps = [e for e in self.doclean.endpoints if "aggregates" in e.path]
        assert eps[0].method == "PUB"

    def test_pageview_fields(self):
        eps = [e for e in self.doclean.endpoints if "pageviews" in e.path]
        req_names = {p.name for p in eps[0].required_params}
        assert "sessionId" in req_names
        assert "url" in req_names


# ── Utility function tests ──────────────────────────────────────────

class TestResolveRef:
    def test_basic_ref(self):
        spec = {"components": {"schemas": {"Foo": {"type": "object"}}}}
        result = resolve_ref(spec, "#/components/schemas/Foo")
        assert result == {"type": "object"}

    def test_circular_ref_raises(self):
        spec = {"a": {"$ref": "#/b"}, "b": {"$ref": "#/a"}}
        with pytest.raises(ValueError, match="Circular"):
            resolve_ref(spec, "#/a")

    def test_nested_ref(self):
        spec = {
            "components": {
                "schemas": {
                    "A": {"$ref": "#/components/schemas/B"},
                    "B": {"type": "string"},
                }
            }
        }
        result = resolve_ref(spec, "#/components/schemas/A")
        assert result == {"type": "string"}


class TestExtractType:
    def test_string(self):
        assert extract_type({"type": "string"}, {}) == "str"

    def test_string_format(self):
        assert extract_type({"type": "string", "format": "date-time"}, {}) == "str(date-time)"

    def test_integer(self):
        assert extract_type({"type": "integer"}, {}) == "int"

    def test_array(self):
        assert extract_type({"type": "array", "items": {"type": "string"}}, {}) == "[str]"

    def test_boolean(self):
        assert extract_type({"type": "boolean"}, {}) == "bool"

    def test_object(self):
        assert extract_type({"type": "object"}, {}) == "map"

    def test_empty(self):
        assert extract_type({}, {}) == "any"


class TestDetectVersion:
    def test_v2(self):
        assert _detect_version({"asyncapi": "2.6.0"}) == 2

    def test_v3(self):
        assert _detect_version({"asyncapi": "3.0.0"}) == 3

    def test_default(self):
        assert _detect_version({}) == 2


# ── Cross-spec tests ────────────────────────────────────────────────

class TestAllSpecs:
    """Run across all specs to ensure no crashes."""

    @pytest.fixture(params=[
        "iot-mqtt.yaml",
        "chat-websocket.yaml",
        "ecommerce-kafka.yaml",
        "notifications.yaml",
        "streaming-analytics.yaml",
    ])
    def spec_name(self, request):
        return request.param

    def test_compiles(self, spec_name):
        doclean = compile_asyncapi(get_spec(spec_name))
        assert doclean.api_name
        assert len(doclean.endpoints) > 0

    def test_doclean_output_valid(self, spec_name):
        doclean = compile_asyncapi(get_spec(spec_name))
        output = doclean.to_doclean()
        assert "@doclean" in output
        assert "@api" in output
        assert "@endpoint" in output

    def test_lean_mode(self, spec_name):
        doclean = compile_asyncapi(get_spec(spec_name))
        lean = doclean.to_doclean(lean=True)
        normal = doclean.to_doclean(lean=False)
        assert len(lean) <= len(normal)

    def test_has_required_or_optional_params(self, spec_name):
        doclean = compile_asyncapi(get_spec(spec_name))
        has_params = any(
            ep.required_params or ep.optional_params
            for ep in doclean.endpoints
        )
        assert has_params


# ── Token benchmark ──────────────────────────────────────────────────

class TestTokenBenchmark:
    """Verify AsyncAPI specs achieve meaningful compression."""

    def _count_tokens(self, text: str) -> int:
        """Rough token count: words + punctuation splits."""
        # Simple approximation: ~4 chars per token
        return max(1, len(text) // 4)

    @pytest.fixture(params=[
        "iot-mqtt.yaml",
        "chat-websocket.yaml",
        "ecommerce-kafka.yaml",
        "notifications.yaml",
        "streaming-analytics.yaml",
    ])
    def spec_name(self, request):
        return request.param

    def test_compression_ratio(self, spec_name):
        spec_path = get_spec(spec_name)
        raw_text = Path(spec_path).read_text()
        doclean = compile_asyncapi(spec_path)
        compiled = doclean.to_doclean(lean=False)

        raw_tokens = self._count_tokens(raw_text)
        compiled_tokens = self._count_tokens(compiled)

        ratio = raw_tokens / compiled_tokens if compiled_tokens else float('inf')
        # AsyncAPI specs should compress at least 1.2x
        assert ratio >= 1.2, f"{spec_name}: ratio {ratio:.2f}x too low"

    def test_lean_extra_compression(self, spec_name):
        spec_path = get_spec(spec_name)
        doclean = compile_asyncapi(spec_path)
        normal = doclean.to_doclean(lean=False)
        lean = doclean.to_doclean(lean=True)

        normal_tokens = self._count_tokens(normal)
        lean_tokens = self._count_tokens(lean)

        # Lean should be same or smaller
        assert lean_tokens <= normal_tokens


# ── Edge cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_channels(self, tmp_path):
        spec = tmp_path / "empty.yaml"
        spec.write_text("asyncapi: '2.6.0'\ninfo:\n  title: Empty\n  version: '1.0'\nchannels: {}\n")
        doclean = compile_asyncapi(str(spec))
        assert doclean.api_name == "Empty"
        assert len(doclean.endpoints) == 0

    def test_invalid_spec_raises(self, tmp_path):
        spec = tmp_path / "bad.yaml"
        spec.write_text("- just a list\n")
        with pytest.raises(ValueError):
            compile_asyncapi(str(spec))

    def test_no_payload(self, tmp_path):
        spec = tmp_path / "nopayload.yaml"
        spec.write_text("""
asyncapi: '2.6.0'
info:
  title: Minimal
  version: '1.0'
channels:
  test/channel:
    subscribe:
      message:
        name: EmptyMessage
""")
        doclean = compile_asyncapi(str(spec))
        assert len(doclean.endpoints) == 1

    def test_ref_in_message(self, tmp_path):
        spec = tmp_path / "ref.yaml"
        spec.write_text("""
asyncapi: '2.6.0'
info:
  title: RefTest
  version: '1.0'
channels:
  test/channel:
    subscribe:
      message:
        $ref: '#/components/messages/TestMsg'
components:
  messages:
    TestMsg:
      name: TestMessage
      payload:
        type: object
        required:
          - id
        properties:
          id:
            type: string
          value:
            type: integer
""")
        doclean = compile_asyncapi(str(spec))
        assert len(doclean.endpoints) == 1
        req_names = {p.name for p in doclean.endpoints[0].required_params}
        assert "id" in req_names
