# LAP Real-World Benchmark Report

_Generated: 2026-02-08 02:01 UTC_

_Token counting: tiktoken cl100k_base_

_Sessions analyzed: 50 (from 1513 total)_

## 1. API Doc Token Consumption: OpenAPI vs LAP

### Per-Spec Comparison

| Spec | YAML Tokens | Standard Tokens | Lean Tokens | Standard Reduction | Lean Reduction | Lean Saved |
|------|------------|----------------|-------------|-------------------|---------------|------------|
| stripe-charges | 1,891 | 992 | 461 | 47.5% | 75.6% | 1,430 |
| github-core | 2,186 | 954 | 545 | 56.4% | 75.1% | 1,641 |
| twilio-core | 2,459 | 1,295 | 693 | 47.3% | 71.8% | 1,766 |
| slack | 758 | 353 | 234 | 53.4% | 69.1% | 524 |
| discord | 906 | 414 | 254 | 54.3% | 72.0% | 652 |
| openai-core | 1,725 | 989 | 453 | 42.7% | 73.7% | 1,272 |

**Average tokens per spec:** YAML=1,654 → Lean=440 (saves 1,214 tokens per inclusion)

### Projected Savings Over Agent Calls

If each agent call includes one API spec as context:

| Calls | YAML Total Tokens | Lean Total Tokens | Tokens Saved | Estimated Cost Saved ($0.005/1K in) |
|-------|-------------------|-------------------|-------------|-------------------------------------|
| 100 | 165,417 | 44,000 | 121,417 | $0.61 |
| 1,000 | 1,654,167 | 440,000 | 1,214,167 | $6.07 |
| 10,000 | 16,541,667 | 4,400,000 | 12,141,667 | $60.71 |

## 2. A2A Communication: Natural Language vs A2A-Lean

| # | NL Tokens | Compact Tokens | JSON Tokens | Compact Savings | Message Preview |
|---|----------|---------------|------------|----------------|-----------------|
| 1 | 22 | 23 | 30 | -4.5% | Please search for recent news articles about AI re... |
| 2 | 18 | 19 | 30 | -5.6% | Create a new GitHub issue titled 'Bug fix' in repo... |
| 3 | 11 | 13 | 26 | -18.2% | Delete the file 'temp.log' from /var/tmp |
| 4 | 13 | 17 | 29 | -30.8% | Update the issue 'Bug fix' set status to 'closed' |
| 5 | 14 | 22 | 33 | -57.1% | Get the latest 10 commits from github.com/openai/t... |
| 6 | 6 | 9 | 21 | -50.0% | List all repositories in my-org |
| 7 | 11 | 12 | 23 | -9.1% | Run the command 'pytest -v' on ci-server |
| 8 | 11 | 10 | 22 | 9.1% | Send a message to #general saying 'Deployment comp... |
| 9 | 17 | 19 | 26 | -11.8% | Search for Python tutorials about async programmin... |
| 10 | 12 | 14 | 26 | -16.7% | Create a new branch called 'feature/auth' in my-pr... |
| 11 | 6 | 9 | 21 | -50.0% | Fetch the status for production-api |
| 12 | 13 | 18 | 29 | -38.5% | Delete the branch 'hotfix/old' from main-repo |
| 13 | 13 | 18 | 30 | -38.5% | Update the config 'app.yaml' set replicas to '3' |
| 14 | 8 | 12 | 23 | -50.0% | Get the logs for web-server-01 |
| 15 | 7 | 11 | 22 | -57.1% | List all issues in bug-tracker |
| 16 | 13 | 15 | 26 | -15.4% | Execute the command 'docker build -t app .' on bui... |
| 17 | 12 | 15 | 27 | -25.0% | Notify @ops-team with 'Disk usage above 90%' |
| 18 | 9 | 10 | 21 | -11.1% | Search for 5 open source alternatives to Slack |
| 19 | 13 | 16 | 28 | -23.1% | Create a new webhook called 'deploy-notify' in my-... |
| 20 | 6 | 9 | 21 | -50.0% | Show all users in admin-panel |
| 21 | 17 | 19 | 26 | -11.8% | Find recent research papers about quantum computin... |
| 22 | 13 | 14 | 26 | -7.7% | Change the title of 'Old Name' to 'New Name' |
| 23 | 9 | 11 | 22 | -22.2% | Run the command 'npm test' on staging |
| 24 | 7 | 11 | 22 | -57.1% | Get the metrics for api-gateway |

**Average:** NL=11.7 tokens → Compact=14.4 tokens (-23.1% reduction)

## 3. Real Agent Session Token Usage

_Parsed 50 sessions from OpenClaw JSONL transcripts_

### Session Statistics

- **Average total tokens per session:** 381,920
- **Average input context per session:** 380,170
- **Average cost per session:** $0.3099
- **Median total tokens:** 42,286

### Top 15 Sessions by Token Usage

| Session | Model | Messages | Input | Output | Cache Read | Total | Cost |
|---------|-------|----------|-------|--------|------------|-------|------|
| 6ca30a08-57a… | claude-opus-4-6 | 215 | 372 | 69,643 | 16,083,601 | 16,653,526 | $12.9092 |
| f2571211-794… | claude-opus-4-6 | 6 | 8 | 796 | 97,366 | 98,637 | $0.0715 |
| a0c18997-68b… | claude-opus-4-5 | 5 | 7 | 1,151 | 88,956 | 95,519 | $0.1071 |
| 1b749fe2-ea0… | claude-sonnet-4-5 | 6 | 56 | 1,053 | 60,875 | 94,038 | $0.2097 |
| 2cabd5d7-7e7… | claude-opus-4-6 | 5 | 7 | 699 | 81,067 | 81,773 | $0.0580 |
| 0071e46c-2d4… | claude-opus-4-6 | 5 | 7 | 651 | 80,061 | 81,734 | $0.0627 |
| a880199e-5cc… | claude-opus-4-6 | 5 | 7 | 657 | 79,228 | 81,624 | $0.0669 |
| d8d6e00d-27c… | claude-opus-4-6 | 5 | 7 | 610 | 80,005 | 81,566 | $0.0612 |
| 706082dc-946… | claude-opus-4-6 | 5 | 7 | 588 | 80,851 | 81,536 | $0.0557 |
| 973a3312-bae… | claude-opus-4-6 | 5 | 7 | 594 | 80,931 | 81,532 | $0.0554 |
| cedd6b2e-870… | claude-opus-4-6 | 3 | 5 | 458 | 52,057 | 58,575 | $0.0753 |
| 6866c9b6-aac… | claude-opus-4-6 | 3 | 5 | 429 | 52,053 | 58,512 | $0.0744 |
| 7f29741e-de9… | claude-opus-4-6 | 3 | 5 | 439 | 52,039 | 58,506 | $0.0747 |
| 9ca188f9-9bc… | claude-opus-4-6 | 3 | 5 | 434 | 52,051 | 58,501 | $0.0745 |
| 391b42b4-8aa… | claude-opus-4-6 | 3 | 5 | 425 | 52,045 | 58,491 | $0.0743 |

## 4. LAP Impact Projection

Assuming a typical session includes 1 API spec as context:

- A full API spec (1,654 tokens) is **0.4%** of avg session input (380,170 tokens)
- LAP-Lean saves 1,214 tokens = **0.3%** of session input
- Over 1,000 sessions: saves **1,214,167 tokens** ($6.07)
- Over 10,000 sessions: saves **12,141,667 tokens** ($60.71)

## Methodology

- **Token counting:** tiktoken cl100k_base encoding (used by GPT-4, Claude approximation)
- **Spec files:** Real OpenAPI YAML specs from `/data/workspace/lap-poc/specs/`
- **LAP output:** Real LAP-processed specs from `/data/workspace/lap-poc/output/`
- **Session data:** Real OpenClaw JSONL session transcripts from `/data/agents/main/sessions/`
- **A2A messages:** Example messages from `src/a2a_lean.py` compiled to A2A-Lean format
- **Cost estimate:** $0.005/1K input tokens (approximate Claude/GPT-4 blended rate)
- **No synthetic or estimated data.** All numbers derived from actual files.
