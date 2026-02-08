# LAP DocLean — Full Benchmark Report
**Date:** 2026-02-08 10:27 UTC  
**Runtime:** 79.8s

---

## Summary — All Formats

| Format | Specs | Endpoints | Raw Tokens | Lean Tokens | Compression |
|---------|-------|-----------|------------|-------------|-------------|
| OpenAPI | 28 | 2,635 | 2,131,740 | 161,109 | **13.2x** |
| GraphQL | 5 | 59 | 3,167 | 2,026 | **1.6x** |
| AsyncAPI | 30 | 122 | 17,242 | 10,625 | **1.6x** |
| Protobuf | 5 | 22 | 2,783 | 1,720 | **1.6x** |
| Postman | 30 | 157 | 35,199 | 7,393 | **4.8x** |
| **TOTAL** | **98** | **2,995** | **2,190,131** | **182,873** | **12.0x** |

## Agent Task Benchmark

- 12 tasks tested (dry-run token comparison)
- **39.4% average token reduction** with DocLean specs vs raw

## Lossless Validation

| Format | Total | Passed | Failed | Errored |
|---------|-------|--------|--------|---------|
| OpenAPI | 28 | 25 | 3 | 0 |
| GraphQL | 5 | 0 | 5 | 0 |
| AsyncAPI | 30 | 30 | 0 | 0 |
| Protobuf | 5 | 5 | 0 | 0 |
| Postman | 30 | 30 | 0 | 0 |

### OpenAPI Failures
- **digitalocean.yaml** — error (`'name'`)
- **notion.yaml** — 21/22 params (1 param lost)
- **vercel.yaml** — 4 breaking changes

### GraphQL Failures
- All 5 GraphQL specs fail validation (endpoint matching issues — not compression failures)

---

## Detailed Results by Format

### OpenAPI (28 specs, 2,635 endpoints)

| API | EPs | Raw | Lean | Ratio |
|-----|-----|-----|------|-------|
| asana | 167 | 97,427 | 7,450 | 13.1x |
| box | 260 | 232,848 | 16,228 | 14.3x |
| circleci | 22 | 5,725 | 1,377 | 4.2x |
| cloudflare | 3 | 763 | 237 | 3.2x |
| digitalocean | 290 | 345,401 | 12,534 | 27.6x |
| discord | 4 | 909 | 253 | 3.6x |
| github-core | 6 | 2,190 | 548 | 4.0x |
| gitlab | 358 | 88,242 | 14,774 | 6.0x |
| google-maps | 4 | 941 | 257 | 3.7x |
| hetzner | 144 | 167,308 | 13,628 | 12.3x |
| launchdarkly | 105 | 31,522 | 4,502 | 7.0x |
| linode | 350 | 203,653 | 20,740 | 9.8x |
| netlify | 120 | 20,142 | 2,916 | 6.9x |
| notion | 13 | 68,587 | 1,609 | 42.6x |
| openai-core | 5 | 1,730 | 456 | 3.8x |
| petstore | 19 | 4,656 | 1,122 | 4.1x |
| plaid | 198 | 304,530 | 18,859 | 16.1x |
| resend | 70 | 21,890 | 3,551 | 6.2x |
| sendgrid | 3 | 518 | 163 | 3.2x |
| slack | 4 | 762 | 238 | 3.2x |
| slack2 | 174 | 126,517 | 10,484 | 12.1x |
| snyk | 103 | 201,205 | 4,281 | 47.0x |
| spotify | 4 | 826 | 262 | 3.2x |
| stripe-charges | 5 | 1,892 | 462 | 4.1x |
| twilio-core | 8 | 2,465 | 697 | 3.5x |
| twitter | 80 | 61,043 | 9,387 | 6.5x |
| vercel | 113 | 136,159 | 13,710 | 9.9x |
| vonage | 3 | 1,889 | 384 | 4.9x |

### GraphQL (5 specs, 59 endpoints)

| API | EPs | Raw | Lean | Ratio |
|-----|-----|-----|------|-------|
| analytics | 9 | 473 | 340 | 1.4x |
| cms | 16 | 764 | 449 | 1.7x |
| ecommerce | 11 | 614 | 413 | 1.5x |
| github | 10 | 674 | 393 | 1.7x |
| social | 13 | 642 | 431 | 1.5x |

### AsyncAPI (30 specs, 122 endpoints)

| API | EPs | Raw | Lean | Ratio |
|-----|-----|-----|------|-------|
| ad-bidding | 4 | 567 | 307 | 1.8x |
| aws-sns-sqs | 4 | 481 | 363 | 1.3x |
| cdn-cache-invalidation | 4 | 547 | 390 | 1.4x |
| chat-websocket | 5 | 658 | 361 | 1.8x |
| cicd-pipeline | 4 | 522 | 383 | 1.4x |
| ecommerce-kafka | 6 | 786 | 443 | 1.8x |
| email-delivery | 5 | 556 | 374 | 1.5x |
| food-delivery | 3 | 447 | 275 | 1.6x |
| fraud-detection | 4 | 576 | 401 | 1.4x |
| gaming-matchmaking | 4 | 644 | 384 | 1.7x |
| github-webhooks | 4 | 645 | 303 | 2.1x |
| healthcare-monitoring | 4 | 630 | 449 | 1.4x |
| iot-fleet | 4 | 575 | 369 | 1.6x |
| iot-mqtt | 4 | 656 | 320 | 2.0x |
| kafka-ecommerce | 4 | 555 | 354 | 1.6x |
| kubernetes-events | 4 | 648 | 402 | 1.6x |
| log-aggregation | 4 | 512 | 371 | 1.4x |
| notifications | 4 | 708 | 323 | 2.2x |
| payment-pipeline | 4 | 491 | 352 | 1.4x |
| ride-sharing | 4 | 565 | 381 | 1.5x |
| slack-events | 4 | 476 | 266 | 1.8x |
| smart-home | 4 | 502 | 334 | 1.5x |
| social-media-feed | 3 | 447 | 250 | 1.8x |
| sports-scores | 4 | 559 | 310 | 1.8x |
| stock-market-feed | 4 | 534 | 345 | 1.5x |
| streaming-analytics | 5 | 662 | 438 | 1.5x |
| stripe-webhooks | 4 | 604 | 302 | 2.0x |
| supply-chain | 4 | 615 | 416 | 1.5x |
| video-streaming | 4 | 542 | 340 | 1.6x |
| weather-alerts | 3 | 532 | 319 | 1.7x |

### Protobuf (5 specs, 22 endpoints)

| API | EPs | Raw | Lean | Ratio |
|-----|-----|-----|------|-------|
| chat | 5 | 662 | 439 | 1.5x |
| health | 2 | 157 | 112 | 1.4x |
| ml_serving | 5 | 765 | 416 | 1.8x |
| payments | 4 | 653 | 389 | 1.7x |
| user | 6 | 546 | 364 | 1.5x |

### Postman (30 specs, 157 endpoints)

| API | EPs | Raw | Lean | Ratio |
|-----|-----|-----|------|-------|
| algolia-search | 5 | 1,153 | 271 | 4.3x |
| auth-heavy | 6 | 1,311 | 293 | 4.5x |
| auth0-identity | 5 | 1,041 | 216 | 4.8x |
| cloudflare-dns | 6 | 1,406 | 307 | 4.6x |
| crud-api | 5 | 924 | 212 | 4.4x |
| datadog-monitoring | 5 | 1,141 | 230 | 5.0x |
| discord-bot | 5 | 1,122 | 240 | 4.7x |
| docker-registry | 5 | 1,150 | 243 | 4.7x |
| file-upload | 4 | 922 | 181 | 5.1x |
| github-repos | 6 | 1,400 | 304 | 4.6x |
| hubspot-crm | 6 | 1,307 | 258 | 5.1x |
| jira-projects | 6 | 1,478 | 288 | 5.1x |
| launchdarkly-flags | 5 | 1,274 | 278 | 4.6x |
| mailchimp-marketing | 5 | 1,115 | 244 | 4.6x |
| mongodb-atlas | 5 | 1,042 | 220 | 4.7x |
| multi-env | 5 | 1,067 | 247 | 4.3x |
| notion-workspace | 5 | 1,239 | 260 | 4.8x |
| okta-sso | 6 | 1,330 | 263 | 5.1x |
| pagerduty-incidents | 5 | 1,173 | 217 | 5.4x |
| paginated | 5 | 1,206 | 294 | 4.1x |
| plaid-banking | 5 | 1,191 | 263 | 4.5x |
| s3-storage | 6 | 1,179 | 202 | 5.8x |
| sendgrid-email | 5 | 1,039 | 194 | 5.4x |
| sentry-errors | 5 | 1,226 | 275 | 4.5x |
| shopify-ecommerce | 6 | 1,346 | 256 | 5.3x |
| slack-api | 5 | 972 | 222 | 4.4x |
| stripe-payments | 6 | 1,236 | 248 | 5.0x |
| twilio-messaging | 4 | 969 | 205 | 4.7x |
| vercel-deployments | 5 | 1,101 | 228 | 4.8x |
| zoom-meetings | 5 | 1,139 | 234 | 4.9x |

---

*Generated by LAP DocLean benchmark suite*
