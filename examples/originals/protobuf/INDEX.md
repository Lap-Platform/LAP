# Protobuf Definitions - Original Documentation Index

Protocol Buffer (.proto) files are self-documenting through inline comments and structured message/service definitions.

## All Protobuf Definitions

All 35 proto files in `specs/protobuf/` are synthetic or real-inspired gRPC service definitions:

| Proto File | Type | Description |
|------------|------|-------------|
| `analytics_service.proto` | Synthetic | Analytics tracking service |
| `auth_service.proto` | Synthetic | Authentication/authorization service |
| `buildkite_agent.proto` | Real-inspired | Buildkite CI/CD agent API |
| `chat.proto` | Synthetic | Simple chat service |
| `consul_health.proto` | Real-inspired | Consul health checking |
| `containerd_runtime.proto` | Real-inspired | Containerd container runtime |
| `coredns_service.proto` | Real-inspired | CoreDNS service API |
| `envoy_ext_auth.proto` | Real-inspired | Envoy external auth filter |
| `etcd_rpc.proto` | Real-inspired | etcd distributed key-value store |
| `google_bigquery_model.proto` | Real-inspired | Google BigQuery ML models |
| `google_datacatalog.proto` | Real-inspired | Google Data Catalog |
| `google_dialogflow_session.proto` | Real-inspired | Google Dialogflow conversations |
| `google_firestore.proto` | Real-inspired | Google Firestore database |
| `google_pubsub.proto` | Real-inspired | Google Pub/Sub messaging |
| `google_spanner.proto` | Real-inspired | Google Spanner database |
| `google_storage.proto` | Real-inspired | Google Cloud Storage |
| `google_talent_job_service.proto` | Real-inspired | Google Talent Solution jobs API |
| `health.proto` | Standard | Standard gRPC health checking |
| `istio_mixer.proto` | Real-inspired | Istio mixer telemetry |
| `kubernetes_pods.proto` | Real-inspired | Kubernetes pod management |
| `logging_service.proto` | Synthetic | Centralized logging service |
| `ml_serving.proto` | Synthetic | Machine learning model serving |
| `monitoring_service.proto` | Synthetic | System monitoring service |
| `nats_jetstream.proto` | Real-inspired | NATS JetStream messaging |
| `notification_service.proto` | Synthetic | Notification delivery service |
| `opentelemetry_collector.proto` | Real-inspired | OpenTelemetry collector |
| `payments.proto` | Synthetic | Payment processing service |
| `prometheus_remote.proto` | Real-inspired | Prometheus remote storage |
| `search_service.proto` | Synthetic | Search indexing service |
| `stripe_payments.proto` | Real-inspired | Stripe payments gRPC API |
| `temporal_workflow.proto` | Real-inspired | Temporal workflow engine |
| `tensorflow_serving.proto` | Real-inspired | TensorFlow model serving |
| `user.proto` | Synthetic | Simple user management |
| `vitess_tabletmanager.proto` | Real-inspired | Vitess tablet manager |
| `workflow_service.proto` | Synthetic | Workflow orchestration service |

## Original Documentation Format

For Protocol Buffers:
- **The .proto file IS the documentation** - includes inline comments, field descriptions
- **Self-documenting by design** - messages, services, fields are explicitly typed and named
- **No separate verbose docs needed** - proto files contain all structural information

## Protobuf Self-Documentation Pattern

Proto files include inline documentation:

```protobuf
syntax = "proto3";

// User management service for authentication and profiles
service UserService {
  // Creates a new user account
  rpc CreateUser(CreateUserRequest) returns (User);
  
  // Retrieves user information by ID
  rpc GetUser(GetUserRequest) returns (User);
}

// User account information
message User {
  // Unique user identifier (UUID format)
  string user_id = 1;
  
  // User's email address (must be valid email)
  string email = 2;
  
  // User's display name (2-50 characters)
  string name = 3;
}
```

This inline documentation is the "original" format - comments serve as documentation.

## Benchmark Strategy

- **Compare against**: The .proto file itself with comments
- **DocLean compression**: Test how DocLean compresses protobuf service definitions into agent-usable format
- **All comparisons**: Local-to-local (proto files stored in specs/protobuf/)
- **gRPC reflection alternative**: Could also compare against gRPC server reflection output

## Notes on Real Proto Files

Many protos here are "real-inspired" - based on actual gRPC APIs (Google Cloud, Kubernetes, etc.) but simplified or synthesized for testing. They capture the essential structure and complexity of production gRPC services.
