# AsyncAPI Specs - Original Documentation Index

AsyncAPI specifications describe event-driven APIs and message formats.

## All AsyncAPI Specs

All 47 specs in `specs/asyncapi/` are synthetic/example specifications demonstrating various async messaging patterns:

| Spec File | Type | Description |
|-----------|------|-------------|
| `ad-bidding.yaml` | Synthetic | Real-time ad bidding system |
| `anyof-asyncapi.yml` | Example | AsyncAPI anyOf pattern demo |
| `application-headers-asyncapi.yml` | Example | Application-level headers |
| `aws-sns-sqs.yaml` | Real-inspired | AWS SNS/SQS messaging |
| `chat-websocket.yaml` | Synthetic | WebSocket chat application |
| `food-delivery.yaml` | Synthetic | Food delivery order events |
| `github-webhooks.yaml` | Real-inspired | GitHub webhook events |
| `gitter-streaming-asyncapi.yml` | Real-inspired | Gitter chat streaming |
| `kafka-ecommerce.yaml` | Synthetic | Kafka e-commerce events |
| `kraken-websocket-request-reply-multiple-channels-asyncapi.yml` | Real-inspired | Kraken exchange WebSocket |
| `log-aggregation.yaml` | Synthetic | Log aggregation pipeline |
| `mercure-asyncapi.yml` | Real-inspired | Mercure protocol events |
| `notifications.yaml` | Synthetic | Notification delivery system |
| `oneof-asyncapi.yml` | Example | AsyncAPI oneOf pattern demo |
| `operation-security-asyncapi.yml` | Example | Operation security patterns |
| `payment-pipeline.yaml` | Synthetic | Payment processing pipeline |
| `ride-sharing.yaml` | Synthetic | Ride-sharing events |
| `rpc-client-asyncapi.yml` | Example | RPC client pattern |
| `slack-events.yaml` | Real-inspired | Slack event API |
| `slack-rtm-asyncapi.yml` | Real-inspired | Slack RTM WebSocket |
| `social-media-feed.yaml` | Synthetic | Social media feed events |
| `sports-scores.yaml` | Synthetic | Live sports score updates |
| `stock-market-feed.yaml` | Synthetic | Stock market data feed |
| `streaming-analytics.yaml` | Synthetic | Streaming analytics pipeline |
| `streetlights-mqtt-asyncapi.yml` | Example | MQTT streetlight control |
| `stripe-webhooks.yaml` | Real-inspired | Stripe webhook events |
| `supply-chain.yaml` | Synthetic | Supply chain tracking |

(Plus ~20 more - run `ls specs/asyncapi/` for complete list)

## Original Documentation Format

For AsyncAPI:
- **The AsyncAPI YAML IS the original spec** - structured message/channel definitions
- **Similar to OpenAPI** - human docs would be vendor-specific (e.g., Stripe webhook docs)
- **Most specs here are synthetic** - created for testing DocLean compression

## AsyncAPI Self-Documentation

AsyncAPI specs include inline documentation:

```yaml
channels:
  user/signedup:
    description: Channel for user signup events
    subscribe:
      message:
        description: Event published when a user signs up
        payload:
          type: object
          properties:
            userId:
              type: string
              description: Unique user identifier
```

This structured format is the "original" documentation - no external markdown needed for synthetic examples.

## Benchmark Strategy

- **For real APIs** (Stripe, Slack, GitHub): Compare against vendor webhook documentation if available
- **For synthetic specs**: Compare DocLean output against the spec itself or generated verbose representation
- **All comparisons**: Local-to-local, no network fetching
