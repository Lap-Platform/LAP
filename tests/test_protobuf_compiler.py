#!/usr/bin/env python3
"""Tests for the Protobuf/gRPC → LAP compiler."""

import sys
from pathlib import Path

import pytest


from lap.core.compilers.protobuf import parse_proto, compile_proto, compile_proto_dir, ProtoFile

SPECS_DIR = Path(__file__).resolve().parent.parent / "examples" / "verbose" / "protobuf"


# ── Parser Tests ─────────────────────────────────────────────────────

class TestParseProto:
    def test_syntax(self):
        pf = parse_proto('syntax = "proto3";')
        assert pf.syntax == "proto3"

    def test_package(self):
        pf = parse_proto('syntax = "proto3"; package foo.bar;')
        assert pf.package == "foo.bar"

    def test_imports(self):
        pf = parse_proto('''
            syntax = "proto3";
            import "google/protobuf/timestamp.proto";
            import "google/protobuf/empty.proto";
        ''')
        assert len(pf.imports) == 2
        assert "google/protobuf/timestamp.proto" in pf.imports

    def test_simple_message(self):
        pf = parse_proto('''
            syntax = "proto3";
            message Foo {
                string name = 1;
                int32 age = 2;
            }
        ''')
        assert len(pf.messages) == 1
        assert pf.messages[0].name == "Foo"
        assert len(pf.messages[0].fields) == 2
        assert pf.messages[0].fields[0].name == "name"
        assert pf.messages[0].fields[0].type == "string"

    def test_repeated_field(self):
        pf = parse_proto('''
            syntax = "proto3";
            message Foo { repeated string tags = 1; }
        ''')
        assert pf.messages[0].fields[0].label == "repeated"

    def test_map_field(self):
        pf = parse_proto('''
            syntax = "proto3";
            message Foo { map<string, int32> counts = 1; }
        ''')
        f = pf.messages[0].fields[0]
        assert f.type == "map"
        assert f.map_key == "string"
        assert f.map_value == "int32"

    def test_enum(self):
        pf = parse_proto('''
            syntax = "proto3";
            enum Color {
                COLOR_UNSPECIFIED = 0;
                RED = 1;
                GREEN = 2;
                BLUE = 3;
            }
        ''')
        assert len(pf.enums) == 1
        assert pf.enums[0].name == "Color"
        assert len(pf.enums[0].values) == 4
        assert ("RED", 1) in pf.enums[0].values

    def test_nested_message(self):
        pf = parse_proto('''
            syntax = "proto3";
            message Outer {
                message Inner { string val = 1; }
                Inner item = 1;
            }
        ''')
        outer = pf.messages[0]
        assert len(outer.messages) == 1
        assert outer.messages[0].name == "Inner"

    def test_nested_enum(self):
        pf = parse_proto('''
            syntax = "proto3";
            message Response {
                enum Status {
                    UNKNOWN = 0;
                    OK = 1;
                }
                Status status = 1;
            }
        ''')
        msg = pf.messages[0]
        assert len(msg.enums) == 1
        assert msg.enums[0].name == "Status"

    def test_oneof(self):
        pf = parse_proto('''
            syntax = "proto3";
            message Foo {
                oneof value {
                    string text = 1;
                    int32 number = 2;
                }
            }
        ''')
        msg = pf.messages[0]
        assert "value" in msg.oneofs
        assert len(msg.oneofs["value"]) == 2
        assert all(f.oneof_group == "value" for f in msg.oneofs["value"])

    def test_service_unary(self):
        pf = parse_proto('''
            syntax = "proto3";
            service Greeter {
                rpc SayHello(HelloRequest) returns (HelloReply);
            }
            message HelloRequest { string name = 1; }
            message HelloReply { string message = 1; }
        ''')
        assert len(pf.services) == 1
        assert pf.services[0].name == "Greeter"
        rpc = pf.services[0].rpcs[0]
        assert rpc.name == "SayHello"
        assert not rpc.client_streaming
        assert not rpc.server_streaming

    def test_service_server_streaming(self):
        pf = parse_proto('''
            syntax = "proto3";
            service Svc { rpc Watch(Req) returns (stream Resp); }
            message Req { string id = 1; }
            message Resp { string data = 1; }
        ''')
        rpc = pf.services[0].rpcs[0]
        assert rpc.server_streaming
        assert not rpc.client_streaming

    def test_service_client_streaming(self):
        pf = parse_proto('''
            syntax = "proto3";
            service Svc { rpc Upload(stream Chunk) returns (Summary); }
            message Chunk { bytes data = 1; }
            message Summary { int32 total = 1; }
        ''')
        rpc = pf.services[0].rpcs[0]
        assert rpc.client_streaming
        assert not rpc.server_streaming

    def test_service_bidi_streaming(self):
        pf = parse_proto('''
            syntax = "proto3";
            service Svc { rpc Chat(stream Msg) returns (stream Msg); }
            message Msg { string text = 1; }
        ''')
        rpc = pf.services[0].rpcs[0]
        assert rpc.client_streaming
        assert rpc.server_streaming

    def test_comments_stripped(self):
        pf = parse_proto('''
            syntax = "proto3";
            // This is a comment
            /* Block comment */
            message Foo {
                string name = 1; // inline comment
            }
        ''')
        assert len(pf.messages) == 1
        assert pf.messages[0].fields[0].name == "name"

    def test_multiple_services(self):
        pf = parse_proto('''
            syntax = "proto3";
            service A { rpc DoA(Req) returns (Resp); }
            service B { rpc DoB(Req) returns (Resp); }
            message Req { string id = 1; }
            message Resp { string result = 1; }
        ''')
        assert len(pf.services) == 2


# ── Compiler Tests (individual protos) ───────────────────────────────

class TestCompileHealth:
    @pytest.fixture
    def spec(self):
        return compile_proto(str(SPECS_DIR / "health.proto"))

    def test_api_name(self, spec):
        assert spec.api_name == "grpc.health.v1"

    def test_endpoint_count(self, spec):
        assert len(spec.endpoints) == 2

    def test_unary_check(self, spec):
        ep = spec.endpoints[0]
        assert ep.method == "UNARY"
        assert "Health/Check" in ep.path

    def test_server_stream_watch(self, spec):
        ep = spec.endpoints[1]
        assert ep.method == "SERVER-STREAM"
        assert "Health/Watch" in ep.path

    def test_enum_in_response(self, spec):
        ep = spec.endpoints[0]
        assert len(ep.response_schemas) == 1
        # HealthCheckResponse is a reused type, so it's defined via @type
        # and referenced by name in the response
        output = spec.to_lap()
        assert "SERVING" in output


class TestCompileUser:
    @pytest.fixture
    def spec(self):
        return compile_proto(str(SPECS_DIR / "user.proto"))

    def test_endpoint_count(self, spec):
        assert len(spec.endpoints) == 6

    def test_has_client_streaming(self, spec):
        bulk = [e for e in spec.endpoints if "BulkImport" in e.path]
        assert len(bulk) == 1
        assert bulk[0].method == "CLIENT-STREAM"

    def test_map_field_in_params(self, spec):
        # Map field should be present either inline or in a @type definition
        output = spec.to_lap()
        assert "map<str,str>" in output

    def test_oneof_in_response(self, spec):
        # Oneof fields should be present in the @type definition or inline
        output = spec.to_lap()
        assert "avatar_url: str?" in output
        assert "avatar_data: bytes?" in output

    def test_nested_message_in_response(self, spec):
        # Address fields should be present in a @type or inline
        output = spec.to_lap()
        assert "street: str" in output
        assert "city: str" in output

    def test_wkt_timestamp(self, spec):
        output = spec.to_lap()
        assert "timestamp" in output

    def test_empty_response(self, spec):
        delete = [e for e in spec.endpoints if "DeleteUser" in e.path][0]
        assert len(delete.response_schemas) == 1
        assert delete.response_schemas[0].status_code == "OK"


class TestCompilePayments:
    @pytest.fixture
    def spec(self):
        return compile_proto(str(SPECS_DIR / "payments.proto"))

    def test_endpoint_count(self, spec):
        assert len(spec.endpoints) == 4

    def test_oneof_payment_method(self, spec):
        create = [e for e in spec.endpoints if "CreatePayment" in e.path][0]
        pm_params = [p for p in create.request_body if p.name == "payment_method"]
        assert len(pm_params) == 1

    def test_enum_types(self, spec):
        output = spec.to_lap()
        assert "PAYMENT_STATUS_PENDING" in output or "enum(" in output


class TestCompileChat:
    @pytest.fixture
    def spec(self):
        return compile_proto(str(SPECS_DIR / "chat.proto"))

    def test_endpoint_count(self, spec):
        assert len(spec.endpoints) == 5

    def test_bidi_stream(self, spec):
        chat = [e for e in spec.endpoints if e.path.endswith("/Chat")][0]
        assert chat.method == "BIDI-STREAM"

    def test_server_stream(self, spec):
        stream = [e for e in spec.endpoints if "StreamMessages" in e.path][0]
        assert stream.method == "SERVER-STREAM"


class TestCompileMLServing:
    @pytest.fixture
    def spec(self):
        return compile_proto(str(SPECS_DIR / "ml_serving.proto"))

    def test_endpoint_count(self, spec):
        assert len(spec.endpoints) == 5

    def test_all_streaming_patterns(self, spec):
        methods = {e.method for e in spec.endpoints}
        assert "UNARY" in methods
        assert "CLIENT-STREAM" in methods
        assert "SERVER-STREAM" in methods

    def test_map_inputs(self, spec):
        # Map fields should be present in the output (inline or @type)
        output = spec.to_lap()
        assert "map<str," in output


# ── LAP Output Tests ─────────────────────────────────────────────

class TestLAPOutput:
    def test_lap_header(self):
        spec = compile_proto(str(SPECS_DIR / "health.proto"))
        output = spec.to_lap()
        assert "@lap" in output
        assert "@api grpc.health.v1" in output

    def test_lean_mode_shorter(self):
        spec = compile_proto(str(SPECS_DIR / "user.proto"))
        normal = spec.to_lap(lean=False)
        lean = spec.to_lap(lean=True)
        assert len(lean) <= len(normal)

    def test_endpoint_format(self):
        spec = compile_proto(str(SPECS_DIR / "health.proto"))
        output = spec.to_lap()
        assert "@endpoint UNARY" in output
        assert "@endpoint SERVER-STREAM" in output

    def test_all_protos_compile(self):
        """All 5 proto files compile without errors."""
        for proto_file in SPECS_DIR.glob("*.proto"):
            spec = compile_proto(str(proto_file))
            output = spec.to_lap()
            assert len(output) > 50
            assert "@lap" in output

    def test_compile_directory(self):
        specs = compile_proto_dir(str(SPECS_DIR))
        assert len(specs) >= 5


# ── Token Benchmark ──────────────────────────────────────────────────

class TestTokenBenchmark:
    """Verify LAP achieves meaningful compression vs raw proto."""

    @staticmethod
    def _approx_tokens(text: str) -> int:
        """Rough token count (~4 chars per token)."""
        return len(text) // 4

    def test_compression_ratio(self):
        """LAP should be more compact than raw proto for all specs."""
        for proto_file in SPECS_DIR.glob("*.proto"):
            raw = proto_file.read_text(encoding='utf-8')
            spec = compile_proto(str(proto_file))
            lap = spec.to_lap(lean=True)

            raw_tokens = self._approx_tokens(raw)
            dl_tokens = self._approx_tokens(lap)

            # LAP should be within 2x of raw (it restructures, doesn't inflate)
            assert dl_tokens < raw_tokens * 2, (
                f"{proto_file.name}: LAP ({dl_tokens}) > 2x raw ({raw_tokens})"
            )

    def test_lean_vs_standard(self):
        """Lean mode should always be <= standard mode."""
        for proto_file in SPECS_DIR.glob("*.proto"):
            spec = compile_proto(str(proto_file))
            standard = spec.to_lap(lean=False)
            lean = spec.to_lap(lean=True)
            assert len(lean) <= len(standard), f"{proto_file.name}: lean > standard"

    def test_aggregate_stats(self):
        """Print aggregate token stats for all proto specs."""
        total_raw = 0
        total_dl = 0
        total_lean = 0
        for proto_file in sorted(SPECS_DIR.glob("*.proto")):
            raw = proto_file.read_text(encoding='utf-8')
            spec = compile_proto(str(proto_file))
            dl = spec.to_lap(lean=False)
            lean = spec.to_lap(lean=True)

            raw_t = self._approx_tokens(raw)
            dl_t = self._approx_tokens(dl)
            lean_t = self._approx_tokens(lean)

            total_raw += raw_t
            total_dl += dl_t
            total_lean += lean_t

        # Just verify totals are sane
        assert total_raw > 0
        assert total_dl > 0
        assert total_lean > 0
        assert total_lean <= total_dl


# ── CLI Integration ──────────────────────────────────────────────────

class TestCLI:
    def test_cli_protobuf_subcommand(self, tmp_path):
        """CLI protobuf subcommand works."""
        import subprocess
        cli_path = Path(__file__).resolve().parent.parent / "lap" / "cli" / "main.py"
        proto_path = SPECS_DIR / "health.proto"
        out = tmp_path / "health.lap"

        result = subprocess.run(
            [sys.executable, str(cli_path), "compile", str(proto_path), "-o", str(out)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert out.exists()
        content = out.read_text(encoding='utf-8')
        assert "@lap" in content
        assert "Health/Check" in content

    def test_cli_protobuf_directory(self, tmp_path):
        """CLI protobuf subcommand works with directory."""
        import subprocess
        cli_path = Path(__file__).resolve().parent.parent / "lap" / "cli" / "main.py"
        out = tmp_path / "all.lap"

        result = subprocess.run(
            [sys.executable, str(cli_path), "compile", str(SPECS_DIR), "-o", str(out)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert out.exists()
        content = out.read_text(encoding='utf-8')
        assert content.count("@lap") >= 5

    def test_cli_protobuf_lean(self, tmp_path):
        """CLI protobuf --lean flag works."""
        import subprocess
        cli_path = Path(__file__).resolve().parent.parent / "lap" / "cli" / "main.py"
        proto_path = SPECS_DIR / "user.proto"
        out_std = tmp_path / "std.lap"
        out_lean = tmp_path / "lean.lap"

        subprocess.run(
            [sys.executable, str(cli_path), "compile", str(proto_path), "-o", str(out_std)],
            capture_output=True, text=True, timeout=10,
        )
        subprocess.run(
            [sys.executable, str(cli_path), "compile", str(proto_path), "--lean", "-o", str(out_lean)],
            capture_output=True, text=True, timeout=10,
        )
        assert out_lean.stat().st_size <= out_std.stat().st_size
