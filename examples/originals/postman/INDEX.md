# Postman Collections - Original Documentation Index

Postman collections are self-documenting JSON files containing request definitions and embedded documentation.

## All Postman Collections

All 37 collections in `specs/postman/` are synthetic/example collections:

| Collection File | Type | Description |
|-----------------|------|-------------|
| `algolia-search.json` | Real-inspired | Algolia search API |
| `auth-heavy.json` | Synthetic | Authentication patterns demo |
| `auth0-auth.json` | Real-inspired | Auth0 authentication API |
| `auth0-identity.json` | Real-inspired | Auth0 identity management |
| `cisco-nso.json` | Real-inspired | Cisco NSO network automation |
| `cloudflare-dns.json` | Real-inspired | Cloudflare DNS management |
| `crud-api.json` | Synthetic | Basic CRUD operations example |
| `datadog-monitoring.json` | Real-inspired | Datadog monitoring API |
| `discord-bot.json` | Real-inspired | Discord bot API |
| `docker-registry.json` | Real-inspired | Docker registry API |
| `file-upload.json` | Synthetic | File upload patterns |
| `github-repos.json` | Real-inspired | GitHub repositories API |
| `hubspot-crm.json` | Real-inspired | HubSpot CRM API |
| `jira-projects.json` | Real-inspired | Jira projects API |
| `launchdarkly-flags.json` | Real-inspired | LaunchDarkly feature flags |
| `mailchimp-marketing.json` | Real-inspired | Mailchimp marketing API |
| `mongodb-atlas.json` | Real-inspired | MongoDB Atlas API |
| `multi-env.json` | Synthetic | Multi-environment configuration |
| `notion-workspace.json` | Real-inspired | Notion workspace API |
| `okta-sso.json` | Real-inspired | Okta SSO API |
| `openstack-compute.json` | Real-inspired | OpenStack compute API |
| `pagerduty-incidents.json` | Real-inspired | PagerDuty incidents API |
| `paginated.json` | Synthetic | Pagination patterns demo |
| `ph-healthcare.json` | Synthetic | Healthcare API example |
| `plaid-banking.json` | Real-inspired | Plaid banking API |
| `s3-storage.json` | Real-inspired | AWS S3 storage API |
| `sendgrid-email.json` | Real-inspired | SendGrid email API |
| `sentry-errors.json` | Real-inspired | Sentry error tracking |
| `shopify-ecommerce.json` | Real-inspired | Shopify e-commerce API |
| `slack-api.json` | Real-inspired | Slack API |
| `stripe-collection.json` | Real-inspired | Stripe API collection |
| `stripe-payments.json` | Real-inspired | Stripe payments API |
| `twilio-messaging.json` | Real-inspired | Twilio messaging API |
| `typesense.json` | Real-inspired | Typesense search API |
| `usps-api.json` | Real-inspired | USPS shipping API |
| `vercel-deployments.json` | Real-inspired | Vercel deployments API |
| `zoom-meetings.json` | Real-inspired | Zoom meetings API |

## Original Documentation Format

For Postman collections:
- **The collection JSON IS the documentation** - includes request details, descriptions, examples
- **Embedded documentation**: Descriptions at collection, folder, and request levels
- **No separate verbose docs needed** - collections are self-contained

## Postman Self-Documentation Structure

Postman collections embed documentation within the JSON:

```json
{
  "info": {
    "name": "Stripe Payments API",
    "description": "Complete Stripe payments API collection with examples",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Create Payment Intent",
      "request": {
        "method": "POST",
        "description": "Creates a new payment intent for the specified amount",
        "url": "{{baseUrl}}/v1/payment_intents"
      }
    }
  ]
}
```

This embedded documentation is the "original" format.

## Benchmark Strategy

- **Compare against**: The collection JSON itself or extracted documentation
- **DocLean compression**: Test how DocLean compresses Postman collection metadata into agent-usable format
- **All comparisons**: Local-to-local (collections stored in specs/postman/)
