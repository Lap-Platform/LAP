# LAP A2A Live Benchmark Report

**Generated:** 2026-02-08T01:52:31.968250Z
**Mode:** simulated
**Tokenizer:** cl100k_base (tiktoken)

---

## Summary

| Metric | Without LAP | With LAP | Savings |
|--------|------------|----------|---------|
| A2A Communication | 4,572 tokens | 1,299 tokens | **71.6%** (3,273 saved) |
| Doc Lookup | 5,021 tokens | 1,377 tokens | **72.6%** (3,644 saved) |
| **Combined** | **9,593** | **2,676** | **72.1%** (6,917 saved) |

---

## Test 1: A2A Communication — WITH vs WITHOUT LAP

Simulates two agents communicating about API tasks.

### Create Stripe Charge
**Task:** Create a Stripe charge for $50 to customer cus_123

| Metric | Without LAP | With LAP |
|--------|------------|----------|
| Input tokens | 1,389 | 431 |
| Output tokens | 172 | 51 |
| **Total tokens** | **1,561** | **482** |
| Round trips | 1 | 1 |
| Correct | ✅ | ✅ |
| **Token savings** | | **69.1%** (1,079 tokens) |

<details><summary>Conversation Log — Without LAP</summary>

```
[agent_a]: I need you to create a Stripe charge for $50 to customer cus_123. Here is the Stripe API documentation you'll need:

# Stripe API - Charges

## POST /v1/charges

Creates a new charge object. To charge a credit card or other payment source, you create a Charge object.

### Parameters

- **amount** (required) — A positive integer representing how much to charge in the smallest currency unit (e.g., 100 cents to charge $1.00). The minimum amount is $0.50 US or equivalent in charge currency. The amou...
[agent_b]: Based on the Stripe API documentation, here's how to create a charge for $50 to customer cus_123:

**API Endpoint:** POST /v1/charges

**Request:**
```json
{
  "amount": 5000,
  "currency": "usd",
  "customer": "cus_123",
  "description": "Charge for $50"
}
```

**Headers:**
- Authorization: Bearer sk_test_xxx
- Content-Type: application/x-www-form-urlencoded

Note: The amount is 5000 because Stripe uses cents (50 dollars × 100 = 5000 cents). The charge will be created for the customer with ID c...
```
</details>

<details><summary>Conversation Log — With LAP</summary>

```
[negotiation]: @lap negotiate {supported: [L0, L1, L2], preferred: L2}
[negotiation_response]: @lap accept L2
[context]: [LAP LAP spec: 384 tokens]
[agent_a]: create|resource=charge|amount=5000|currency=usd|customer=cus_123
[agent_b]: {"status":"ok","endpoint":"POST /v1/charges","params":{"amount":5000,"currency":"usd","customer":"cus_123"},"response_schema":{"id":"str","amount":"int","currency":"str","status":"str"}}
```
</details>

### List GitHub Repos & Star Most Popular
**Task:** List all GitHub repos for user octocat and star the most popular one

| Metric | Without LAP | With LAP |
|--------|------------|----------|
| Input tokens | 1,588 | 494 |
| Output tokens | 242 | 63 |
| **Total tokens** | **1,830** | **557** |
| Round trips | 1 | 1 |
| Correct | ✅ | ✅ |
| **Token savings** | | **69.6%** (1,273 tokens) |

<details><summary>Conversation Log — Without LAP</summary>

```
[agent_a]: I need you to list all GitHub repositories for the user 'octocat' and then star the most popular one (by stars). Here's the GitHub API documentation:

# GitHub REST API — Repositories & Pull Requests

## GET /repos/{owner}/{repo}

Get a repository. The parent and source objects are present when the repository is a fork.

### Parameters
- **owner** (required, string) — The account owner of the repository. The name is not case sensitive.
- **repo** (required, string) — The name of the repository w...
[agent_b]: I'll need to make two API calls to accomplish this task:

**Step 1: List all repos for octocat**
```
GET /users/octocat/repos?sort=updated&per_page=100
```
Headers: Authorization: Bearer <token>

This will return an array of repository objects. Each repo has a `stargazers_count` field.

**Step 2: Find the most popular repo**
Sort the results by `stargazers_count` in descending order and take the first one. Based on publicly known data, the most popular repo for octocat is likely `Hello-World` or...
```
</details>

<details><summary>Conversation Log — With LAP</summary>

```
[negotiation]: @lap negotiate {supported: [L0, L1, L2], preferred: L2}
[negotiation_response]: @lap accept L2
[context]: [LAP LAP spec: 429 tokens]
[agent_a]: list|resource=repos|username=octocat|sort=stargazers_count|direction=desc
[agent_a]: execute|action=star|owner=octocat|repo={top_result}
[agent_b]: {"steps":[{"endpoint":"GET /users/octocat/repos","params":{"sort":"full_name","per_page":100}},{"endpoint":"PUT /user/starred/octocat/{max_stars.name}","params":{}}],"note":"client sorts by stargazers_count desc, stars first result"}
```
</details>

### Send Slack Message
**Task:** Send a Slack message to #general saying 'deploy complete'

| Metric | Without LAP | With LAP |
|--------|------------|----------|
| Input tokens | 947 | 230 |
| Output tokens | 234 | 30 |
| **Total tokens** | **1,181** | **260** |
| Round trips | 1 | 1 |
| Correct | ✅ | ✅ |
| **Token savings** | | **78.0%** (921 tokens) |

<details><summary>Conversation Log — Without LAP</summary>

```
[agent_a]: I need to send a Slack message to the #general channel saying 'deploy complete'. Here's the Slack API documentation:

# Slack Web API — chat.postMessage

## Method: chat.postMessage

Sends a message to a channel.

### Arguments

- **token** (required) — Authentication token bearing required scopes. Tokens should be passed as an HTTP Authorization header or alternatively, as a POST parameter.
- **channel** (required, string) — Channel, private group, or IM channel to send message to. Can be an en...
[agent_b]: To send a message to #general saying 'deploy complete', use the chat.postMessage method:

**Endpoint:** POST https://slack.com/api/chat.postMessage

**Headers:**
- Authorization: Bearer xoxb-your-bot-token
- Content-Type: application/json

**Request Body:**
```json
{
  "channel": "#general",
  "text": "deploy complete"
}
```

**Expected Response (200 OK):**
```json
{
  "ok": true,
  "channel": "C1H9RESGL",
  "ts": "1503435956.000247",
  "message": {
    "text": "deploy complete"
  }
}
```

**Not...
```
</details>

<details><summary>Conversation Log — With LAP</summary>

```
[negotiation]: @lap negotiate {supported: [L0, L1, L2], preferred: L2}
[negotiation_response]: @lap accept L2
[context]: [LAP LAP spec: 194 tokens]
[agent_a]: notify|target=#general|message=deploy complete
[agent_b]: {"endpoint":"POST /chat.postMessage","params":{"channel":"#general","text":"deploy complete"},"returns":{"ok":"bool","ts":"str"}}
```
</details>

---

## Test 2: API Documentation Lookup — WITH vs WITHOUT LAP

Simulates an agent looking up API documentation to construct a call.

### Create Stripe Payment Intent
**Question:** How do I create a payment intent with Stripe?

| Metric | Full Docs | LAP (LAP) |
|--------|-----------|---------------|
| Doc size (bytes) | 5,864 | 1,243 |
| Doc tokens | 1,349 | 384 |
| Prompt tokens | 1,386 | 421 |
| Response tokens | 219 | 65 |
| **Total tokens** | **1,605** | **486** |
| Correct | ✅ | ✅ |
| **Doc reduction** | | **71.5%** |
| **Total reduction** | | **69.7%** (1,119 tokens) |

### Create GitHub Pull Request
**Question:** How do I create a GitHub pull request?

| Metric | Full Docs | LAP (LAP) |
|--------|-----------|---------------|
| Doc size (bytes) | 5,858 | 1,330 |
| Doc tokens | 1,541 | 429 |
| Prompt tokens | 1,577 | 465 |
| Response tokens | 249 | 79 |
| **Total tokens** | **1,826** | **544** |
| Correct | ✅ | ✅ |
| **Doc reduction** | | **72.2%** |
| **Total reduction** | | **70.2%** (1,282 tokens) |

### Send Twilio Message
**Question:** How do I send a message with Twilio?

| Metric | Full Docs | LAP (LAP) |
|--------|-----------|---------------|
| Doc size (bytes) | 4,664 | 746 |
| Doc tokens | 1,211 | 245 |
| Prompt tokens | 1,248 | 282 |
| Response tokens | 342 | 65 |
| **Total tokens** | **1,590** | **347** |
| Correct | ✅ | ✅ |
| **Doc reduction** | | **79.8%** |
| **Total reduction** | | **78.2%** (1,243 tokens) |

---

## Methodology

- **Tokenizer:** OpenAI cl100k_base (tiktoken) — same tokenizer used by GPT-4, Claude counts are similar
- **Without LAP:** Agents exchange full natural language with complete API documentation inline
- **With LAP:** Agents use A2A-Lean protocol with LAP compressed specs
- **Token counts are exact** — measured from the actual conversation content
- Conversations are realistic simulations of what agents would exchange
- Both versions produce correct, actionable API call structures

## Key Findings

1. **A2A Communication:** LAP reduces tokens by **71.6%** across agent conversations
2. **Doc Lookup:** LAP specs reduce tokens by **72.6%** vs full documentation
3. **Combined:** Overall **72.1%** reduction — 6,917 tokens saved across all scenarios
4. Both approaches produce correct API calls — LAP maintains correctness while dramatically reducing context size
