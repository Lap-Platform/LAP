# LAP Compression Benchmark v2

**162 API specs** across 5 formats · **5,228 endpoints** · **5,887,999 → 336,430 tokens**

### 🏆 Global Median Compression: **2.8x**

> Token counts use `len(text)//4` character-based approximation (~equivalent to tiktoken o200k_base). OpenAPI specs >1MB use 5-min compile timeout.

## Summary

| Format | Specs | Endpoints | Median | Mean | Min | Max | P25 | P75 |
|--------|------:|----------:|-------:|-----:|----:|----:|----:|----:|
| OpenAPI | 30 | 3,596 | **8.86x** | 18.27x | 5.49x | 74.75x | 5.95x | 22.13x |
| GraphQL | 30 | 548 | **1.35x** | 1.4x | 1.13x | 2.07x | 1.19x | 1.51x |
| AsyncAPI | 31 | 126 | **2.15x** | 2.69x | 1.69x | 14.04x | 1.89x | 2.77x |
| Protobuf | 35 | 406 | **1.78x** | 7.56x | 1.4x | 117.38x | 1.6x | 2.68x |
| Postman | 36 | 552 | **6.13x** | 7.02x | 4.68x | 18.0x | 5.74x | 7.22x |
| **All** | **162** | **5,228** | **2.8x** | | | | | |

## OpenAPI (30 specs, 3,596 endpoints)

| Spec | Raw Tokens | Lean Tokens | Compression | Endpoints |
|------|----------:|-----------:|------------:|----------:|
| notion.yaml | 92,611 | 1,239 | **74.75x** | 13 |
| snyk.yaml | 253,585 | 3,523 | **71.98x** | 103 |
| zoom.yaml | 1,259,292 | 17,545 | **71.77x** | 373 |
| digitalocean.yaml | 391,882 | 9,218 | **42.51x** | 290 |
| hetzner.yaml | 281,913 | 11,238 | **25.09x** | 144 |
| vercel.yaml | 232,588 | 10,393 | **22.38x** | 113 |
| asana.yaml | 117,247 | 5,267 | **22.26x** | 167 |
| plaid.yaml | 372,615 | 16,840 | **22.13x** | 198 |
| box.yaml | 306,762 | 14,173 | **21.64x** | 260 |
| slack2.yaml | 182,094 | 8,599 | **21.18x** | 174 |
| stripe-full.yaml | 1,512,828 | 106,576 | **14.19x** | 588 |
| linode.yaml | 241,928 | 17,304 | **13.98x** | 350 |
| resend.yaml | 26,934 | 2,861 | **9.41x** | 70 |
| twitter.yaml | 71,576 | 7,774 | **9.21x** | 80 |
| netlify.yaml | 22,123 | 2,474 | **8.94x** | 120 |
| launchdarkly.yaml | 34,187 | 3,892 | **8.78x** | 105 |
| gitlab.yaml | 100,079 | 12,278 | **8.15x** | 358 |
| openai-core.yaml | 2,476 | 340 | **7.28x** | 5 |
| vonage.yaml | 2,149 | 295 | **7.28x** | 3 |
| github-core.yaml | 3,000 | 429 | **6.99x** | 6 |
| stripe-charges.yaml | 2,790 | 402 | **6.94x** | 5 |
| petstore.yaml | 5,526 | 877 | **6.3x** | 19 |
| discord.yaml | 1,213 | 204 | **5.95x** | 4 |
| twilio-core.yaml | 3,356 | 576 | **5.83x** | 8 |
| slack.yaml | 1,079 | 193 | **5.59x** | 4 |
| google-maps.yaml | 1,194 | 215 | **5.55x** | 4 |
| sendgrid.yaml | 723 | 131 | **5.52x** | 3 |
| cloudflare.yaml | 1,013 | 184 | **5.51x** | 3 |
| spotify.yaml | 1,130 | 205 | **5.51x** | 4 |
| circleci.yaml | 6,682 | 1,217 | **5.49x** | 22 |

## GraphQL (30 specs, 548 endpoints)

| Spec | Raw Tokens | Lean Tokens | Compression | Endpoints |
|------|----------:|-----------:|------------:|----------:|
| wordpress.graphql | 2,485 | 1,203 | **2.07x** | 19 |
| github.graphql | 635 | 334 | **1.9x** | 10 |
| gitlab.graphql | 1,719 | 955 | **1.8x** | 10 |
| cms.graphql | 695 | 412 | **1.69x** | 16 |
| linear.graphql | 1,803 | 1,068 | **1.69x** | 21 |
| shopify.graphql | 1,925 | 1,179 | **1.63x** | 15 |
| stripe.graphql | 1,582 | 1,017 | **1.56x** | 33 |
| social.graphql | 560 | 370 | **1.51x** | 13 |
| ecommerce.graphql | 548 | 365 | **1.5x** | 11 |
| twitch.graphql | 1,114 | 751 | **1.48x** | 23 |
| pinterest.graphql | 900 | 612 | **1.47x** | 18 |
| analytics.graphql | 437 | 309 | **1.41x** | 9 |
| fauna.graphql | 1,244 | 881 | **1.41x** | 21 |
| airbnb.graphql | 1,184 | 880 | **1.35x** | 11 |
| medium.graphql | 1,068 | 793 | **1.35x** | 20 |
| twitter.graphql | 1,264 | 939 | **1.35x** | 25 |
| figma.graphql | 1,221 | 954 | **1.28x** | 14 |
| reddit.graphql | 1,339 | 1,063 | **1.26x** | 21 |
| netflix.graphql | 1,170 | 938 | **1.25x** | 19 |
| uber.graphql | 954 | 785 | **1.22x** | 14 |
| yelp.graphql | 812 | 673 | **1.21x** | 11 |
| slack.graphql | 1,316 | 1,097 | **1.2x** | 19 |
| dgraph.graphql | 2,099 | 1,765 | **1.19x** | 23 |
| jira.graphql | 1,489 | 1,248 | **1.19x** | 19 |
| discord.graphql | 1,385 | 1,177 | **1.18x** | 17 |
| spotify.graphql | 1,446 | 1,237 | **1.17x** | 27 |
| contentful.graphql | 1,238 | 1,068 | **1.16x** | 21 |
| hasura.graphql | 1,894 | 1,655 | **1.14x** | 29 |
| notion.graphql | 1,784 | 1,568 | **1.14x** | 15 |
| youtube.graphql | 1,684 | 1,490 | **1.13x** | 24 |

## AsyncAPI (31 specs, 126 endpoints)

| Spec | Raw Tokens | Lean Tokens | Compression | Endpoints |
|------|----------:|-----------:|------------:|----------:|
| social-media-backend.yaml | 646 | 46 | **14.04x** | 4 |
| stripe-webhooks.yaml | 801 | 231 | **3.47x** | 4 |
| notifications.yaml | 922 | 271 | **3.4x** | 4 |
| github-webhooks.yaml | 803 | 246 | **3.26x** | 4 |
| iot-mqtt.yaml | 883 | 286 | **3.09x** | 4 |
| chat-websocket.yaml | 829 | 285 | **2.91x** | 5 |
| ecommerce-kafka.yaml | 1,105 | 390 | **2.83x** | 6 |
| ad-bidding.yaml | 690 | 249 | **2.77x** | 4 |
| slack-events.yaml | 544 | 205 | **2.65x** | 4 |
| sports-scores.yaml | 628 | 248 | **2.53x** | 4 |
| social-media-feed.yaml | 492 | 198 | **2.48x** | 3 |
| streaming-analytics.yaml | 891 | 371 | **2.4x** | 5 |
| gaming-matchmaking.yaml | 737 | 309 | **2.39x** | 4 |
| kubernetes-events.yaml | 749 | 331 | **2.26x** | 4 |
| food-delivery.yaml | 511 | 234 | **2.18x** | 3 |
| video-streaming.yaml | 599 | 278 | **2.15x** | 4 |
| weather-alerts.yaml | 609 | 285 | **2.14x** | 3 |
| kafka-ecommerce.yaml | 640 | 309 | **2.07x** | 4 |
| stock-market-feed.yaml | 575 | 282 | **2.04x** | 4 |
| email-delivery.yaml | 603 | 301 | **2.0x** | 5 |
| ride-sharing.yaml | 616 | 308 | **2.0x** | 4 |
| iot-fleet.yaml | 625 | 320 | **1.95x** | 4 |
| supply-chain.yaml | 713 | 371 | **1.92x** | 4 |
| smart-home.yaml | 536 | 283 | **1.89x** | 4 |
| fraud-detection.yaml | 667 | 358 | **1.86x** | 4 |
| cdn-cache-invalidation.yaml | 581 | 320 | **1.82x** | 4 |
| log-aggregation.yaml | 561 | 314 | **1.79x** | 4 |
| cicd-pipeline.yaml | 574 | 323 | **1.78x** | 4 |
| payment-pipeline.yaml | 540 | 305 | **1.77x** | 4 |
| healthcare-monitoring.yaml | 689 | 393 | **1.75x** | 4 |
| aws-sns-sqs.yaml | 533 | 315 | **1.69x** | 4 |

## Protobuf (35 specs, 406 endpoints)

| Spec | Raw Tokens | Lean Tokens | Compression | Endpoints |
|------|----------:|-----------:|------------:|----------:|
| google_bigquery_model.proto | 17,725 | 151 | **117.38x** | 4 |
| google_storage.proto | 35,003 | 1,098 | **31.88x** | 24 |
| google_talent_job_service.proto | 11,202 | 470 | **23.83x** | 10 |
| google_datacatalog.proto | 21,726 | 1,589 | **13.67x** | 37 |
| google_dialogflow_session.proto | 8,868 | 785 | **11.3x** | 2 |
| opentelemetry_collector.proto | 1,225 | 143 | **8.57x** | 3 |
| etcd_rpc.proto | 11,469 | 1,631 | **7.03x** | 41 |
| envoy_ext_auth.proto | 568 | 179 | **3.17x** | 1 |
| tensorflow_serving.proto | 1,133 | 423 | **2.68x** | 7 |
| istio_mixer.proto | 873 | 333 | **2.62x** | 4 |
| google_firestore.proto | 2,236 | 1,065 | **2.1x** | 13 |
| coredns_service.proto | 611 | 295 | **2.07x** | 7 |
| vitess_tabletmanager.proto | 1,082 | 524 | **2.06x** | 11 |
| ml_serving.proto | 703 | 361 | **1.95x** | 5 |
| containerd_runtime.proto | 1,007 | 527 | **1.91x** | 13 |
| prometheus_remote.proto | 1,130 | 592 | **1.91x** | 8 |
| temporal_workflow.proto | 1,580 | 857 | **1.84x** | 10 |
| buildkite_agent.proto | 1,065 | 597 | **1.78x** | 9 |
| payments.proto | 589 | 338 | **1.74x** | 4 |
| consul_health.proto | 1,082 | 632 | **1.71x** | 8 |
| health.proto | 165 | 97 | **1.7x** | 2 |
| nats_jetstream.proto | 1,341 | 793 | **1.69x** | 12 |
| google_spanner.proto | 1,805 | 1,088 | **1.66x** | 15 |
| auth_service.proto | 1,714 | 1,054 | **1.63x** | 25 |
| monitoring_service.proto | 1,523 | 942 | **1.62x** | 16 |
| chat.proto | 598 | 371 | **1.61x** | 5 |
| workflow_service.proto | 1,265 | 793 | **1.6x** | 10 |
| user.proto | 499 | 315 | **1.58x** | 6 |
| notification_service.proto | 1,142 | 729 | **1.57x** | 10 |
| kubernetes_pods.proto | 1,130 | 728 | **1.55x** | 8 |
| stripe_payments.proto | 1,885 | 1,233 | **1.53x** | 20 |
| search_service.proto | 1,475 | 970 | **1.52x** | 13 |
| google_pubsub.proto | 1,100 | 757 | **1.45x** | 15 |
| logging_service.proto | 963 | 672 | **1.43x** | 11 |
| analytics_service.proto | 1,926 | 1,380 | **1.4x** | 17 |

## Postman (36 specs, 552 endpoints)

| Spec | Raw Tokens | Lean Tokens | Compression | Endpoints |
|------|----------:|-----------:|------------:|----------:|
| ph-healthcare.json | 21,219 | 1,179 | **18.0x** | 52 |
| cisco-nso.json | 24,078 | 1,636 | **14.72x** | 47 |
| auth0-auth.json | 7,242 | 633 | **11.44x** | 23 |
| usps-api.json | 23,410 | 2,067 | **11.33x** | 44 |
| s3-storage.json | 1,200 | 157 | **7.64x** | 6 |
| shopify-ecommerce.json | 1,488 | 199 | **7.48x** | 6 |
| okta-sso.json | 1,517 | 205 | **7.4x** | 6 |
| openstack-compute.json | 31,680 | 4,302 | **7.36x** | 157 |
| hubspot-crm.json | 1,516 | 210 | **7.22x** | 6 |
| jira-projects.json | 1,593 | 222 | **7.18x** | 6 |
| stripe-payments.json | 1,389 | 196 | **7.09x** | 6 |
| github-repos.json | 1,654 | 237 | **6.98x** | 6 |
| pagerduty-incidents.json | 1,170 | 171 | **6.84x** | 5 |
| cloudflare-dns.json | 1,598 | 240 | **6.66x** | 6 |
| sendgrid-email.json | 1,010 | 153 | **6.6x** | 5 |
| typesense.json | 12,827 | 2,042 | **6.28x** | 72 |
| vercel-deployments.json | 1,055 | 168 | **6.28x** | 5 |
| datadog-monitoring.json | 1,085 | 174 | **6.24x** | 5 |
| auth0-identity.json | 1,006 | 167 | **6.02x** | 5 |
| zoom-meetings.json | 1,109 | 185 | **5.99x** | 5 |
| twilio-messaging.json | 980 | 165 | **5.94x** | 4 |
| docker-registry.json | 1,212 | 205 | **5.91x** | 5 |
| notion-workspace.json | 1,208 | 208 | **5.81x** | 5 |
| launchdarkly-flags.json | 1,291 | 223 | **5.79x** | 5 |
| discord-bot.json | 1,107 | 192 | **5.77x** | 5 |
| file-upload.json | 786 | 137 | **5.74x** | 4 |
| sentry-errors.json | 1,222 | 213 | **5.74x** | 5 |
| mongodb-atlas.json | 1,048 | 184 | **5.7x** | 5 |
| crud-api.json | 880 | 161 | **5.47x** | 5 |
| mailchimp-marketing.json | 1,068 | 197 | **5.42x** | 5 |
| algolia-search.json | 1,131 | 211 | **5.36x** | 5 |
| slack-api.json | 919 | 174 | **5.28x** | 5 |
| multi-env.json | 1,015 | 195 | **5.21x** | 5 |
| auth-heavy.json | 1,230 | 239 | **5.15x** | 6 |
| plaid-banking.json | 1,105 | 227 | **4.87x** | 5 |
| paginated.json | 1,082 | 231 | **4.68x** | 5 |

## Key Insights

- **162 real-world API specs** benchmarked across 5 major formats
- **Global median compression: 2.8x** — LLMs need 2.8x fewer tokens to understand APIs
- **5,887,999 raw tokens → 336,430 lean tokens** (17.5x aggregate)
- Highest compression in verbose formats (OpenAPI, Postman) with rich descriptions
- Even minimal specs (Protobuf, GraphQL) show meaningful compression

---
*Generated 2026-02-08 12:27 UTC*