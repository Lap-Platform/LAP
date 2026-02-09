# LAP Benchmark: Median vs Mean Compression Ratios

*Generated: 2026-02-08 | Tokenizer: tiktoken o200k_base*

## Summary

Compression ratio = DocLean tokens / Raw tokens (lower = better compression)

### Standard DocLean Compression

| Format | Specs | Median | Mean | Min | Max | P25 | P75 |
|--------|-------|--------|------|-----|-----|-----|-----|
| openapi | 30 | 0.3095 | 0.3220 | 0.0314 | 0.6127 | 0.1765 | 0.4999 |
| graphql | 30 | 0.8636 | 0.8583 | 0.7592 | 0.9522 | 0.8397 | 0.8812 |
| asyncapi | 31 | 0.7939 | 0.7749 | 0.1902 | 0.9896 | 0.7284 | 0.8536 |
| protobuf | 35 | 0.6563 | 0.5563 | 0.0126 | 0.8917 | 0.4686 | 0.7136 |
| postman | 36 | 0.2882 | 0.2711 | 0.1038 | 0.3693 | 0.2690 | 0.3044 |

### Lean DocLean Compression

| Format | Specs | Median | Mean | Min | Max | P25 | P75 |
|--------|-------|--------|------|-----|-----|-----|-----|
| openapi | 30 | 0.1631 | 0.1904 | 0.0253 | 0.4147 | 0.0885 | 0.2747 |
| graphql | 30 | 0.7730 | 0.7603 | 0.5340 | 0.9473 | 0.6711 | 0.8442 |
| asyncapi | 31 | 0.7068 | 0.6956 | 0.1902 | 0.9023 | 0.6625 | 0.7747 |
| protobuf | 35 | 0.6358 | 0.5362 | 0.0121 | 0.8917 | 0.4461 | 0.6950 |
| postman | 36 | 0.2501 | 0.2324 | 0.0847 | 0.3251 | 0.2305 | 0.2625 |

## OPENAPI — Per-Spec Details

| Spec | Raw Tokens | Std Tokens | Lean Tokens | Std Ratio | Lean Ratio |
|------|-----------|------------|-------------|-----------|------------|
| notion | 68,587 | 2,151 | 1,733 | 0.0314 | 0.0253 |
| snyk | 201,205 | 10,708 | 5,193 | 0.0532 | 0.0258 |
| zoom | 848,983 | 91,762 | 22,474 | 0.1081 | 0.0265 |
| digitalocean | 345,401 | 24,325 | 12,896 | 0.0704 | 0.0373 |
| plaid | 304,530 | 39,009 | 18,930 | 0.1281 | 0.0622 |
| box | 232,848 | 60,220 | 17,559 | 0.2586 | 0.0754 |
| asana | 97,427 | 43,851 | 8,257 | 0.4501 | 0.0848 |
| hetzner | 167,308 | 22,157 | 14,242 | 0.1324 | 0.0851 |
| vercel | 136,159 | 24,767 | 13,472 | 0.1819 | 0.0989 |
| slack2 | 126,517 | 22,107 | 13,316 | 0.1747 | 0.1053 |
| linode | 203,653 | 44,120 | 21,795 | 0.2166 | 0.1070 |
| stripe-full | 1,034,829 | 154,855 | 118,758 | 0.1496 | 0.1148 |
| launchdarkly | 31,522 | 12,331 | 4,731 | 0.3912 | 0.1501 |
| netlify | 20,142 | 4,434 | 3,127 | 0.2201 | 0.1552 |
| twitter | 61,043 | 16,358 | 9,474 | 0.2680 | 0.1552 |
| gitlab | 88,242 | 30,130 | 15,092 | 0.3414 | 0.1710 |
| resend | 21,890 | 6,078 | 3,776 | 0.2777 | 0.1725 |
| vonage | 1,889 | 491 | 412 | 0.2599 | 0.2181 |
| github-core | 2,190 | 875 | 531 | 0.3995 | 0.2425 |
| circleci | 5,725 | 2,119 | 1,464 | 0.3701 | 0.2557 |
| stripe-charges | 1,892 | 1,020 | 490 | 0.5391 | 0.2590 |
| petstore | 4,656 | 1,689 | 1,217 | 0.3628 | 0.2614 |
| twilio-core | 2,465 | 1,245 | 688 | 0.5051 | 0.2791 |
| openai-core | 1,730 | 1,060 | 524 | 0.6127 | 0.3029 |
| google-maps | 941 | 460 | 316 | 0.4888 | 0.3358 |
| discord | 909 | 469 | 308 | 0.5160 | 0.3388 |
| cloudflare | 763 | 387 | 265 | 0.5072 | 0.3473 |
| spotify | 826 | 416 | 331 | 0.5036 | 0.4007 |
| sendgrid | 518 | 296 | 209 | 0.5714 | 0.4035 |
| slack | 762 | 435 | 316 | 0.5709 | 0.4147 |

## GRAPHQL — Per-Spec Details

| Spec | Raw Tokens | Std Tokens | Lean Tokens | Std Ratio | Lean Ratio |
|------|-----------|------------|-------------|-----------|------------|
| wordpress | 2,459 | 2,189 | 1,313 | 0.8902 | 0.5340 |
| github | 674 | 525 | 370 | 0.7789 | 0.5490 |
| cms | 764 | 580 | 448 | 0.7592 | 0.5864 |
| gitlab | 1,762 | 1,533 | 1,079 | 0.8700 | 0.6124 |
| linear | 1,854 | 1,582 | 1,215 | 0.8533 | 0.6553 |
| shopify | 1,971 | 1,698 | 1,293 | 0.8615 | 0.6560 |
| social | 642 | 510 | 424 | 0.7944 | 0.6604 |
| ecommerce | 614 | 481 | 409 | 0.7834 | 0.6661 |
| stripe | 1,539 | 1,373 | 1,056 | 0.8921 | 0.6862 |
| analytics | 473 | 389 | 339 | 0.8224 | 0.7167 |
| twitch | 1,251 | 1,082 | 901 | 0.8649 | 0.7202 |
| pinterest | 964 | 843 | 697 | 0.8745 | 0.7230 |
| fauna | 1,332 | 1,143 | 986 | 0.8581 | 0.7402 |
| medium | 1,119 | 930 | 849 | 0.8311 | 0.7587 |
| twitter | 1,336 | 1,150 | 1,021 | 0.8608 | 0.7642 |
| airbnb | 1,182 | 1,049 | 924 | 0.8875 | 0.7817 |
| figma | 1,286 | 1,132 | 1,048 | 0.8802 | 0.8149 |
| slack | 1,387 | 1,143 | 1,143 | 0.8241 | 0.8241 |
| reddit | 1,414 | 1,235 | 1,172 | 0.8734 | 0.8289 |
| netflix | 1,210 | 1,094 | 1,008 | 0.9041 | 0.8331 |
| dgraph | 2,274 | 1,907 | 1,905 | 0.8386 | 0.8377 |
| spotify | 1,568 | 1,322 | 1,321 | 0.8431 | 0.8425 |
| yelp | 857 | 729 | 724 | 0.8506 | 0.8448 |
| jira | 1,557 | 1,346 | 1,319 | 0.8645 | 0.8471 |
| discord | 1,492 | 1,287 | 1,276 | 0.8626 | 0.8552 |
| uber | 959 | 876 | 827 | 0.9135 | 0.8624 |
| contentful | 1,326 | 1,156 | 1,154 | 0.8718 | 0.8703 |
| hasura | 2,085 | 1,838 | 1,838 | 0.8815 | 0.8815 |
| youtube | 1,576 | 1,431 | 1,431 | 0.9080 | 0.9080 |
| notion | 1,840 | 1,752 | 1,743 | 0.9522 | 0.9473 |

## ASYNCAPI — Per-Spec Details

| Spec | Raw Tokens | Std Tokens | Lean Tokens | Std Ratio | Lean Ratio |
|------|-----------|------------|-------------|-----------|------------|
| social-media-backend | 615 | 117 | 117 | 0.1902 | 0.1902 |
| notifications | 708 | 391 | 351 | 0.5523 | 0.4958 |
| iot-mqtt | 656 | 486 | 377 | 0.7409 | 0.5747 |
| github-webhooks | 645 | 423 | 375 | 0.6558 | 0.5814 |
| chat-websocket | 658 | 473 | 389 | 0.7188 | 0.5912 |
| stripe-webhooks | 604 | 402 | 363 | 0.6656 | 0.6010 |
| social-media-feed | 447 | 308 | 279 | 0.6890 | 0.6242 |
| sports-scores | 559 | 406 | 368 | 0.7263 | 0.6583 |
| kubernetes-events | 648 | 472 | 432 | 0.7284 | 0.6667 |
| gaming-matchmaking | 644 | 469 | 431 | 0.7283 | 0.6693 |
| ad-bidding | 567 | 423 | 383 | 0.7460 | 0.6755 |
| video-streaming | 542 | 409 | 368 | 0.7546 | 0.6790 |
| ecommerce-kafka | 786 | 624 | 534 | 0.7939 | 0.6794 |
| iot-fleet | 575 | 450 | 397 | 0.7826 | 0.6904 |
| streaming-analytics | 662 | 528 | 466 | 0.7976 | 0.7039 |
| weather-alerts | 532 | 403 | 376 | 0.7575 | 0.7068 |
| slack-events | 476 | 380 | 340 | 0.7983 | 0.7143 |
| food-delivery | 447 | 351 | 321 | 0.7852 | 0.7181 |
| smart-home | 502 | 408 | 362 | 0.8127 | 0.7211 |
| email-delivery | 556 | 449 | 402 | 0.8076 | 0.7230 |
| ride-sharing | 565 | 469 | 427 | 0.8301 | 0.7558 |
| cdn-cache-invalidation | 547 | 466 | 418 | 0.8519 | 0.7642 |
| stock-market-feed | 534 | 460 | 413 | 0.8614 | 0.7734 |
| fraud-detection | 576 | 490 | 447 | 0.8507 | 0.7760 |
| kafka-ecommerce | 555 | 482 | 432 | 0.8685 | 0.7784 |
| cicd-pipeline | 522 | 452 | 411 | 0.8659 | 0.7874 |
| supply-chain | 615 | 526 | 486 | 0.8553 | 0.7902 |
| healthcare-monitoring | 630 | 553 | 506 | 0.8778 | 0.8032 |
| log-aggregation | 512 | 493 | 447 | 0.9629 | 0.8730 |
| payment-pipeline | 491 | 479 | 440 | 0.9756 | 0.8961 |
| aws-sns-sqs | 481 | 476 | 434 | 0.9896 | 0.9023 |

## PROTOBUF — Per-Spec Details

| Spec | Raw Tokens | Std Tokens | Lean Tokens | Std Ratio | Lean Ratio |
|------|-----------|------------|-------------|-----------|------------|
| google_bigquery_model | 16,144 | 203 | 195 | 0.0126 | 0.0121 |
| google_storage | 32,270 | 1,317 | 1,253 | 0.0408 | 0.0388 |
| google_talent_job_service | 10,851 | 546 | 538 | 0.0503 | 0.0496 |
| google_datacatalog | 20,924 | 1,774 | 1,720 | 0.0848 | 0.0822 |
| google_dialogflow_session | 8,005 | 828 | 817 | 0.1034 | 0.1021 |
| opentelemetry_collector | 1,337 | 236 | 218 | 0.1765 | 0.1631 |
| etcd_rpc | 11,785 | 2,249 | 2,036 | 0.1908 | 0.1728 |
| envoy_ext_auth | 597 | 227 | 224 | 0.3802 | 0.3752 |
| tensorflow_serving | 1,178 | 545 | 512 | 0.4626 | 0.4346 |
| istio_mixer | 885 | 420 | 405 | 0.4746 | 0.4576 |
| google_firestore | 2,310 | 1,159 | 1,114 | 0.5017 | 0.4823 |
| ml_serving | 765 | 459 | 445 | 0.6000 | 0.5817 |
| temporal_workflow | 1,524 | 953 | 891 | 0.6253 | 0.5846 |
| vitess_tabletmanager | 1,036 | 668 | 612 | 0.6448 | 0.5907 |
| buildkite_agent | 1,222 | 802 | 759 | 0.6563 | 0.6211 |
| google_spanner | 1,935 | 1,241 | 1,215 | 0.6413 | 0.6279 |
| coredns_service | 687 | 462 | 435 | 0.6725 | 0.6332 |
| prometheus_remote | 1,222 | 801 | 777 | 0.6555 | 0.6358 |
| nats_jetstream | 1,494 | 988 | 955 | 0.6613 | 0.6392 |
| payments | 653 | 426 | 418 | 0.6524 | 0.6401 |
| containerd_runtime | 1,033 | 719 | 662 | 0.6960 | 0.6409 |
| consul_health | 1,185 | 829 | 788 | 0.6996 | 0.6650 |
| workflow_service | 1,356 | 928 | 910 | 0.6844 | 0.6711 |
| notification_service | 1,145 | 810 | 786 | 0.7074 | 0.6865 |
| monitoring_service | 1,590 | 1,147 | 1,101 | 0.7214 | 0.6925 |
| kubernetes_pods | 1,262 | 897 | 876 | 0.7108 | 0.6941 |
| search_service | 1,648 | 1,172 | 1,147 | 0.7112 | 0.6960 |
| stripe_payments | 2,049 | 1,467 | 1,440 | 0.7160 | 0.7028 |
| chat | 662 | 477 | 467 | 0.7205 | 0.7054 |
| auth_service | 1,805 | 1,364 | 1,293 | 0.7557 | 0.7163 |
| user | 546 | 421 | 409 | 0.7711 | 0.7491 |
| analytics_service | 2,125 | 1,671 | 1,630 | 0.7864 | 0.7671 |
| logging_service | 1,056 | 837 | 820 | 0.7926 | 0.7765 |
| google_pubsub | 1,062 | 869 | 837 | 0.8183 | 0.7881 |
| health | 157 | 140 | 140 | 0.8917 | 0.8917 |

## POSTMAN — Per-Spec Details

| Spec | Raw Tokens | Std Tokens | Lean Tokens | Std Ratio | Lean Ratio |
|------|-----------|------------|-------------|-----------|------------|
| cisco-nso | 26,729 | 2,774 | 2,265 | 0.1038 | 0.0847 |
| usps-api | 28,224 | 3,022 | 2,553 | 0.1071 | 0.0905 |
| auth0-auth | 7,857 | 1,195 | 872 | 0.1521 | 0.1110 |
| ph-healthcare | 11,539 | 1,858 | 1,539 | 0.1610 | 0.1334 |
| openstack-compute | 38,981 | 6,564 | 5,298 | 0.1684 | 0.1359 |
| typesense | 15,704 | 3,152 | 2,668 | 0.2007 | 0.1699 |
| s3-storage | 1,179 | 301 | 251 | 0.2553 | 0.2129 |
| hubspot-crm | 1,307 | 334 | 286 | 0.2555 | 0.2188 |
| pagerduty-incidents | 1,173 | 309 | 264 | 0.2634 | 0.2251 |
| okta-sso | 1,330 | 375 | 309 | 0.2820 | 0.2323 |
| jira-projects | 1,478 | 406 | 352 | 0.2747 | 0.2382 |
| cloudflare-dns | 1,406 | 389 | 335 | 0.2767 | 0.2383 |
| stripe-payments | 1,236 | 353 | 295 | 0.2856 | 0.2387 |
| mongodb-atlas | 1,042 | 288 | 249 | 0.2764 | 0.2390 |
| launchdarkly-flags | 1,274 | 345 | 306 | 0.2708 | 0.2402 |
| twilio-messaging | 969 | 267 | 233 | 0.2755 | 0.2405 |
| shopify-ecommerce | 1,346 | 379 | 328 | 0.2816 | 0.2437 |
| vercel-deployments | 1,101 | 323 | 274 | 0.2934 | 0.2489 |
| docker-registry | 1,150 | 326 | 289 | 0.2835 | 0.2513 |
| sendgrid-email | 1,039 | 302 | 263 | 0.2907 | 0.2531 |
| file-upload | 922 | 293 | 234 | 0.3178 | 0.2538 |
| multi-env | 1,067 | 329 | 275 | 0.3083 | 0.2577 |
| crud-api | 924 | 295 | 240 | 0.3193 | 0.2597 |
| github-repos | 1,400 | 417 | 364 | 0.2979 | 0.2600 |
| datadog-monitoring | 1,141 | 343 | 298 | 0.3006 | 0.2612 |
| zoom-meetings | 1,139 | 335 | 298 | 0.2941 | 0.2616 |
| algolia-search | 1,153 | 341 | 302 | 0.2958 | 0.2619 |
| auth0-identity | 1,041 | 319 | 275 | 0.3064 | 0.2642 |
| notion-workspace | 1,239 | 371 | 329 | 0.2994 | 0.2655 |
| sentry-errors | 1,226 | 368 | 328 | 0.3002 | 0.2675 |
| mailchimp-marketing | 1,115 | 341 | 301 | 0.3058 | 0.2700 |
| discord-bot | 1,122 | 341 | 303 | 0.3039 | 0.2701 |
| auth-heavy | 1,311 | 415 | 355 | 0.3166 | 0.2708 |
| paginated | 1,206 | 417 | 340 | 0.3458 | 0.2819 |
| plaid-banking | 1,191 | 383 | 343 | 0.3216 | 0.2880 |
| slack-api | 972 | 359 | 316 | 0.3693 | 0.3251 |

## Key Insights

- **Total specs benchmarked:** 162
- **Overall standard compression:** median=0.6333, mean=0.5473
- **Overall lean compression:** median=0.5618, mean=0.4767
- **Lean vs Standard improvement:** 11.3% additional reduction at median
- **Best compressing format (lean median):** openapi (0.1631)
- **Least compressing format (lean median):** graphql (0.7730)
- **Median vs Mean gap:** Mean is typically lower than median, suggesting left-skewed distribution
