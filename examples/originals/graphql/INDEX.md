# GraphQL Schemas - Original Documentation Index

GraphQL schemas are self-documenting through SDL (Schema Definition Language) with inline descriptions and comments.

## All GraphQL Schemas

All 30 schemas in `specs/graphql/` are synthetic/example schemas that demonstrate various GraphQL patterns:

| Schema File | Type | Description |
|-------------|------|-------------|
| `airbnb.graphql` | Synthetic | Vacation rental platform schema |
| `analytics.graphql` | Synthetic | Analytics/metrics tracking |
| `cms.graphql` | Synthetic | Content management system |
| `contentful.graphql` | Real-inspired | Headless CMS (Contentful-style) |
| `dgraph.graphql` | Real-inspired | Graph database schema |
| `discord.graphql` | Real-inspired | Discord-style messaging platform |
| `ecommerce.graphql` | Synthetic | E-commerce platform |
| `fauna.graphql` | Real-inspired | FaunaDB-style schema |
| `figma.graphql` | Real-inspired | Design tool API |
| `github.graphql` | Real-inspired | GitHub-style code platform |
| `gitlab.graphql` | Real-inspired | GitLab-style DevOps platform |
| `hasura.graphql` | Real-inspired | Hasura-style schema |
| `jira.graphql` | Real-inspired | Jira-style project management |
| `linear.graphql` | Real-inspired | Linear-style issue tracker |
| `medium.graphql` | Real-inspired | Medium-style publishing platform |
| `netflix.graphql` | Real-inspired | Streaming service schema |
| `notion.graphql` | Real-inspired | Notion-style workspace |
| `pinterest.graphql` | Real-inspired | Pinterest-style content discovery |
| `reddit.graphql` | Real-inspired | Reddit-style forum |
| `shopify.graphql` | Real-inspired | Shopify-style e-commerce |
| `slack.graphql` | Real-inspired | Slack-style messaging |
| `social.graphql` | Synthetic | Social media platform |
| `spotify.graphql` | Real-inspired | Spotify-style music streaming |
| `stripe.graphql` | Real-inspired | Stripe-style payments |
| `twitch.graphql` | Real-inspired | Twitch-style streaming |
| `twitter.graphql` | Real-inspired | Twitter-style social media |
| `uber.graphql` | Real-inspired | Uber-style ride-hailing |
| `wordpress.graphql` | Real-inspired | WordPress-style CMS |
| `yelp.graphql` | Real-inspired | Yelp-style local search |
| `youtube.graphql` | Real-inspired | YouTube-style video platform |

## Original Documentation Format

For GraphQL:
- **The schema IS the documentation** - SDL format with types, fields, descriptions
- **No separate verbose docs needed** - GraphQL is inherently self-documenting
- **DocLean comparison**: Compare against the schema itself or introspection query results

## Schema Documentation Pattern

GraphQL schemas include inline documentation:

```graphql
"""
User account information
"""
type User {
  "Unique user identifier"
  id: ID!
  
  "User's email address"
  email: String!
  
  "User's display name"
  name: String
}
```

This inline documentation is the "original" format - no external markdown needed.
