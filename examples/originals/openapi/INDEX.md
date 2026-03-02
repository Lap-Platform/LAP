# OpenAPI Specs - Original Documentation Index

This index maps OpenAPI spec files to their original documentation sources.

## Specs with Real Human Documentation

These have fetched markdown docs from vendor websites (stored in `specs/real-docs/`):

| Spec File | Original Docs | Source |
|-----------|---------------|--------|
| `specs/openai-core.yaml` | `specs/real-docs/openai-core.md` | platform.openai.com/docs |
| `specs/github-core.yaml` | `specs/real-docs/github-core.md` | docs.github.com/en/rest |
| `specs/stripe-charges.yaml` | `specs/real-docs/stripe-charges.md` | stripe.com/docs/api |
| `specs/twilio-core.yaml` | `output/twilio-core.verbose.md` | Generated verbose format |

## Synthetic/Example Specs

These specs are examples or synthetic test cases - the spec file IS the original source:

| Spec File | Type | Notes |
|-----------|------|-------|
| `specs/petstore.yaml` | Example | Standard OpenAPI 3.0 example spec |
| `specs/asana.yaml` | Real API | Large production API spec |
| `specs/box.yaml` | Real API | Box.com API spec |
| `specs/circleci.yaml` | Real API | CircleCI API spec |
| `specs/cloudflare.yaml` | Real API | Cloudflare API subset |
| `specs/digitalocean.yaml` | Real API | DigitalOcean API spec |
| `specs/discord.yaml` | Real API | Discord API subset |
| `specs/gitlab.yaml` | Real API | GitLab API spec |
| `specs/google-maps.yaml` | Real API | Google Maps API subset |
| `specs/hetzner.yaml` | Real API | Hetzner Cloud API |
| `specs/jira.yaml` | Real API | Jira API spec |
| `specs/launchdarkly.yaml` | Real API | LaunchDarkly API |
| `specs/linode.yaml` | Real API | Linode API spec |
| `specs/netlify.yaml` | Real API | Netlify API spec |
| `specs/notion.yaml` | Real API | Notion API spec |
| `specs/plaid.yaml` | Real API | Plaid API spec |
| `specs/resend.yaml` | Real API | Resend email API |
| `specs/sendgrid.yaml` | Real API | SendGrid API subset |
| `specs/slack.yaml` | Real API | Slack API subset |
| `specs/slack2.yaml` | Real API | Slack API (larger) |
| `specs/snyk.yaml` | Real API | Snyk API spec |
| `specs/spotify.yaml` | Real API | Spotify API subset |
| `specs/stripe-full.yaml` | Real API | Full Stripe API spec |
| `specs/twitter.yaml` | Real API | Twitter API spec |
| `specs/vercel.yaml` | Real API | Vercel API spec |
| `specs/vonage.yaml` | Real API | Vonage API spec |
| `specs/zoom.yaml` | Real API | Zoom API spec |

## Notes

- **Real API specs**: While these are real API specs (OpenAPI YAML), we don't have the human-readable markdown documentation for all of them
- **Benchmark strategy**: For specs without human docs, benchmarks compare against the generated verbose representation (`.to_original_text()`)
- **Token comparison**: DocLean format vs spec source YAML is meaningful since agents typically receive either the full spec or prose documentation
